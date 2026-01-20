#!/usr/bin/env python3
"""
Test script for domain pattern caching functionality
Tests Phase 1: first.last@domain pattern priority
Tests Phase 2: persistent domain pattern caching
"""

import requests
import json
import time

BASE_URL = "http://localhost:8001/api"

def register_and_login():
    """Register/login to get auth token"""
    email = f"test_cache_{int(time.time())}@example.com"
    password = "TestPassword123!"
    
    # Register
    register_data = {
        "email": email,
        "password": password,
        "full_name": "Cache Test User"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        if response.status_code != 201:
            # Try login instead
            login_data = {"email": "test@example.com", "password": "password123"}
            response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
            if response.status_code != 200:
                print(f"❌ Login failed: {response.status_code}")
                return None
        
        data = response.json()
        token = data['access_token']
        print(f"✅ Authenticated as: {data['user']['email']}")
        return token
    except Exception as e:
        print(f"❌ Auth error: {e}")
        return None

def test_finder_with_cache(token):
    """Test email finder with first.last@domain pattern"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n" + "="*80)
    print("TEST 1: Finding email with first.last@domain pattern")
    print("="*80)
    
    # Test finding an email (this will test pattern priority)
    finder_data = {
        "first_name": "John",
        "last_name": "Doe",
        "domain": "example.com"
    }
    
    print(f"\n🔍 Searching for: {finder_data['first_name']} {finder_data['last_name']} @ {finder_data['domain']}")
    
    try:
        response = requests.post(f"{BASE_URL}/find/single", json=finder_data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n📊 Result:")
            print(f"   Found: {result.get('found')}")
            print(f"   Email: {result.get('email')}")
            print(f"   Pattern: {result.get('found_pattern')}")
            print(f"   Patterns Tested: {result.get('patterns_tested')}")
            print(f"   Search Time: {result.get('search_time', 0):.2f}s")
            print(f"   Deliverability Score: {result.get('deliverability_score', 0)}")
            
            if result.get('found_pattern') == '{first}.{last}@{domain}':
                print(f"\n✅ SUCCESS: first.last@domain pattern confirmed!")
            else:
                print(f"\n⚠️  Different pattern used: {result.get('found_pattern')}")
            
            return result.get('domain')
        else:
            print(f"❌ Finder request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Finder error: {e}")
        return None

def test_domain_cache_stats(token, domain=None):
    """Test domain cache statistics endpoint"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n" + "="*80)
    print("TEST 2: Domain Cache Statistics")
    print("="*80)
    
    try:
        if domain:
            print(f"\n📊 Getting stats for domain: {domain}")
            response = requests.get(f"{BASE_URL}/domain-cache/stats?domain={domain}", headers=headers)
        else:
            print(f"\n📊 Getting overall cache statistics")
            response = requests.get(f"{BASE_URL}/domain-cache/stats", headers=headers)
        
        if response.status_code == 200:
            stats = response.json()
            print(f"\n✅ Cache Stats:")
            print(json.dumps(stats, indent=2))
            return stats
        else:
            print(f"❌ Stats request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return None

def test_domain_cache_lookup(token, domain):
    """Test domain cache lookup endpoint"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n" + "="*80)
    print(f"TEST 3: Domain Cache Lookup for {domain}")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/domain-cache/{domain}", headers=headers)
        
        if response.status_code == 200:
            cache_entry = response.json()
            print(f"\n✅ Cached Pattern Found:")
            print(json.dumps(cache_entry, indent=2))
            return cache_entry
        elif response.status_code == 404:
            print(f"\n⚠️  No cached pattern for {domain} (this is expected for first run)")
            return None
        else:
            print(f"❌ Lookup failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Lookup error: {e}")
        return None

def test_search_cache(token):
    """Test searching domain cache"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n" + "="*80)
    print("TEST 4: Search Domain Cache")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/domain-cache/search?limit=10", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"\n✅ Found {len(results)} cached domains:")
            for entry in results[:5]:  # Show first 5
                print(f"   - {entry.get('domain')}: {entry.get('pattern')} (successes: {entry.get('success_count')})")
            return results
        else:
            print(f"❌ Search failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Search error: {e}")
        return None

def main():
    """Run all tests"""
    print("="*80)
    print("🚀 DOMAIN PATTERN CACHE TESTING")
    print("="*80)
    
    # Authenticate
    token = register_and_login()
    if not token:
        print("\n❌ Cannot proceed without authentication")
        return
    
    # Test 1: Find email (tests pattern priority)
    domain = test_finder_with_cache(token)
    
    # Wait a moment for cache to be saved
    time.sleep(2)
    
    # Test 2: Get overall cache stats
    test_domain_cache_stats(token)
    
    # Test 3: Get specific domain cache (if we found one)
    if domain:
        test_domain_cache_lookup(token, domain)
        test_domain_cache_stats(token, domain)
    
    # Test 4: Search cache
    test_search_cache(token)
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80)
    print("\nNext Steps:")
    print("1. Check backend logs for detailed pattern testing: tail -f /var/log/supervisor/backend.out.log")
    print("2. Run finder again on same domain to see cache hit")
    print("3. View cache stats in the app UI (if implemented)")

if __name__ == "__main__":
    main()
