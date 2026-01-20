#!/usr/bin/env python3
"""
Critical Fixes Testing for Email Verification Tool
Tests the specific fixes mentioned in the review request:
1. Settings Endpoint ObjectId Fix
2. Email Verification Status Logic
3. Redis Connectivity
4. All Previous Functionality Still Working
"""

import requests
import json
import csv
import io
import time
import redis
from datetime import datetime
from typing import Dict, List, Optional

# Configuration
BASE_URL = "http://localhost:8001/api"
TEST_USER_EMAIL = "sarah.johnson@example.com"
TEST_USER_PASSWORD = "securepass456"
TEST_USER_NAME = "Sarah Johnson"

class CriticalFixesTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.user_id = None
        self.headers = {"Content-Type": "application/json"}
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str, response_data: dict = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name} - {message}")
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2)}")
    
    def make_request(self, method: str, endpoint: str, data: dict = None, files: dict = None, params: dict = None) -> tuple:
        """Make HTTP request with proper headers"""
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                if files:
                    # Remove Content-Type for file uploads
                    headers.pop("Content-Type", None)
                    response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                else:
                    response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response.status_code, response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            return 500, {"error": str(e)}
        except json.JSONDecodeError:
            return response.status_code, {"error": "Invalid JSON response"}
    
    def set_auth_token(self, token: str):
        """Set JWT token for authenticated requests"""
        self.token = token
        self.headers["Authorization"] = f"Bearer {token}"
    
    def authenticate(self):
        """Authenticate and get token"""
        print("\n=== AUTHENTICATING ===")
        
        # Try login first
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        
        status, response = self.make_request("POST", "/auth/login", login_data)
        
        if status == 200:
            self.log_test("Authentication", True, "Login successful")
            self.set_auth_token(response["access_token"])
            self.user_id = response["user"]["id"]
            return True
        elif status == 401:
            # Try registration
            register_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "full_name": TEST_USER_NAME
            }
            
            status, response = self.make_request("POST", "/auth/register", register_data)
            
            if status == 200 or status == 201:
                self.log_test("Authentication", True, "Registration successful")
                self.set_auth_token(response["access_token"])
                self.user_id = response["user"]["id"]
                return True
            else:
                self.log_test("Authentication", False, f"Registration failed: {response}", response)
                return False
        else:
            self.log_test("Authentication", False, f"Login failed: {response}", response)
            return False
    
    def test_settings_endpoint_objectid_fix(self):
        """Test Settings Endpoint ObjectId Fix"""
        print("\n=== TESTING SETTINGS ENDPOINT OBJECTID FIX ===")
        
        # Test 1: GET /api/settings endpoint (requires authentication)
        status, response = self.make_request("GET", "/settings")
        
        if status == 200:
            # Verify response is valid JSON without ObjectId serialization errors
            if isinstance(response, dict):
                # Check that _id field is not present
                if "_id" not in response:
                    self.log_test("Settings ObjectId Fix", True, 
                                "Settings endpoint returns clean JSON without _id field")
                else:
                    self.log_test("Settings ObjectId Fix", False, 
                                "Settings response contains _id field", response)
                
                # Verify it's a proper settings object
                expected_fields = ["user_id", "threads", "global_delay"]
                has_expected = any(field in response for field in expected_fields)
                
                if has_expected:
                    self.log_test("Settings Structure", True, 
                                f"Settings object has expected structure: {list(response.keys())}")
                else:
                    self.log_test("Settings Structure", False, 
                                f"Settings object missing expected fields: {response}")
            else:
                self.log_test("Settings ObjectId Fix", False, 
                            f"Settings response is not a dict: {type(response)}", response)
        else:
            self.log_test("Settings ObjectId Fix", False, 
                        f"Settings endpoint failed with status {status}: {response}", response)
        
        # Test 2: Test when settings don't exist (creating new settings)
        # This tests the scenario where insert_one() adds _id field
        print("Testing settings creation scenario...")
        
        # Try to update settings to trigger creation path
        new_settings = {
            "threads": 20,
            "global_delay": 3,
            "use_proxies": False
        }
        
        status, response = self.make_request("PUT", "/settings", new_settings)
        
        if status == 200:
            if "_id" not in response:
                self.log_test("Settings Creation ObjectId Fix", True, 
                            "Settings creation returns clean JSON without _id")
            else:
                self.log_test("Settings Creation ObjectId Fix", False, 
                            "Settings creation response contains _id field", response)
        else:
            self.log_test("Settings Creation ObjectId Fix", False, 
                        f"Settings update failed: {response}", response)
    
    def test_email_verification_status_logic(self):
        """Test Email Verification Status Logic with specific test emails"""
        print("\n=== TESTING EMAIL VERIFICATION STATUS LOGIC ===")
        
        # Test emails from the review request
        test_emails = [
            {
                "email": "amits.joys@gmail.com",
                "expected_status": "valid",
                "expected_score_range": (95, 100),
                "description": "Gmail address - should be VALID with high score"
            },
            {
                "email": "amit@marketjoy.com", 
                "expected_status": "valid",
                "expected_score_range": (95, 100),
                "description": "Custom domain - should be VALID, NOT unknown"
            },
            {
                "email": "sandip@saleszip.com",
                "expected_status": "valid", 
                "expected_score_range": (95, 100),
                "description": "Custom domain - should be VALID, NOT unknown"
            },
            {
                "email": "abb@mj.com",
                "expected_status": "invalid",
                "expected_score_range": (0, 10),
                "description": "Invalid domain - should be INVALID with low score"
            }
        ]
        
        for test_case in test_emails:
            email = test_case["email"]
            expected_status = test_case["expected_status"]
            expected_score_min, expected_score_max = test_case["expected_score_range"]
            description = test_case["description"]
            
            print(f"\nTesting: {email} - {description}")
            
            # Test single email verification
            data = {"email": email}
            status, response = self.make_request("POST", "/verify/single", data)
            
            if status == 200:
                actual_status = response.get("status", "").lower()
                deliverability_score = response.get("deliverability_score", 0)
                
                # Check status matches expected
                status_correct = actual_status == expected_status
                
                # Check deliverability score is in expected range
                score_correct = expected_score_min <= deliverability_score <= expected_score_max
                
                # Check that status matches deliverability score logic
                if deliverability_score >= 80:
                    score_status_match = actual_status == "valid"
                elif deliverability_score >= 60:
                    score_status_match = actual_status in ["valid", "risky"]
                elif deliverability_score >= 40:
                    score_status_match = actual_status in ["risky", "unknown"]
                else:
                    score_status_match = actual_status == "invalid"
                
                if status_correct and score_correct and score_status_match:
                    self.log_test(f"Verification Logic - {email}", True,
                                f"Status: {actual_status}, Score: {deliverability_score} (Expected: {expected_status}, {expected_score_min}-{expected_score_max})")
                else:
                    issues = []
                    if not status_correct:
                        issues.append(f"status {actual_status} != {expected_status}")
                    if not score_correct:
                        issues.append(f"score {deliverability_score} not in {expected_score_min}-{expected_score_max}")
                    if not score_status_match:
                        issues.append(f"status {actual_status} doesn't match score {deliverability_score}")
                    
                    self.log_test(f"Verification Logic - {email}", False,
                                f"Issues: {', '.join(issues)}", response)
                
                # Verify deliverability_score field is populated
                if "deliverability_score" in response:
                    self.log_test(f"Deliverability Score Present - {email}", True,
                                f"Score field present: {deliverability_score}")
                else:
                    self.log_test(f"Deliverability Score Present - {email}", False,
                                "deliverability_score field missing", response)
            else:
                self.log_test(f"Verification Logic - {email}", False,
                            f"Verification failed with status {status}: {response}", response)
    
    def test_bulk_email_verification_status(self):
        """Test bulk email verification with the specific test emails"""
        print("\n=== TESTING BULK EMAIL VERIFICATION STATUS ===")
        
        # Create CSV with test emails
        test_emails_csv = """email
amits.joys@gmail.com
amit@marketjoy.com
sandip@saleszip.com
abb@mj.com"""
        
        files = {
            'file': ('test_verification_status.csv', test_emails_csv, 'text/csv')
        }
        
        data = {
            'threads': '2',
            'delay': '1'
        }
        
        status, response = self.make_request("POST", "/verify/upload", data, files=files)
        
        if status == 200:
            job_id = response.get("job_id")
            self.log_test("Bulk Verification Status Test", True,
                        f"Bulk job created: {job_id}, Records: {response.get('total_records')}")
            
            # Wait for job completion
            max_wait = 60  # seconds
            wait_time = 0
            
            while wait_time < max_wait:
                time.sleep(3)
                wait_time += 3
                
                job_status, job_response = self.make_request("GET", f"/jobs/{job_id}")
                if job_status == 200:
                    job_state = job_response.get("status")
                    processed = job_response.get("processed_records", 0)
                    total = job_response.get("total_records", 0)
                    
                    print(f"Job progress: {processed}/{total} ({job_state})")
                    
                    if job_state in ["completed", "failed", "stopped"]:
                        break
            
            # Get results and verify status logic
            results_status, results_response = self.make_request("GET", f"/results/{job_id}")
            
            if results_status == 200:
                results = results_response.get("results", [])
                
                # Check each result
                expected_results = {
                    "amits.joys@gmail.com": {"status": "valid", "score_min": 95},
                    "amit@marketjoy.com": {"status": "valid", "score_min": 95},
                    "sandip@saleszip.com": {"status": "valid", "score_min": 95},
                    "abb@mj.com": {"status": "invalid", "score_max": 10}
                }
                
                for result in results:
                    email = result.get("email")
                    status = result.get("status", "").lower()
                    score = result.get("deliverability_score", 0)
                    
                    if email in expected_results:
                        expected = expected_results[email]
                        expected_status = expected["status"]
                        
                        # Check status
                        status_ok = status == expected_status
                        
                        # Check score range
                        score_ok = True
                        if "score_min" in expected:
                            score_ok = score >= expected["score_min"]
                        elif "score_max" in expected:
                            score_ok = score <= expected["score_max"]
                        
                        # Check no high-score emails have status="unknown"
                        no_unknown_high_score = not (score > 80 and status == "unknown")
                        
                        if status_ok and score_ok and no_unknown_high_score:
                            self.log_test(f"Bulk Result - {email}", True,
                                        f"Status: {status}, Score: {score}")
                        else:
                            issues = []
                            if not status_ok:
                                issues.append(f"status {status} != {expected_status}")
                            if not score_ok:
                                issues.append(f"score {score} out of range")
                            if not no_unknown_high_score:
                                issues.append(f"high score {score} with unknown status")
                            
                            self.log_test(f"Bulk Result - {email}", False,
                                        f"Issues: {', '.join(issues)}", result)
                
                # Overall check: no emails with score >80 should have status="unknown"
                high_score_unknown = [r for r in results 
                                    if r.get("deliverability_score", 0) > 80 
                                    and r.get("status", "").lower() == "unknown"]
                
                if not high_score_unknown:
                    self.log_test("No High-Score Unknown Status", True,
                                "No emails with score >80 have status='unknown'")
                else:
                    self.log_test("No High-Score Unknown Status", False,
                                f"Found {len(high_score_unknown)} high-score emails with unknown status",
                                high_score_unknown)
            else:
                self.log_test("Bulk Results Retrieval", False,
                            f"Failed to get bulk results: {results_response}", results_response)
        else:
            self.log_test("Bulk Verification Status Test", False,
                        f"Failed to create bulk job: {response}", response)
    
    def test_redis_connectivity(self):
        """Test Redis Connectivity"""
        print("\n=== TESTING REDIS CONNECTIVITY ===")
        
        # Test 1: Direct Redis connection
        try:
            redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            redis_client.ping()
            self.log_test("Redis Direct Connection", True, "Redis is accessible at localhost:6379")
        except Exception as e:
            self.log_test("Redis Direct Connection", False, f"Redis connection failed: {e}")
        
        # Test 2: Backend Redis connectivity via health endpoint
        status, response = self.make_request("GET", "/health")
        
        if status == 200:
            redis_status = response.get("services", {}).get("redis", {})
            redis_health = redis_status.get("status", "unknown")
            
            if redis_health == "healthy":
                self.log_test("Backend Redis Connection", True, "Backend reports Redis as healthy")
            else:
                self.log_test("Backend Redis Connection", False, 
                            f"Backend Redis status: {redis_health}", redis_status)
        else:
            self.log_test("Backend Redis Connection", False, 
                        f"Health endpoint failed: {response}", response)
        
        # Test 3: Check if Socket.IO is using Redis adapter
        # This would be visible in backend logs, but we can test indirectly
        # by checking if Redis stats endpoint works
        status, response = self.make_request("GET", "/redis/stats")
        
        if status == 200:
            self.log_test("Socket.IO Redis Adapter", True, 
                        "Redis stats endpoint accessible - Redis adapter likely active")
        elif status == 503:
            self.log_test("Socket.IO Redis Adapter", False, 
                        "Redis not available for Socket.IO", response)
        else:
            self.log_test("Socket.IO Redis Adapter", False, 
                        f"Redis stats failed: {response}", response)
    
    def test_all_previous_functionality(self):
        """Test that all previous functionality still works"""
        print("\n=== TESTING ALL PREVIOUS FUNCTIONALITY ===")
        
        # Test 1: Single email verification still works
        status, response = self.make_request("POST", "/verify/single", {"email": "test@gmail.com"})
        
        if status == 200:
            self.log_test("Single Email Verification", True, 
                        f"Single verification works: {response.get('status')}")
        else:
            self.log_test("Single Email Verification", False, 
                        f"Single verification failed: {response}", response)
        
        # Test 2: Single email finder still works
        finder_data = {
            "first_name": "John",
            "last_name": "Doe", 
            "domain": "google.com"
        }
        
        status, response = self.make_request("POST", "/find/single", finder_data)
        
        if status == 200:
            self.log_test("Single Email Finder", True, 
                        f"Single finder works: found={response.get('found')}")
        else:
            self.log_test("Single Email Finder", False, 
                        f"Single finder failed: {response}", response)
        
        # Test 3: Job management endpoints work
        # First create a small job
        test_emails = ["test1@gmail.com", "test2@outlook.com"]
        status, response = self.make_request("POST", "/verify/bulk", test_emails)
        
        if status == 200:
            job_id = response.get("job_id")
            
            # Test pause
            status, response = self.make_request("POST", f"/jobs/{job_id}/pause")
            if status == 200:
                self.log_test("Job Pause", True, "Job pause works")
            else:
                self.log_test("Job Pause", False, f"Job pause failed: {response}", response)
            
            # Test resume
            status, response = self.make_request("POST", f"/jobs/{job_id}/resume")
            if status == 200:
                self.log_test("Job Resume", True, "Job resume works")
            else:
                self.log_test("Job Resume", False, f"Job resume failed: {response}", response)
            
            # Test stop
            status, response = self.make_request("POST", f"/jobs/{job_id}/stop")
            if status == 200:
                self.log_test("Job Stop", True, "Job stop works")
            else:
                self.log_test("Job Stop", False, f"Job stop failed: {response}", response)
        else:
            self.log_test("Job Management Setup", False, 
                        f"Failed to create test job: {response}", response)
        
        # Test 4: Results export (CSV/JSON) works
        # Get any existing job
        status, response = self.make_request("GET", "/jobs")
        
        if status == 200 and response:
            jobs = response if isinstance(response, list) else []
            if jobs:
                test_job_id = jobs[0].get("id")
                
                # Test JSON export
                status, response = self.make_request("GET", f"/results/{test_job_id}/export", 
                                                   params={"format": "json"})
                
                if status == 200:
                    self.log_test("Results Export JSON", True, "JSON export works")
                else:
                    self.log_test("Results Export JSON", False, 
                                f"JSON export failed: {response}", response)
                
                # Test CSV export
                try:
                    url = f"{self.base_url}/results/{test_job_id}/export"
                    headers = self.headers.copy()
                    csv_response = requests.get(url, headers=headers, 
                                              params={"format": "csv"}, timeout=30)
                    
                    if csv_response.status_code == 200:
                        self.log_test("Results Export CSV", True, "CSV export works")
                    else:
                        self.log_test("Results Export CSV", False, 
                                    f"CSV export failed: {csv_response.status_code}")
                except Exception as e:
                    self.log_test("Results Export CSV", False, f"CSV export error: {e}")
            else:
                self.log_test("Results Export Test", False, "No jobs available for export test")
        else:
            self.log_test("Results Export Test", False, "Failed to get jobs list for export test")
    
    def run_critical_fixes_test(self):
        """Run all critical fixes tests"""
        print("🚀 Starting Critical Fixes Testing")
        print(f"🔗 Testing against: {self.base_url}")
        
        # Step 1: Authentication
        if not self.authenticate():
            print("❌ Authentication failed - stopping tests")
            return
        
        # Step 2: Test Settings Endpoint ObjectId Fix
        self.test_settings_endpoint_objectid_fix()
        
        # Step 3: Test Email Verification Status Logic
        self.test_email_verification_status_logic()
        
        # Step 4: Test Bulk Email Verification Status
        self.test_bulk_email_verification_status()
        
        # Step 5: Test Redis Connectivity
        self.test_redis_connectivity()
        
        # Step 6: Test All Previous Functionality Still Working
        self.test_all_previous_functionality()
        
        # Summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "="*60)
        print("📊 CRITICAL FIXES TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Group results by category
        categories = {
            "Settings ObjectId Fix": [],
            "Email Verification Status": [],
            "Redis Connectivity": [],
            "Previous Functionality": [],
            "Other": []
        }
        
        for result in self.test_results:
            test_name = result["test"]
            if "Settings" in test_name and "ObjectId" in test_name:
                categories["Settings ObjectId Fix"].append(result)
            elif "Verification Logic" in test_name or "Bulk Result" in test_name or "High-Score" in test_name:
                categories["Email Verification Status"].append(result)
            elif "Redis" in test_name or "Socket.IO" in test_name:
                categories["Redis Connectivity"].append(result)
            elif any(x in test_name for x in ["Single Email", "Job", "Export"]):
                categories["Previous Functionality"].append(result)
            else:
                categories["Other"].append(result)
        
        for category, results in categories.items():
            if results:
                passed = sum(1 for r in results if r["success"])
                total = len(results)
                print(f"\n{category}: {passed}/{total} passed")
                
                for result in results:
                    status = "✅" if result["success"] else "❌"
                    print(f"   {status} {result['test']}: {result['message']}")
        
        print("\n" + "="*60)

if __name__ == "__main__":
    tester = CriticalFixesTester()
    tester.run_critical_fixes_test()