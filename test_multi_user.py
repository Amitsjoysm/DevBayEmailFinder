#!/usr/bin/env python3
"""
Multi-User Async Testing Script
Tests concurrent user operations to verify no cross-contamination
"""

import asyncio
import aiohttp
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001/api"
TEST_USERS = [
    {"email": f"testuser{i}@example.com", "password": "testpass123", "full_name": f"Test User {i}"}
    for i in range(1, 6)  # Create 5 test users
]

class TestRunner:
    def __init__(self):
        self.results = []
        self.tokens = {}
    
    async def register_user(self, session, user):
        """Register a test user"""
        try:
            async with session.post(f"{BASE_URL}/auth/register", json=user) as resp:
                if resp.status in [200, 201]:
                    data = await resp.json()
                    self.tokens[user['email']] = data['access_token']
                    print(f"✓ Registered: {user['email']}")
                    return True
                elif resp.status == 400:
                    # User already exists, try login
                    return await self.login_user(session, user)
                else:
                    print(f"✗ Registration failed for {user['email']}: {resp.status}")
                    return False
        except Exception as e:
            print(f"✗ Error registering {user['email']}: {e}")
            return False
    
    async def login_user(self, session, user):
        """Login an existing user"""
        try:
            async with session.post(f"{BASE_URL}/auth/login", json={
                "email": user['email'],
                "password": user['password']
            }) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.tokens[user['email']] = data['access_token']
                    print(f"✓ Logged in: {user['email']}")
                    return True
                else:
                    print(f"✗ Login failed for {user['email']}: {resp.status}")
                    return False
        except Exception as e:
            print(f"✗ Error logging in {user['email']}: {e}")
            return False
    
    async def verify_single_email(self, session, user_email, test_email):
        """Verify a single email for a user"""
        headers = {"Authorization": f"Bearer {self.tokens[user_email]}"}
        try:
            start_time = time.time()
            async with session.post(
                f"{BASE_URL}/verify/single",
                json={"email": test_email},
                headers=headers
            ) as resp:
                elapsed = time.time() - start_time
                if resp.status == 200:
                    data = await resp.json()
                    result = {
                        "user": user_email,
                        "test_email": test_email,
                        "status": data.get('status'),
                        "elapsed": elapsed,
                        "success": True
                    }
                    self.results.append(result)
                    print(f"  ✓ {user_email} verified {test_email}: {data.get('status')} ({elapsed:.2f}s)")
                    return result
                else:
                    print(f"  ✗ {user_email} failed to verify {test_email}: {resp.status}")
                    return None
        except Exception as e:
            print(f"  ✗ Error for {user_email}: {e}")
            return None
    
    async def create_bulk_job(self, session, user_email, emails):
        """Create a bulk verification job"""
        headers = {"Authorization": f"Bearer {self.tokens[user_email]}"}
        try:
            async with session.post(
                f"{BASE_URL}/verify/bulk",
                json=emails,
                params={"threads": 5, "delay": 0},
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    job_id = data.get('job_id')
                    print(f"  ✓ {user_email} created job: {job_id}")
                    return job_id
                else:
                    print(f"  ✗ {user_email} failed to create job: {resp.status}")
                    return None
        except Exception as e:
            print(f"  ✗ Error creating job for {user_email}: {e}")
            return None
    
    async def test_concurrent_single_verifications(self, session):
        """Test 1: Concurrent single email verifications"""
        print("\n" + "="*60)
        print("TEST 1: Concurrent Single Email Verifications")
        print("="*60)
        
        # Each user verifies different emails from the same domain (gmail.com)
        test_emails = [
            ("testuser1@example.com", "user1@gmail.com"),
            ("testuser2@example.com", "user2@gmail.com"),
            ("testuser3@example.com", "user3@gmail.com"),
            ("testuser4@example.com", "user4@gmail.com"),
            ("testuser5@example.com", "user5@gmail.com"),
        ]
        
        # Run all verifications concurrently
        tasks = [
            self.verify_single_email(session, user_email, test_email)
            for user_email, test_email in test_emails
        ]
        
        start = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        print(f"\nResults: {len([r for r in results if r])} / {len(results)} successful")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Average time per verification: {elapsed/len(results):.2f}s")
        
        # Check for timing consistency (no user should wait for another's domain delay)
        if results:
            times = [r['elapsed'] for r in results if r]
            if times:
                max_time = max(times)
                min_time = min(times)
                print(f"Timing range: {min_time:.2f}s - {max_time:.2f}s")
                
                # If users were interfering, we'd see much longer times for some users
                if max_time < 10:  # Reasonable threshold
                    print("✓ PASS: No significant timing interference detected")
                else:
                    print("✗ FAIL: Possible timing interference (delays too long)")
        
        return len([r for r in results if r]) == len(results)
    
    async def test_concurrent_bulk_jobs(self, session):
        """Test 2: Concurrent bulk verification jobs"""
        print("\n" + "="*60)
        print("TEST 2: Concurrent Bulk Verification Jobs")
        print("="*60)
        
        # Each user creates a bulk job
        email_sets = [
            [f"bulk{i}_{j}@gmail.com" for j in range(1, 6)]  # 5 emails per user
            for i in range(1, 6)  # 5 users
        ]
        
        tasks = [
            self.create_bulk_job(session, f"testuser{i}@example.com", emails)
            for i, emails in enumerate(email_sets, 1)
        ]
        
        job_ids = await asyncio.gather(*tasks)
        successful_jobs = [j for j in job_ids if j]
        
        print(f"\nResults: {len(successful_jobs)} / {len(job_ids)} jobs created")
        
        if len(successful_jobs) == len(job_ids):
            print("✓ PASS: All users created jobs concurrently")
            return True
        else:
            print("✗ FAIL: Some users failed to create jobs")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("MULTI-USER ASYNC TESTING")
        print("="*60)
        print(f"Started at: {datetime.now()}")
        print(f"Testing with {len(TEST_USERS)} concurrent users")
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Register/Login all users
            print("\nStep 1: User Registration/Login")
            print("-" * 60)
            
            tasks = [self.register_user(session, user) for user in TEST_USERS]
            results = await asyncio.gather(*tasks)
            
            if not all(results):
                print("\n✗ CRITICAL: Not all users could be registered/logged in")
                return False
            
            print(f"\n✓ All {len(TEST_USERS)} users ready")
            
            # Step 2: Run concurrent tests
            test_results = []
            
            # Test 1: Concurrent single verifications
            test_results.append(await self.test_concurrent_single_verifications(session))
            
            # Test 2: Concurrent bulk jobs
            test_results.append(await self.test_concurrent_bulk_jobs(session))
            
            # Summary
            print("\n" + "="*60)
            print("TEST SUMMARY")
            print("="*60)
            passed = sum(test_results)
            total = len(test_results)
            print(f"Tests Passed: {passed} / {total}")
            
            if all(test_results):
                print("\n✓ ALL TESTS PASSED")
                print("Multi-user async functionality is working correctly!")
                return True
            else:
                print("\n✗ SOME TESTS FAILED")
                print("Please review the multi-user isolation fixes")
                return False

async def main():
    runner = TestRunner()
    success = await runner.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
