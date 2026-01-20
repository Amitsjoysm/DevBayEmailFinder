import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_finder import EmailFinder
from domain_cache_service import DomainCacheService
from motor.motor_asyncio import AsyncIOMotorClient

async def test_finder_priority():
    """Test that first.last@domain is checked FIRST, before cached pattern"""
    
    # Setup MongoDB connection
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['email_verifier']
    
    # Initialize domain cache service
    domain_cache_service = DomainCacheService(db)
    await domain_cache_service.initialize()
    
    # Initialize EmailFinder with domain cache
    finder = EmailFinder(domain_cache_service=domain_cache_service)
    
    print("\n" + "="*80)
    print("🧪 Testing Email Finder Pattern Priority")
    print("="*80)
    print("\nTest Case:")
    print("  Domain: marketjoy.com")
    print("  First Name: amit")
    print("  Last Name: jadhav")
    print("  Expected: amit.jadhav@marketjoy.com should be found FIRST")
    print("  Note: Both amit@marketjoy.com and amit.jadhav@marketjoy.com are valid")
    print("\n" + "-"*80)
    
    # Test the finder
    result = await finder.find_email(
        first_name="amit",
        last_name="jadhav",
        domain="marketjoy.com",
        stop_on_first_valid=True,
        user_id="test_user_123"
    )
    
    print("\n" + "-"*80)
    print("📊 RESULT:")
    print("-"*80)
    print(f"  Found: {result.get('found')}")
    print(f"  Email: {result.get('email')}")
    print(f"  Pattern: {result.get('pattern')}")
    print(f"  Total Checked: {result.get('total_checked', 0)}")
    print(f"  Response Time: {result.get('response_time', 0):.2f}s")
    
    if result.get('all_results'):
        print(f"\n  All Results ({len(result['all_results'])} checked):")
        for idx, r in enumerate(result['all_results'][:5], 1):  # Show first 5
            print(f"    {idx}. {r.get('email')} - {r.get('status')}")
    
    print("\n" + "="*80)
    
    # Verification
    if result.get('found') and result.get('email') == 'amit.jadhav@marketjoy.com':
        print("✅ SUCCESS: Correct email found (first.last format)!")
    elif result.get('found') and result.get('email') == 'amit@marketjoy.com':
        print("❌ FAIL: Wrong email found (first format instead of first.last)!")
        print("   This means cached pattern took priority over first.last pattern")
    else:
        print("⚠️  Email not found or unexpected result")
    
    print("="*80 + "\n")
    
    # Close connection
    client.close()

if __name__ == "__main__":
    asyncio.run(test_finder_priority())
