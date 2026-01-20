import asyncio
import sys
import os
import logging

# Setup logging to see detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_finder import EmailFinder
from domain_cache_service import DomainCacheService
from motor.motor_asyncio import AsyncIOMotorClient

async def test_pattern_generation():
    """Test pattern generation order"""
    
    # Setup MongoDB connection
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['email_verifier']
    
    # Initialize domain cache service
    domain_cache_service = DomainCacheService(db)
    await domain_cache_service.initialize()
    
    # Initialize EmailFinder
    finder = EmailFinder(domain_cache_service=domain_cache_service)
    
    print("\n" + "="*80)
    print("Testing Pattern Generation Order")
    print("="*80)
    
    # Generate email variants (this will log the order)
    variants = await finder.generate_email_variants_with_cache(
        first_name="amit",
        last_name="jadhav",
        domain="marketjoy.com"
    )
    
    print("\nGenerated Pattern Order:")
    for idx, email in enumerate(variants, 1):
        print(f"  {idx}. {email}")
    
    print("\n" + "="*80)
    print("✅ Pattern order test complete!")
    print("="*80 + "\n")
    
    # Close connection
    client.close()

if __name__ == "__main__":
    asyncio.run(test_pattern_generation())
