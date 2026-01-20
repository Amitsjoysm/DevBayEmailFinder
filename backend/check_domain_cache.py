import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def check_cache():
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['email_verifier']
    
    print("\n" + "="*80)
    print("Domain Pattern Cache Contents")
    print("="*80 + "\n")
    
    cache_entries = await db.domain_pattern_cache.find({}).to_list(None)
    
    if not cache_entries:
        print("No cached patterns found.")
    else:
        for entry in cache_entries:
            print(f"Domain: {entry.get('domain')}")
            print(f"  Pattern: {entry.get('pattern')}")
            print(f"  Success Count: {entry.get('success_count')}")
            print(f"  Confidence: {entry.get('confidence_score')}")
            print(f"  Last Example: {entry.get('last_example')}")
            print()
    
    print("="*80 + "\n")
    client.close()

asyncio.run(check_cache())
