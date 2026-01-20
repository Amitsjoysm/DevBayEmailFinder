import asyncio
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from domain_cache_service import DomainCacheService
from email_finder import EmailFinder
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

async def test_cached_pattern_override():
    """Test that first.last is checked FIRST even when cache has a different pattern"""
    
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['email_verifier']
    
    print("\n" + "="*80)
    print("Testing Cached Pattern Override")
    print("="*80)
    
    # Manually insert a cache entry with {first}@{domain} pattern for testdomain.com
    test_domain = "testcompany.example"
    await db.domain_pattern_cache.delete_one({'domain': test_domain})
    await db.domain_pattern_cache.insert_one({
        'domain': test_domain,
        'pattern': '{first}@{domain}',  # Different from first.last
        'success_count': 5,
        'confidence_score': 75,
        'first_success_at': datetime.now(timezone.utc),
        'last_success_at': datetime.now(timezone.utc),
        'created_by_user_id': 'test',
        'last_user_id': 'test',
        'last_example': {
            'email': 'john@testcompany.example',
            'first_name': 'john',
            'last_name': 'smith'
        }
    })
    
    print(f"\n✅ Injected cache entry for {test_domain}:")
    print(f"   Cached pattern: {{first}}@{{domain}}")
    print(f"   This should be #2, not #1")
    print()
    
    # Initialize services
    domain_cache_service = DomainCacheService(db)
    await domain_cache_service.initialize()
    finder = EmailFinder(domain_cache_service=domain_cache_service)
    
    # Generate variants
    print("-"*80)
    variants = await finder.generate_email_variants_with_cache(
        first_name="john",
        last_name="doe",
        domain=test_domain
    )
    
    print("\nGenerated Pattern Order:")
    for idx, email in enumerate(variants, 1):
        marker = ""
        if "john.doe@" in email:
            marker = " ⭐ (first.last - should be #1)"
        elif email == f"john@{test_domain}":
            marker = " 📌 (cached pattern - should be #2)"
        print(f"  {idx}. {email}{marker}")
    
    print("\n" + "-"*80)
    
    # Verify
    if variants[0] == f"john.doe@{test_domain}":
        print("✅ SUCCESS: first.last@domain is #1 (as expected)")
    elif variants[0] == f"john@{test_domain}":
        print("❌ FAIL: Cached pattern is #1 (should be #2)")
    
    if variants[1] == f"john@{test_domain}":
        print("✅ SUCCESS: Cached pattern is #2 (as expected)")
    
    print("="*80 + "\n")
    
    # Cleanup
    await db.domain_pattern_cache.delete_one({'domain': test_domain})
    client.close()

asyncio.run(test_cached_pattern_override())
