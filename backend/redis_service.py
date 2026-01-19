"""
Production-Ready Redis Service for Email Verifier
Handles: Job persistence, caching, rate limiting, distributed locking
"""

import redis
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import logging
from contextlib import asynccontextmanager
import time

logger = logging.getLogger(__name__)

class RedisService:
    """
    Production-ready Redis service with:
    - Job state persistence
    - L1 caching layer
    - Distributed rate limiting
    - Distributed locking
    - Health monitoring
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis_client = None
        self._connection_pool = None
        self._is_healthy = False
        
        # Key prefixes for organization
        self.PREFIXES = {
            'job_state': 'job:state:',
            'job_progress': 'job:progress:',
            'job_queue': 'job:queue:',
            'cache': 'cache:email:',
            'rate_limit': 'rate:',
            'lock': 'lock:',
            'stats': 'stats:',
            'health': 'health:'
        }
        
        # TTL configurations (in seconds)
        self.TTL = {
            'job_state': 86400 * 7,  # 7 days
            'job_progress': 3600,     # 1 hour (for active jobs)
            'cache': 86400 * 30,      # 30 days (matches ledger)
            'rate_limit': 60,         # 1 minute
            'lock': 300,              # 5 minutes
            'completed_job': 86400 * 3  # 3 days for completed jobs
        }
    
    def connect(self):
        """Initialize Redis connection with connection pooling"""
        try:
            self._connection_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=50,
                decode_responses=True,
                socket_keepalive=True,
                socket_connect_timeout=5,
                health_check_interval=30
            )
            
            self.redis_client = redis.Redis(connection_pool=self._connection_pool)
            
            # Test connection
            self.redis_client.ping()
            self._is_healthy = True
            logger.info("✅ Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self._is_healthy = False
            self.redis_client = None
    
    def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed")
    
    def is_healthy(self) -> bool:
        """Check Redis health"""
        try:
            if self.redis_client:
                self.redis_client.ping()
                self._is_healthy = True
                return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self._is_healthy = False
        return False
    
    # ============================================================================
    # JOB STATE PERSISTENCE (Phase 1 - Critical)
    # ============================================================================
    
    def save_job_state(self, job_id: str, job_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Save job state to Redis for persistence across restarts
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['job_state']}{job_id}"
            
            # Serialize job data (convert datetime objects)
            serialized_data = self._serialize_job_data(job_data)
            
            # Save to Redis
            self.redis_client.set(
                key,
                json.dumps(serialized_data),
                ex=ttl or self.TTL['job_state']
            )
            
            # Add to active jobs set
            if job_data.get('status') == 'processing':
                self.redis_client.sadd('active_jobs', job_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save job state for {job_id}: {e}")
            return False
    
    def get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job state from Redis"""
        if not self.redis_client:
            return None
        
        try:
            key = f"{self.PREFIXES['job_state']}{job_id}"
            data = self.redis_client.get(key)
            
            if data:
                return self._deserialize_job_data(json.loads(data))
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job state for {job_id}: {e}")
            return None
    
    def delete_job_state(self, job_id: str) -> bool:
        """Remove job state from Redis"""
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['job_state']}{job_id}"
            self.redis_client.delete(key)
            self.redis_client.srem('active_jobs', job_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete job state for {job_id}: {e}")
            return False
    
    def get_active_jobs(self) -> List[str]:
        """Get all active job IDs"""
        if not self.redis_client:
            return []
        
        try:
            return list(self.redis_client.smembers('active_jobs'))
        except Exception as e:
            logger.error(f"Failed to get active jobs: {e}")
            return []
    
    def mark_job_completed(self, job_id: str) -> bool:
        """Mark job as completed and reduce TTL"""
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['job_state']}{job_id}"
            # Reduce TTL for completed jobs
            self.redis_client.expire(key, self.TTL['completed_job'])
            self.redis_client.srem('active_jobs', job_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark job completed {job_id}: {e}")
            return False
    
    # ============================================================================
    # EMAIL RESULT CACHING (Phase 1 - Performance)
    # ============================================================================
    
    def cache_email_result(self, email: str, user_id: str, result: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Cache email verification result (L1 cache before MongoDB)
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['cache']}{user_id}:{email.lower()}"
            
            # Add timestamp
            result['cached_at'] = datetime.now(timezone.utc).isoformat()
            
            self.redis_client.set(
                key,
                json.dumps(result),
                ex=ttl or self.TTL['cache']
            )
            
            # Track cache stats
            self.increment_stat('cache_writes')
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache email result for {email}: {e}")
            return False
    
    def get_cached_email_result(self, email: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached email result (L1 cache check)
        Returns None if not found or expired
        """
        if not self.redis_client:
            return None
        
        try:
            key = f"{self.PREFIXES['cache']}{user_id}:{email.lower()}"
            data = self.redis_client.get(key)
            
            if data:
                result = json.loads(data)
                
                # Check if cache is still fresh (30 days)
                if 'cached_at' in result:
                    cached_time = datetime.fromisoformat(result['cached_at'].replace('Z', '+00:00'))
                    age_days = (datetime.now(timezone.utc) - cached_time).days
                    
                    if age_days <= 30:
                        self.increment_stat('cache_hits')
                        return result
                
                # Cache expired, delete it
                self.redis_client.delete(key)
            
            self.increment_stat('cache_misses')
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached email result for {email}: {e}")
            return None
    
    def invalidate_email_cache(self, email: str, user_id: str) -> bool:
        """Invalidate cached email result"""
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['cache']}{user_id}:{email.lower()}"
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate cache for {email}: {e}")
            return False
    
    # ============================================================================
    # DISTRIBUTED RATE LIMITING (Phase 2)
    # ============================================================================
    
    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check if rate limit is exceeded
        Returns: (allowed: bool, remaining: int)
        """
        if not self.redis_client:
            return True, max_requests  # Allow if Redis unavailable
        
        try:
            rate_key = f"{self.PREFIXES['rate_limit']}{key}"
            
            # Get current count
            current = self.redis_client.get(rate_key)
            
            if current is None:
                # First request in window
                self.redis_client.setex(rate_key, window_seconds, 1)
                return True, max_requests - 1
            
            current = int(current)
            
            if current >= max_requests:
                return False, 0
            
            # Increment
            self.redis_client.incr(rate_key)
            return True, max_requests - current - 1
            
        except Exception as e:
            logger.error(f"Rate limit check failed for {key}: {e}")
            return True, max_requests  # Fail open
    
    def apply_domain_rate_limit(self, user_id: str, domain: str, delay_seconds: int) -> float:
        """
        Apply domain-specific rate limiting with distributed locking
        Returns: seconds to wait
        """
        if not self.redis_client:
            return 0
        
        try:
            rate_key = f"{self.PREFIXES['rate_limit']}domain:{user_id}:{domain}"
            
            # Get last request time
            last_request = self.redis_client.get(rate_key)
            
            if last_request:
                elapsed = time.time() - float(last_request)
                if elapsed < delay_seconds:
                    wait_time = delay_seconds - elapsed
                    return wait_time
            
            # Update last request time
            self.redis_client.setex(rate_key, delay_seconds * 2, time.time())
            return 0
            
        except Exception as e:
            logger.error(f"Domain rate limit failed for {domain}: {e}")
            return 0
    
    # ============================================================================
    # DISTRIBUTED LOCKING (Phase 2)
    # ============================================================================
    
    @asynccontextmanager
    async def acquire_lock(self, lock_name: str, timeout: int = 10, blocking_timeout: int = 5):
        """
        Distributed lock for concurrent operations
        Usage:
            async with redis_service.acquire_lock("job:123"):
                # Critical section
        """
        lock_key = f"{self.PREFIXES['lock']}{lock_name}"
        lock_value = f"{time.time()}"
        acquired = False
        
        try:
            if not self.redis_client:
                yield  # No locking if Redis unavailable
                return
            
            # Try to acquire lock
            start_time = time.time()
            while time.time() - start_time < blocking_timeout:
                acquired = self.redis_client.set(lock_key, lock_value, nx=True, ex=timeout)
                if acquired:
                    break
                await asyncio.sleep(0.1)
            
            if not acquired:
                logger.warning(f"Failed to acquire lock: {lock_name}")
            
            yield
            
        finally:
            # Release lock
            if acquired:
                try:
                    self.redis_client.delete(lock_key)
                except Exception as e:
                    logger.error(f"Failed to release lock {lock_name}: {e}")
    
    # ============================================================================
    # JOB PROGRESS TRACKING (Phase 2)
    # ============================================================================
    
    def update_job_progress(self, job_id: str, progress_data: Dict[str, Any]) -> bool:
        """
        Update job progress in Redis for fast reads
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['job_progress']}{job_id}"
            
            # Store as hash for efficient partial updates
            self.redis_client.hset(key, mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in progress_data.items()
            })
            
            # Set TTL
            self.redis_client.expire(key, self.TTL['job_progress'])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update job progress for {job_id}: {e}")
            return False
    
    def get_job_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job progress from Redis"""
        if not self.redis_client:
            return None
        
        try:
            key = f"{self.PREFIXES['job_progress']}{job_id}"
            data = self.redis_client.hgetall(key)
            
            if not data:
                return None
            
            # Deserialize values
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except:
                    result[k] = v
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get job progress for {job_id}: {e}")
            return None
    
    # ============================================================================
    # STATISTICS & MONITORING (Phase 3)
    # ============================================================================
    
    def increment_stat(self, stat_name: str, amount: int = 1) -> bool:
        """Increment a statistics counter"""
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.PREFIXES['stats']}{stat_name}"
            self.redis_client.incr(key, amount)
            
            # Also track daily stats
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            daily_key = f"{self.PREFIXES['stats']}daily:{today}:{stat_name}"
            self.redis_client.incr(daily_key, amount)
            self.redis_client.expire(daily_key, 86400 * 30)  # Keep 30 days
            
            return True
        except Exception as e:
            logger.error(f"Failed to increment stat {stat_name}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all statistics"""
        if not self.redis_client:
            return {}
        
        try:
            stats = {}
            
            # Get all stat keys
            stat_keys = self.redis_client.keys(f"{self.PREFIXES['stats']}*")
            
            for key in stat_keys:
                stat_name = key.replace(self.PREFIXES['stats'], '')
                if not stat_name.startswith('daily:'):
                    stats[stat_name] = int(self.redis_client.get(key) or 0)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        stats = self.get_stats()
        
        hits = stats.get('cache_hits', 0)
        misses = stats.get('cache_misses', 0)
        total = hits + misses
        
        return {
            'cache_hits': hits,
            'cache_misses': misses,
            'total_requests': total,
            'hit_rate': round(hits / total * 100, 2) if total > 0 else 0,
            'cache_writes': stats.get('cache_writes', 0)
        }
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _serialize_job_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize job data for Redis storage"""
        serialized = {}
        
        for key, value in data.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif hasattr(value, 'value'):  # Enum
                serialized[key] = value.value
            else:
                serialized[key] = value
        
        return serialized
    
    def _deserialize_job_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize job data from Redis"""
        deserialized = {}
        
        datetime_fields = ['created_at', 'started_at', 'completed_at', 'paused_at']
        
        for key, value in data.items():
            if key in datetime_fields and value:
                try:
                    deserialized[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except:
                    deserialized[key] = value
            else:
                deserialized[key] = value
        
        return deserialized
    
    def flush_all(self, pattern: Optional[str] = None) -> int:
        """
        Flush keys matching pattern (for testing/maintenance)
        WARNING: Use with caution in production
        """
        if not self.redis_client:
            return 0
        
        try:
            if pattern:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            else:
                # Flush entire database
                self.redis_client.flushdb()
                return -1
        except Exception as e:
            logger.error(f"Failed to flush keys: {e}")
            return 0
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis server information"""
        if not self.redis_client:
            return {'status': 'disconnected'}
        
        try:
            info = self.redis_client.info()
            
            return {
                'status': 'connected',
                'version': info.get('redis_version'),
                'uptime_seconds': info.get('uptime_in_seconds'),
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': info.get('used_memory_human'),
                'total_connections_received': info.get('total_connections_received'),
                'total_commands_processed': info.get('total_commands_processed'),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec'),
                'keyspace': info.get('db0', {})
            }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {'status': 'error', 'error': str(e)}


# Global Redis service instance
redis_service = None

def get_redis_service() -> Optional[RedisService]:
    """Get global Redis service instance"""
    return redis_service

def init_redis_service(redis_url: str = "redis://localhost:6379/0") -> RedisService:
    """Initialize global Redis service"""
    global redis_service
    redis_service = RedisService(redis_url)
    redis_service.connect()
    return redis_service
