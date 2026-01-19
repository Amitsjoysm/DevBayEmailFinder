from typing import Optional, Dict
from datetime import datetime, timezone
from models import EmailLedger, VerificationStatus, EmailProvider
import logging

logger = logging.getLogger(__name__)

class LedgerService:
    """Service to manage unified email verification/finder ledger"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.email_ledger
    
    async def initialize(self):
        """Create indexes for efficient lookups"""
        try:
            # Create unique index on email
            await self.collection.create_index("email", unique=True)
            # Create index on user_id for filtering
            await self.collection.create_index("user_id")
            # Create index on last_verified_at for sorting
            await self.collection.create_index("last_verified_at")
            logger.info("Email ledger indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create ledger indexes: {e}")
    
    async def get_from_ledger(self, email: str, user_id: str) -> Optional[Dict]:
        """
        Check if email exists in ledger and return cached result
        Returns None if not found or result is stale (>30 days)
        """
        try:
            entry = await self.collection.find_one(
                {"email": email.lower(), "user_id": user_id},
                {"_id": 0}
            )
            
            if not entry:
                return None
            
            # Check if entry is fresh (less than 30 days old)
            last_verified = entry.get('last_verified_at')
            if isinstance(last_verified, str):
                last_verified = datetime.fromisoformat(last_verified.replace('Z', '+00:00'))
            
            age_days = (datetime.now(timezone.utc) - last_verified).days
            
            # Return cached result if less than 30 days old
            if age_days < 30:
                logger.info(f"Ledger hit for {email} (age: {age_days} days)")
                return entry
            else:
                logger.info(f"Ledger entry for {email} is stale ({age_days} days), will re-verify")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get from ledger: {e}")
            return None
    
    async def save_to_ledger(self, email: str, user_id: str, result: Dict, source: str = "verification", job_id: str = None):
        """
        Save or update email verification/finder result in ledger
        """
        try:
            email_lower = email.lower()
            now = datetime.now(timezone.utc)
            
            # Check if entry exists
            existing = await self.collection.find_one({"email": email_lower, "user_id": user_id})
            
            ledger_data = {
                "email": email_lower,
                "status": result.get('status', VerificationStatus.UNKNOWN),
                "provider": result.get('provider', EmailProvider.CUSTOM),
                "mx_records": result.get('mx_records', []),
                "response_time": result.get('response_time', 0),
                "smtp_response": result.get('smtp_response'),
                "is_catch_all": result.get('is_catch_all', False),
                "is_role_based": result.get('is_role_based', False),
                "is_disposable": result.get('is_disposable', False),
                "deliverability_score": result.get('deliverability_score', 0),
                "source": source,
                "last_verified_at": now.isoformat(),
                "user_id": user_id,
                "last_job_id": job_id,
            }
            
            # Add finder-specific metadata if available
            if source == "finder":
                ledger_data.update({
                    "first_name": result.get('first_name'),
                    "last_name": result.get('last_name'),
                    "domain": result.get('domain'),
                    "patterns_tested": result.get('patterns_tested', 0),
                })
            
            if existing:
                # Update existing entry
                ledger_data["verification_count"] = existing.get('verification_count', 1) + 1
                await self.collection.update_one(
                    {"email": email_lower, "user_id": user_id},
                    {"$set": ledger_data}
                )
                logger.info(f"Updated ledger entry for {email}")
            else:
                # Create new entry
                ledger_data.update({
                    "first_verified_at": now.isoformat(),
                    "verification_count": 1,
                })
                await self.collection.insert_one(ledger_data)
                logger.info(f"Created ledger entry for {email}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to save to ledger: {e}")
            return False
    
    async def get_ledger_stats(self, user_id: str) -> Dict:
        """Get statistics from ledger"""
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]
            
            results = await self.collection.aggregate(pipeline).to_list(None)
            
            stats = {
                "total_emails": 0,
                "valid": 0,
                "invalid": 0,
                "risky": 0,
                "unknown": 0,
                "total_verifications": 0
            }
            
            for result in results:
                status = result['_id']
                count = result['count']
                stats['total_emails'] += count
                
                if status == VerificationStatus.VALID:
                    stats['valid'] = count
                elif status == VerificationStatus.INVALID:
                    stats['invalid'] = count
                elif status in [VerificationStatus.RISKY, VerificationStatus.DISPOSABLE]:
                    stats['risky'] += count
                else:
                    stats['unknown'] += count
            
            # Get total verification count
            total_verifications = await self.collection.aggregate([
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": None, "total": {"$sum": "$verification_count"}}}
            ]).to_list(None)
            
            if total_verifications:
                stats['total_verifications'] = total_verifications[0].get('total', 0)
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get ledger stats: {e}")
            return {}
    
    async def search_ledger(self, user_id: str, query: str = None, status: str = None, limit: int = 100, skip: int = 0) -> list:
        """Search ledger entries"""
        try:
            filter_query = {"user_id": user_id}
            
            if query:
                filter_query["email"] = {"$regex": query, "$options": "i"}
            
            if status:
                filter_query["status"] = status
            
            results = await self.collection.find(
                filter_query,
                {"_id": 0}
            ).sort("last_verified_at", -1).skip(skip).limit(limit).to_list(None)
            
            return results
        except Exception as e:
            logger.error(f"Failed to search ledger: {e}")
            return []
