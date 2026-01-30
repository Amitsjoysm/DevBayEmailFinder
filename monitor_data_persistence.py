#!/usr/bin/env python3
"""
Data Persistence Monitor
Run this script to check if verification/finder history and ledger data are being properly retained.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

# Load environment
backend_dir = Path(__file__).parent / 'backend'
load_dotenv(backend_dir / '.env')

async def monitor_data_persistence():
    """Monitor data persistence across all collections"""
    
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'test_database')
    
    print("=" * 80)
    print("📊 EMAIL VERIFIER - DATA PERSISTENCE MONITOR")
    print("=" * 80)
    print(f"Database: {db_name}")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    try:
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Check connection
        await client.admin.command('ping')
        print("✅ MongoDB connection: HEALTHY")
        print()
        
        # Collections to monitor
        collections = {
            'verification_jobs': 'Verification/Finder Jobs',
            'verification_results': 'Verification Results',
            'finder_results': 'Finder Results',
            'email_ledger': 'Email Ledger (Unified History)',
            'users': 'Users',
            'user_settings': 'User Settings',
            'domain_pattern_cache': 'Domain Pattern Cache'
        }
        
        print("📦 COLLECTION STATUS:")
        print("-" * 80)
        
        total_documents = 0
        empty_collections = []
        
        for coll_name, display_name in collections.items():
            try:
                count = await db[coll_name].count_documents({})
                total_documents += count
                
                status = "✅" if count > 0 else "⚠️ "
                print(f"{status} {display_name:40} {count:>8} documents")
                
                if count == 0 and coll_name not in ['users', 'user_settings', 'domain_pattern_cache']:
                    empty_collections.append(display_name)
                
                # Get sample data for non-empty collections
                if count > 0 and coll_name in ['verification_jobs', 'verification_results', 'finder_results', 'email_ledger']:
                    # Get oldest and newest records
                    date_field = 'created_at' if coll_name == 'verification_jobs' else 'verified_at'
                    if coll_name == 'email_ledger':
                        date_field = 'last_verified_at'
                    
                    oldest = await db[coll_name].find_one(
                        {},
                        sort=[(date_field, 1)]
                    )
                    
                    newest = await db[coll_name].find_one(
                        {},
                        sort=[(date_field, -1)]
                    )
                    
                    if oldest and newest:
                        oldest_date = oldest.get(date_field)
                        newest_date = newest.get(date_field)
                        
                        if isinstance(oldest_date, str):
                            oldest_date = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
                        if isinstance(newest_date, str):
                            newest_date = datetime.fromisoformat(newest_date.replace('Z', '+00:00'))
                        
                        if oldest_date and newest_date:
                            age_days = (datetime.now(timezone.utc) - oldest_date).days
                            retention_days = (newest_date - oldest_date).days
                            
                            print(f"     └─ Oldest: {oldest_date.strftime('%Y-%m-%d %H:%M')} ({age_days} days old)")
                            print(f"     └─ Newest: {newest_date.strftime('%Y-%m-%d %H:%M')}")
                            print(f"     └─ Retention span: {retention_days} days")
                
            except Exception as e:
                print(f"❌ {display_name:40} ERROR: {e}")
        
        print()
        print(f"📊 TOTAL DOCUMENTS: {total_documents}")
        
        # Check indexes on email_ledger
        print()
        print("🔍 EMAIL LEDGER INDEX STATUS:")
        print("-" * 80)
        
        indexes = await db.email_ledger.index_information()
        
        has_compound_unique = False
        has_ttl = False
        
        for idx_name, idx_info in indexes.items():
            keys_str = ', '.join([f"{k[0]}:{k[1]}" for k in idx_info.get('key', [])])
            unique_str = " [UNIQUE]" if idx_info.get('unique') else ""
            ttl_str = ""
            
            if 'expireAfterSeconds' in idx_info:
                has_ttl = True
                ttl_hours = idx_info['expireAfterSeconds'] / 3600
                ttl_str = f" [TTL: {ttl_hours}h ⚠️  AUTO-DELETE]"
            
            print(f"  {idx_name}: {keys_str}{unique_str}{ttl_str}")
            
            if idx_name == 'email_user_unique':
                has_compound_unique = True
        
        print()
        if has_compound_unique:
            print("✅ Compound unique index (email, user_id) is properly configured")
        else:
            print("❌ WARNING: Compound unique index NOT found - multi-user data conflicts possible!")
        
        if has_ttl:
            print("⚠️  WARNING: TTL index found - data will be AUTO-DELETED!")
        else:
            print("✅ No TTL indexes - data will persist indefinitely")
        
        # Warnings and recommendations
        print()
        print("📋 STATUS SUMMARY:")
        print("-" * 80)
        
        if total_documents == 0:
            print("⚠️  All collections are empty - no data has been saved yet")
            print("   Recommendation: Run some verification/finder jobs to test persistence")
        elif empty_collections:
            print("⚠️  Some collections are empty:")
            for coll in empty_collections:
                print(f"   - {coll}")
        else:
            print("✅ Data is being saved successfully")
        
        # Check for data loss patterns
        jobs_count = await db.verification_jobs.count_documents({})
        results_count = await db.verification_results.count_documents({})
        finder_results_count = await db.finder_results.count_documents({})
        ledger_count = await db.email_ledger.count_documents({})
        
        print()
        if jobs_count > 0 and results_count == 0 and finder_results_count == 0:
            print("🚨 CRITICAL: Jobs exist but NO results found!")
            print("   This indicates data is being deleted or not saved properly")
        elif results_count > 0 and ledger_count == 0:
            print("⚠️  WARNING: Results exist but ledger is empty")
            print("   Ledger may not be working correctly")
        else:
            print("✅ No suspicious data loss patterns detected")
        
        # Check Redis status
        print()
        print("🔴 REDIS STATUS:")
        print("-" * 80)
        try:
            import redis
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url)
            r.ping()
            print("✅ Redis is running and accessible")
            
            # Get Redis info
            info = r.info()
            print(f"   Redis version: {info.get('redis_version')}")
            print(f"   Used memory: {info.get('used_memory_human')}")
            
            # Check for active jobs
            active_jobs = r.smembers('active_jobs')
            print(f"   Active jobs in Redis: {len(active_jobs)}")
            
        except Exception as e:
            print(f"❌ Redis not available: {e}")
            print("   Job state persistence limited to MongoDB only")
            print("   Recommendation: Install Redis for better reliability")
        
        print()
        print("=" * 80)
        print("Monitor complete. Re-run this script periodically to verify data persistence.")
        print("=" * 80)
        
        client.close()
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(monitor_data_persistence())
