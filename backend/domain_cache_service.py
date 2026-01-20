from typing import Optional, Dict, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class DomainCacheService:
    """Service to manage persistent domain pattern caching"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.domain_pattern_cache
    
    async def initialize(self):
        """Create indexes for efficient lookups"""
        try:
            # Create unique compound index on domain
            await self.collection.create_index("domain", unique=True)
            # Create index on success_count for analytics
            await self.collection.create_index("success_count")
            # Create index on last_success_at for sorting
            await self.collection.create_index("last_success_at")
            logger.info("Domain pattern cache indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create domain cache indexes: {e}")
    
    async def get_domain_pattern(self, domain: str) -> Optional[Dict]:
        """
        Get cached pattern for a domain
        Returns pattern info if exists, None otherwise
        """
        try:
            domain_lower = domain.lower()
            entry = await self.collection.find_one(
                {"domain": domain_lower},
                {"_id": 0}
            )
            
            if entry:
                logger.info(f"✅ Domain cache HIT for {domain}: {entry['pattern']} (success_count: {entry['success_count']})")
                return entry
            else:
                logger.info(f"❌ Domain cache MISS for {domain}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get domain pattern: {e}")
            return None
    
    async def save_domain_pattern(self, domain: str, pattern: str, user_id: str, 
                                   email_found: str = None, first_name: str = None, 
                                   last_name: str = None) -> bool:
        """
        Save or update domain pattern cache
        Increments success_count if pattern already exists
        """
        try:
            domain_lower = domain.lower()
            now = datetime.now(timezone.utc)
            
            # Check if entry exists
            existing = await self.collection.find_one({"domain": domain_lower})
            
            if existing:
                # Update existing entry
                success_count = existing.get('success_count', 0) + 1
                
                # Build update data
                update_data = {
                    "success_count": success_count,
                    "last_success_at": now.isoformat(),
                    "last_user_id": user_id,
                    "confidence_score": min(100, 50 + (success_count * 5))  # 50-100 based on success
                }
                
                # Add example if provided
                if email_found and first_name and last_name:
                    update_data["last_example"] = {
                        "email": email_found,
                        "first_name": first_name,
                        "last_name": last_name
                    }
                
                # If pattern changed, track it
                if existing.get('pattern') != pattern:
                    logger.warning(f"⚠️ Pattern changed for {domain}: {existing['pattern']} -> {pattern}")
                    update_data["pattern"] = pattern
                    update_data["pattern_changed_at"] = now.isoformat()
                
                await self.collection.update_one(
                    {"domain": domain_lower},
                    {"$set": update_data}
                )
                logger.info(f"💾 Updated domain cache for {domain}: {pattern} (success_count: {success_count})")
            else:
                # Create new entry
                cache_data = {
                    "domain": domain_lower,
                    "pattern": pattern,
                    "success_count": 1,
                    "first_success_at": now.isoformat(),
                    "last_success_at": now.isoformat(),
                    "created_by_user_id": user_id,
                    "last_user_id": user_id,
                    "confidence_score": 50,  # Initial confidence
                }
                
                # Add example if provided
                if email_found and first_name and last_name:
                    cache_data["last_example"] = {
                        "email": email_found,
                        "first_name": first_name,
                        "last_name": last_name
                    }
                
                await self.collection.insert_one(cache_data)
                logger.info(f"🆕 Created domain cache for {domain}: {pattern}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to save domain pattern: {e}")
            return False
    
    async def get_pattern_stats(self, domain: str = None) -> Dict:
        """Get statistics about domain patterns"""
        try:
            if domain:
                # Get stats for specific domain
                entry = await self.get_domain_pattern(domain)
                if entry:
                    return {
                        "domain": domain,
                        "pattern": entry['pattern'],
                        "success_count": entry['success_count'],
                        "confidence_score": entry['confidence_score'],
                        "first_success_at": entry.get('first_success_at'),
                        "last_success_at": entry.get('last_success_at'),
                        "last_example": entry.get('last_example')
                    }
                return {}
            else:
                # Get overall stats
                total_domains = await self.collection.count_documents({})
                
                # Get most common patterns
                pipeline = [
                    {"$group": {
                        "_id": "$pattern",
                        "count": {"$sum": 1},
                        "total_successes": {"$sum": "$success_count"}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 10}
                ]
                
                pattern_distribution = await self.collection.aggregate(pipeline).to_list(None)
                
                # Get top performing domains
                top_domains = await self.collection.find(
                    {},
                    {"_id": 0, "domain": 1, "pattern": 1, "success_count": 1, "confidence_score": 1}
                ).sort("success_count", -1).limit(10).to_list(None)
                
                return {
                    "total_domains_cached": total_domains,
                    "pattern_distribution": pattern_distribution,
                    "top_performing_domains": top_domains
                }
        except Exception as e:
            logger.error(f"Failed to get pattern stats: {e}")
            return {}
    
    async def search_cached_domains(self, query: str = None, limit: int = 100, skip: int = 0) -> List[Dict]:
        """Search cached domains"""
        try:
            filter_query = {}
            
            if query:
                filter_query["domain"] = {"$regex": query, "$options": "i"}
            
            results = await self.collection.find(
                filter_query,
                {"_id": 0}
            ).sort("success_count", -1).skip(skip).limit(limit).to_list(None)
            
            return results
        except Exception as e:
            logger.error(f"Failed to search cached domains: {e}")
            return []
    
    async def delete_domain_cache(self, domain: str) -> bool:
        """Delete cache entry for a domain"""
        try:
            domain_lower = domain.lower()
            result = await self.collection.delete_one({"domain": domain_lower})
            
            if result.deleted_count > 0:
                logger.info(f"🗑️ Deleted domain cache for {domain}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete domain cache: {e}")
            return False
    
    async def clear_all_cache(self) -> bool:
        """Clear all domain cache entries (admin only)"""
        try:
            result = await self.collection.delete_many({})
            logger.info(f"🗑️ Cleared all domain cache ({result.deleted_count} entries)")
            return True
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False
