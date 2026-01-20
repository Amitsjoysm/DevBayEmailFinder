import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from email_verifier import EmailVerifier
from redis_service import RedisService
from ledger_service import LedgerService
from queue_manager import serialize_result_for_cache

async def test_live_verification():
    """Test live verification with Redis caching"""
    
    print("\n" + "="*80)
    print("Testing Live Email Verification with Redis Caching")
    print("="*80 + "\n")
    
    # Setup services
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['email_verifier']
    
    redis_service = RedisService(redis_url='redis://localhost:6379/0')
    redis_service.connect()
    
    if not redis_service.is_healthy():
        print("❌ Redis not available")
        return
    
    print("✅ Services initialized")
    print("  - MongoDB connected")
    print("  - Redis connected and healthy\n")
    
    # Initialize services
    verifier = EmailVerifier()
    ledger = LedgerService(db)
    
    # Test email
    test_email = "test@gmail.com"
    test_user = "test_user_verification"
    
    print("-"*80)
    print(f"Test 1: First verification (should hit SMTP)")
    print("-"*80)
    
    # Clear any existing cache
    redis_service.invalidate_email_cache(test_email, test_user)
    
    # First verification
    result1 = await verifier.verify_email(test_email, use_api_fallback=True)
    
    print(f"  Email: {result1.get('email')}")
    print(f"  Status: {result1.get('status')}")
    print(f"  Provider: {result1.get('provider')}")
    print(f"  Response Time: {result1.get('response_time', 0):.2f}s")
    
    # Serialize and cache
    serialized = serialize_result_for_cache(result1)
    redis_service.cache_email_result(test_email, test_user, serialized)
    print(f"  ✅ Cached result in Redis")
    
    # Save to ledger
    await ledger.save_to_ledger(test_email, test_user, result1, source="verification")
    print(f"  ✅ Saved to ledger\n")
    
    print("-"*80)
    print(f"Test 2: Second verification (should hit cache)")
    print("-"*80)
    
    # Try to get from cache
    cached = redis_service.get_cached_email_result(test_email, test_user)
    
    if cached:
        print(f"  ✅ Cache HIT!")
        print(f"  Email: {cached.get('email')}")
        print(f"  Status: {cached.get('status')}")
        print(f"  Provider: {cached.get('provider')}")
        print(f"  Cached At: {cached.get('cached_at')}")
    else:
        print(f"  ❌ Cache MISS")
    
    # Check ledger
    ledger_result = await ledger.get_from_ledger(test_email, test_user)
    if ledger_result:
        print(f"  ✅ Ledger HIT!")
        print(f"  Verification Count: {ledger_result.get('verification_count')}")
    
    print("\n" + "-"*80)
    print("Cache Statistics:")
    print("-"*80)
    
    stats = redis_service.get_cache_stats()
    print(f"  Cache Hits: {stats.get('cache_hits')}")
    print(f"  Cache Misses: {stats.get('cache_misses')}")
    print(f"  Cache Writes: {stats.get('cache_writes')}")
    print(f"  Hit Rate: {stats.get('hit_rate')}%")
    
    print("\n" + "="*80)
    print("✅ Live verification test completed successfully!")
    print("="*80 + "\n")
    
    # Cleanup
    redis_service.disconnect()
    client.close()

if __name__ == "__main__":
    asyncio.run(test_live_verification())
