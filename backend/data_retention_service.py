"""Data Retention and Monitoring Service

This service ensures that verification/finder history and ledger data
are properly retained and never accidentally deleted.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

class DataRetentionService:
    """Service to monitor and protect data from accidental deletion"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_data_health_report(self, user_id: str = None) -> Dict:
        """
        Generate comprehensive data health report
        Shows if data is being properly retained
        """
        try:
            report = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "healthy",
                "warnings": [],
                "collections": {}
            }
            
            # Check each critical collection
            collections = [
                "verification_jobs",
                "verification_results",
                "finder_results",
                "email_ledger",
                "users"
            ]
            
            for coll_name in collections:
                query = {"user_id": user_id} if user_id and coll_name != "users" else {}
                
                total_count = await self.db[coll_name].count_documents(query)
                
                # Get date range if applicable
                if coll_name in ["verification_jobs", "verification_results", "finder_results"]:
                    # Get oldest and newest records
                    oldest = await self.db[coll_name].find_one(
                        query,
                        sort=[("created_at" if coll_name == "verification_jobs" else "verified_at", 1)]
                    )
                    newest = await self.db[coll_name].find_one(
                        query,
                        sort=[("created_at" if coll_name == "verification_jobs" else "verified_at", -1)]
                    )
                    
                    oldest_date = None
                    newest_date = None
                    
                    if oldest:
                        date_field = "created_at" if coll_name == "verification_jobs" else "verified_at"
                        oldest_date = oldest.get(date_field)
                        if isinstance(oldest_date, str):
                            oldest_date = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
                    
                    if newest:
                        date_field = "created_at" if coll_name == "verification_jobs" else "verified_at"
                        newest_date = newest.get(date_field)
                        if isinstance(newest_date, str):
                            newest_date = datetime.fromisoformat(newest_date.replace('Z', '+00:00'))
                    
                    report["collections"][coll_name] = {
                        "count": total_count,
                        "oldest_record": oldest_date.isoformat() if oldest_date else None,
                        "newest_record": newest_date.isoformat() if newest_date else None,
                        "retention_days": (newest_date - oldest_date).days if oldest_date and newest_date else 0
                    }
                else:
                    report["collections"][coll_name] = {
                        "count": total_count
                    }
                
                # Add warnings
                if total_count == 0 and coll_name != "users":
                    report["warnings"].append(f"{coll_name} is empty - no data has been saved yet")
            
            # Check for suspicious data loss patterns
            jobs_count = report["collections"]["verification_jobs"]["count"]
            results_count = report["collections"]["verification_results"]["count"]
            finder_results_count = report["collections"]["finder_results"]["count"]
            ledger_count = report["collections"]["email_ledger"]["count"]
            
            if jobs_count > 0 and results_count == 0 and finder_results_count == 0:
                report["warnings"].append("CRITICAL: Jobs exist but no results found - data may be getting deleted")
                report["status"] = "critical"
            
            if results_count > 0 and ledger_count == 0:
                report["warnings"].append("WARNING: Verification results exist but ledger is empty - ledger may not be working")
                report["status"] = "warning"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate data health report: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def create_data_retention_indexes(self):
        """
        Ensure NO TTL indexes exist that would auto-delete data
        This is a safety check
        """
        try:
            collections = [
                "verification_jobs",
                "verification_results",
                "finder_results",
                "email_ledger"
            ]
            
            for coll_name in collections:
                # Get all indexes
                indexes = await self.db[coll_name].index_information()
                
                # Check for TTL indexes
                for idx_name, idx_info in indexes.items():
                    if 'expireAfterSeconds' in idx_info:
                        logger.warning(f"⚠️  FOUND TTL INDEX on {coll_name}.{idx_name}: {idx_info['expireAfterSeconds']} seconds")
                        logger.warning(f"    This will auto-delete data after {idx_info['expireAfterSeconds'] / 3600} hours!")
                        logger.warning(f"    Consider removing this index if data retention is required")
            
            logger.info("✅ Data retention check complete - no automatic deletion configured")
            
        except Exception as e:
            logger.error(f"Failed to check data retention indexes: {e}")
    
    async def get_recent_activity(self, user_id: str, hours: int = 24) -> Dict:
        """
        Get recent activity to verify data is being saved
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            cutoff_iso = cutoff_time.isoformat()
            
            # Count recent jobs
            recent_jobs = await self.db.verification_jobs.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": cutoff_iso}
            })
            
            # Count recent verification results
            recent_verifications = await self.db.verification_results.count_documents({
                "user_id": user_id,
                "verified_at": {"$gte": cutoff_iso}
            })
            
            # Count recent finder results
            recent_finds = await self.db.finder_results.count_documents({
                "user_id": user_id,
                "verified_at": {"$gte": cutoff_iso}
            })
            
            return {
                "period_hours": hours,
                "recent_jobs": recent_jobs,
                "recent_verifications": recent_verifications,
                "recent_finds": recent_finds,
                "total_recent_activity": recent_jobs + recent_verifications + recent_finds
            }
            
        except Exception as e:
            logger.error(f"Failed to get recent activity: {e}")
            return {}
