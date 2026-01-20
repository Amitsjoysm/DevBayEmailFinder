import asyncio
import os
from redis_service import RedisService
from datetime import datetime, timezone
from models import VerificationStatus, EmailProvider

async def test_redis_caching():
    """Test Redis email result caching with proper serialization"""
    
    print("\n" + "="*80)
    print("Testing Redis Email Result Caching")
    print("="*80 + "\n")
    
    # Initialize Redis
    redis_service = RedisService(redis_url='redis://localhost:6379/0')
    redis_service.connect()
    
    if not redis_service.is_healthy():
        print("❌ Redis is not available!")
        return
    
    print("✅ Redis connected and healthy\n")
    
    # Test 1: Cache a verification result (with proper serialization)
    test_email = "test@example.com"
    test_user = "test_user_123"
    
    # Create a result with Enum and datetime objects (as returned by verifier)
    verification_result = {
        'email': test_email,
        'status': VerificationStatus.VALID,  # Enum
        'provider': EmailProvider.GMAIL,      # Enum
        'mx_records': ['mx1.example.com'],
        'response_time': 1.23,
        'smtp_response': '250 OK',
        'is_catch_all': False,
        'is_role_based': False,
        'is_disposable': False,
        'verified_at': datetime.now(timezone.utc),  # datetime object
        'retry_count': 0,
        'deliverability_score': 85
    }
    
    print("Test 1: Caching verification result with Enums and datetime")
    print("-"*80)
    print(f"  Email: {test_email}")
    print(f"  Status: {verification_result['status']} (type: {type(verification_result['status'])})")
    print(f"  Provider: {verification_result['provider']} (type: {type(verification_result['provider'])})")
    print(f"  Verified At: {verification_result['verified_at']} (type: {type(verification_result['verified_at'])})")
    
    # Serialize before caching (as done in queue_manager)
    from queue_manager import serialize_result_for_cache
    serialized_result = serialize_result_for_cache(verification_result)
    
    print("\n  After serialization:")
    print(f"  Status: {serialized_result['status']} (type: {type(serialized_result['status'])})")
    print(f"  Provider: {serialized_result['provider']} (type: {type(serialized_result['provider'])})")
    print(f"  Verified At: {serialized_result['verified_at']} (type: {type(serialized_result['verified_at'])})")
    
    # Cache the result
    success = redis_service.cache_email_result(test_email, test_user, serialized_result)
    
    if success:
        print("\n✅ Successfully cached result")
    else:
        print("\n❌ Failed to cache result")
        return
    
    # Test 2: Retrieve cached result
    print("\n" + "-"*80)
    print("Test 2: Retrieving cached result")
    print("-"*80)
    
    cached = redis_service.get_cached_email_result(test_email, test_user)
    
    if cached:
        print("✅ Successfully retrieved cached result")
        print(f"  Email: {cached.get('email')}")
        print(f"  Status: {cached.get('status')}")
        print(f"  Provider: {cached.get('provider')}")
        print(f"  Verified At: {cached.get('verified_at')}")
        print(f"  Cached At: {cached.get('cached_at')}")
    else:
        print("❌ Failed to retrieve cached result")
    
    # Test 3: Cache stats
    print("\n" + "-"*80)
    print("Test 3: Cache statistics")
    print("-"*80)
    
    stats = redis_service.get_cache_stats()
    print(f"  Cache Hits: {stats.get('cache_hits')}")
    print(f"  Cache Misses: {stats.get('cache_misses')}")
    print(f"  Cache Writes: {stats.get('cache_writes')}")
    print(f"  Hit Rate: {stats.get('hit_rate')}%")
    
    print("\n" + "="*80)
    print("✅ All Redis caching tests passed!")
    print("="*80 + "\n")
    
    # Cleanup
    redis_service.invalidate_email_cache(test_email, test_user)
    redis_service.disconnect()

if __name__ == "__main__":
    asyncio.run(test_redis_caching())
