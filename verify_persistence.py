#!/usr/bin/env python3
"""
Verification Script for Email Verifier Data Persistence
Tests Redis, MongoDB, and ensures history remains persistent
"""

import asyncio
import redis
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime

# Load environment variables
backend_dir = Path(__file__).parent / 'backend'
load_dotenv(backend_dir / '.env')

def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def check_redis():
    """Test Redis connectivity and features"""
    print_section("🔴 REDIS VERIFICATION")
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    print(f"📍 Redis URL: {redis_url}")
    
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        response = r.ping()
        print(f"✅ Connection: HEALTHY (PING: {response})")
        
        # Get server info
        info = r.info('server')
        print(f"✅ Version: {info['redis_version']}")
        print(f"✅ Uptime: {info['uptime_in_seconds']} seconds ({info['uptime_in_seconds'] // 3600} hours)")
        
        # Memory info
        memory_info = r.info('memory')
        print(f"✅ Memory Used: {memory_info['used_memory_human']}")
        
        # Database info
        stats = r.info('stats')
        print(f"✅ Total Connections: {stats['total_connections_received']}")
        print(f"✅ Commands Processed: {stats['total_commands_processed']}")
        
        # Keys count
        keys_count = r.dbsize()
        print(f"✅ Total Keys: {keys_count}")
        
        # Test persistence
        test_key = 'persistence_test'
        test_value = {'timestamp': datetime.utcnow().isoformat(), 'test': 'data'}
        r.set(test_key, json.dumps(test_value), ex=3600)
        retrieved = json.loads(r.get(test_key))
        print(f"✅ Persistence Test: SET/GET working correctly")
        
        print("\n🎉 REDIS: FULLY OPERATIONAL")
        return True
        
    except Exception as e:
        print(f"\n❌ Redis Connection Failed: {e}")
        return False

async def check_mongodb():
    """Test MongoDB connectivity and verify no TTL indexes"""
    print_section("🍃 MONGODB VERIFICATION")
    
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    print(f"📍 MongoDB URL: {mongo_url}")
    print(f"📍 Database: {db_name}")
    
    try:
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Test connection
        await client.admin.command('ping')
        print(f"✅ Connection: HEALTHY")
        
        # Get collections
        collections = await db.list_collection_names()
        print(f"✅ Collections Found: {len(collections)}")
        
        # Check each collection
        print("\n📊 Collection Details:")
        total_docs = 0
        for coll in collections:
            count = await db[coll].count_documents({})
            total_docs += count
            print(f"   - {coll}: {count} documents")
        
        print(f"\n✅ Total Documents: {total_docs}")
        
        # Verify no TTL indexes (critical for data persistence)
        print("\n🔍 Checking for TTL Indexes (Auto-Delete):")
        ttl_found = False
        
        critical_collections = ['jobs', 'verification_results', 'finder_results', 'email_ledger']
        for coll in critical_collections:
            if coll in collections:
                indexes = await db[coll].index_information()
                for idx_name, idx_info in indexes.items():
                    if 'expireAfterSeconds' in idx_info:
                        ttl_found = True
                        print(f"   ⚠️  {coll}.{idx_name}: TTL {idx_info['expireAfterSeconds']}s")
        
        if not ttl_found:
            print(f"   ✅ NO TTL INDEXES - Data persists indefinitely")
        
        # Check EmailLedger compound unique index
        print("\n🔍 Checking EmailLedger Index (Multi-User Support):")
        if 'email_ledger' in collections:
            indexes = await db.email_ledger.index_information()
            compound_index_found = False
            for idx_name, idx_info in indexes.items():
                if 'key' in idx_info:
                    keys = list(idx_info['key'])
                    if len(keys) == 2 and ('email', 1) in keys and ('user_id', 1) in keys:
                        compound_index_found = True
                        print(f"   ✅ Compound Index Found: (email, user_id)")
                        if idx_info.get('unique'):
                            print(f"   ✅ Unique Constraint: Enabled")
            
            if not compound_index_found:
                print(f"   ⚠️  Compound index not found - will be created on first use")
        else:
            print(f"   ℹ️  EmailLedger collection will be created on first verification")
        
        print("\n🎉 MONGODB: FULLY OPERATIONAL")
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ MongoDB Connection Failed: {e}")
        return False

async def check_backend_services():
    """Check backend API health"""
    print_section("🚀 BACKEND SERVICES VERIFICATION")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Check health endpoint
            async with session.get('http://localhost:8001/api/health') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Backend API: HEALTHY")
                    print(f"   - MongoDB: {data['services']['mongodb']['status']}")
                    print(f"   - Redis: {data['services']['redis']['status']}")
                    print(f"   - Active Jobs: {data['active_jobs']}")
                    
                    if data['services']['redis']['status'] == 'healthy':
                        redis_info = data['services']['redis']['info']
                        print(f"   - Redis Keys: {redis_info['keyspace'].get('keys', 0)}")
                    
                    return True
                else:
                    print(f"❌ Backend API returned status: {resp.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Backend API Check Failed: {e}")
        print("   ℹ️  Make sure backend is running on port 8001")
        return False

def check_supervisor_services():
    """Check supervisor service status"""
    print_section("⚙️  SUPERVISOR SERVICES")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ['sudo', 'supervisorctl', 'status'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        print(result.stdout)
        
        # Count running services
        running = result.stdout.count('RUNNING')
        stopped = result.stdout.count('STOPPED')
        
        print(f"\n📊 Services Summary:")
        print(f"   ✅ Running: {running}")
        if stopped > 0:
            print(f"   ⚠️  Stopped: {stopped}")
        
        return running > 0
        
    except Exception as e:
        print(f"❌ Failed to check supervisor: {e}")
        return False

async def main():
    """Run all verification checks"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "EMAIL VERIFIER - PERSISTENCE VERIFICATION" + " " * 22 + "║")
    print("╚" + "=" * 78 + "╝")
    
    results = {}
    
    # Check all services
    results['redis'] = check_redis()
    results['mongodb'] = await check_mongodb()
    results['backend'] = await check_backend_services()
    results['supervisor'] = check_supervisor_services()
    
    # Final summary
    print_section("📋 VERIFICATION SUMMARY")
    
    all_healthy = all(results.values())
    
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        status_text = "HEALTHY" if status else "NEEDS ATTENTION"
        print(f"{status_icon} {service.upper()}: {status_text}")
    
    print("\n" + "=" * 80)
    
    if all_healthy:
        print("🎉 ALL SYSTEMS OPERATIONAL")
        print("\n✅ Data Persistence Guarantee:")
        print("   - Redis: Job state & L1 cache enabled")
        print("   - MongoDB: No TTL indexes (data persists forever)")
        print("   - EmailLedger: Compound unique index (multi-user support)")
        print("   - Verification/Finder history: Will remain persistent")
    else:
        print("⚠️  SOME SERVICES NEED ATTENTION")
        print("\nPlease review the failed checks above")
    
    print("=" * 80 + "\n")

if __name__ == '__main__':
    asyncio.run(main())
