#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Email Verification and Finder Tool
Tests all authentication and API endpoints with JWT Bearer token authentication
"""

import requests
import json
import csv
import io
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

# Configuration
BASE_URL = "https://sync-app-restart.preview.emergentagent.com/api"
TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = "testpassword123"
TEST_USER_NAME = "Test User"

class EmailVerificationTester:
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
    
    def test_authentication_flow(self):
        """Test complete authentication flow"""
        print("\n=== TESTING AUTHENTICATION FLOW ===")
        
        # Test 1: Register new user
        register_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        }
        
        status, response = self.make_request("POST", "/auth/register", register_data)
        
        if status == 200 or status == 201:
            self.log_test("User Registration", True, "User registered successfully")
            self.set_auth_token(response["access_token"])
            self.user_id = response["user"]["id"]
        elif status == 400 and "already registered" in response.get("detail", ""):
            # User already exists, try login
            self.log_test("User Registration", True, "User already exists, proceeding to login")
            
            # Test 2: Login with existing user
            login_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
            
            status, response = self.make_request("POST", "/auth/login", login_data)
            
            if status == 200:
                self.log_test("User Login", True, "Login successful")
                self.set_auth_token(response["access_token"])
                self.user_id = response["user"]["id"]
            else:
                self.log_test("User Login", False, f"Login failed: {response}", response)
                return False
        else:
            self.log_test("User Registration", False, f"Registration failed: {response}", response)
            return False
        
        # Test 3: Verify token works with /auth/me
        status, response = self.make_request("GET", "/auth/me")
        
        if status == 200:
            self.log_test("Token Verification", True, f"Token valid, user: {response['email']}")
        else:
            self.log_test("Token Verification", False, f"Token verification failed: {response}", response)
            return False
        
        # Test 4: Test unauthorized access (without token)
        temp_headers = self.headers.copy()
        self.headers.pop("Authorization", None)
        
        status, response = self.make_request("GET", "/auth/me")
        
        if status == 401:
            self.log_test("Unauthorized Access Test", True, "Correctly returned 401 without token")
        else:
            self.log_test("Unauthorized Access Test", False, f"Should return 401, got {status}: {response}", response)
        
        # Restore headers
        self.headers = temp_headers
        
        return True
    
    def test_single_email_verification(self):
        """Test single email verification endpoint"""
        print("\n=== TESTING SINGLE EMAIL VERIFICATION ===")
        
        test_emails = [
            ("test@gmail.com", "Gmail address"),
            ("user@outlook.com", "Outlook address"),
            ("invalid@nonexistentdomain12345.com", "Invalid domain"),
            ("notanemail", "Invalid email format")
        ]
        
        for email, description in test_emails:
            data = {"email": email}
            status, response = self.make_request("POST", "/verify/single", data)
            
            if status == 200:
                self.log_test(f"Single Verification - {description}", True, 
                            f"Verified {email}: {response.get('status', 'unknown')}")
            elif status == 422 and "invalid" in email:
                self.log_test(f"Single Verification - {description}", True, 
                            f"Correctly rejected invalid email: {email}")
            else:
                self.log_test(f"Single Verification - {description}", False, 
                            f"Verification failed for {email}: {response}", response)
    
    def test_bulk_email_verification(self):
        """Test bulk email verification endpoint"""
        print("\n=== TESTING BULK EMAIL VERIFICATION ===")
        
        # Test with small batch
        test_emails = [
            "john.doe@gmail.com",
            "jane.smith@outlook.com", 
            "test.user@yahoo.com",
            "admin@company.com",
            "invalid@nonexistent123.com"
        ]
        
        status, response = self.make_request("POST", "/verify/bulk", test_emails)
        
        if status == 200:
            job_id = response.get("job_id")
            self.log_test("Bulk Verification Start", True, 
                        f"Job created: {job_id}, Total: {response.get('total_records')}")
            
            # Wait and check job status
            time.sleep(2)
            return self.check_job_status(job_id, "verification")
        else:
            self.log_test("Bulk Verification Start", False, 
                        f"Failed to start bulk verification: {response}", response)
            return None
    
    def test_csv_upload_verification(self):
        """Test CSV upload verification endpoint"""
        print("\n=== TESTING CSV UPLOAD VERIFICATION ===")
        
        # Create test CSV
        csv_data = "email\ntest1@gmail.com\ntest2@outlook.com\ntest3@yahoo.com\ninvalid@fake123.com\nuser@company.org"
        csv_file = io.StringIO(csv_data)
        
        files = {
            'file': ('test_emails.csv', csv_file.getvalue(), 'text/csv')
        }
        
        data = {
            'threads': '5',
            'delay': '1'
        }
        
        status, response = self.make_request("POST", "/verify/upload", data, files=files)
        
        if status == 200:
            job_id = response.get("job_id")
            self.log_test("CSV Upload Verification", True, 
                        f"CSV uploaded, Job: {job_id}, Records: {response.get('total_records')}")
            
            # Wait and check job status
            time.sleep(2)
            return self.check_job_status(job_id, "verification")
        else:
            self.log_test("CSV Upload Verification", False, 
                        f"CSV upload failed: {response}", response)
            return None
    
    def test_single_email_finder(self):
        """Test single email finder endpoint"""
        print("\n=== TESTING SINGLE EMAIL FINDER ===")
        
        test_cases = [
            {"first_name": "John", "last_name": "Smith", "domain": "google.com", "desc": "Common name at Google"},
            {"first_name": "Jane", "last_name": "Doe", "domain": "microsoft.com", "desc": "Common name at Microsoft"},
            {"first_name": "Test", "last_name": "User", "domain": "nonexistent123.com", "desc": "Invalid domain"}
        ]
        
        for case in test_cases:
            data = {
                "first_name": case["first_name"],
                "last_name": case["last_name"], 
                "domain": case["domain"]
            }
            
            status, response = self.make_request("POST", "/find/single", data)
            
            if status == 200:
                found = response.get("found", False)
                patterns_tested = response.get("patterns_tested", 0)
                self.log_test(f"Single Finder - {case['desc']}", True, 
                            f"Found: {found}, Patterns tested: {patterns_tested}")
            else:
                self.log_test(f"Single Finder - {case['desc']}", False, 
                            f"Finder failed: {response}", response)
    
    def test_bulk_email_finder(self):
        """Test bulk email finder endpoint"""
        print("\n=== TESTING BULK EMAIL FINDER ===")
        
        # Create test CSV for finder
        csv_data = "first_name,last_name,domain\nJohn,Smith,google.com\nJane,Doe,microsoft.com\nTest,User,github.com\nAdmin,User,stackoverflow.com"
        csv_file = io.StringIO(csv_data)
        
        files = {
            'file': ('test_finder.csv', csv_file.getvalue(), 'text/csv')
        }
        
        data = {
            'threads': '3'
        }
        
        status, response = self.make_request("POST", "/find/upload", data, files=files)
        
        if status == 200:
            job_id = response.get("job_id")
            self.log_test("Bulk Finder Upload", True, 
                        f"Finder job created: {job_id}, Records: {response.get('total_records')}")
            
            # Wait and check job status
            time.sleep(3)
            return self.check_job_status(job_id, "finder")
        else:
            self.log_test("Bulk Finder Upload", False, 
                        f"Bulk finder failed: {response}", response)
            return None
    
    def check_job_status(self, job_id: str, job_type: str):
        """Check job status and progress"""
        if not job_id:
            return None
            
        # Check job details
        status, response = self.make_request("GET", f"/jobs/{job_id}")
        
        if status == 200:
            job_status = response.get("status")
            processed = response.get("processed_records", 0)
            total = response.get("total_records", 0)
            
            self.log_test(f"Job Status Check - {job_id}", True, 
                        f"Status: {job_status}, Progress: {processed}/{total}")
            
            # Wait for completion if still processing
            max_wait = 30  # seconds
            wait_time = 0
            
            while job_status in ["queued", "processing"] and wait_time < max_wait:
                time.sleep(2)
                wait_time += 2
                
                status, response = self.make_request("GET", f"/jobs/{job_id}")
                if status == 200:
                    job_status = response.get("status")
                    processed = response.get("processed_records", 0)
                    
            self.log_test(f"Job Completion - {job_id}", True, 
                        f"Final status: {job_status}, Processed: {processed}")
            
            return job_id
        else:
            self.log_test(f"Job Status Check - {job_id}", False, 
                        f"Failed to get job status: {response}", response)
            return None
    
    def test_job_management(self, job_id: str):
        """Test job management endpoints (pause/resume/stop/retry)"""
        if not job_id:
            return
            
        print(f"\n=== TESTING JOB MANAGEMENT FOR {job_id} ===")
        
        # Test pause
        status, response = self.make_request("POST", f"/jobs/{job_id}/pause")
        if status == 200:
            self.log_test("Job Pause", True, f"Job paused: {response.get('status')}")
        else:
            self.log_test("Job Pause", False, f"Pause failed: {response}", response)
        
        time.sleep(1)
        
        # Test resume
        status, response = self.make_request("POST", f"/jobs/{job_id}/resume")
        if status == 200:
            self.log_test("Job Resume", True, f"Job resumed: {response.get('status')}")
        else:
            self.log_test("Job Resume", False, f"Resume failed: {response}", response)
        
        time.sleep(1)
        
        # Test retry
        status, response = self.make_request("POST", f"/jobs/{job_id}/retry")
        if status == 200:
            self.log_test("Job Retry", True, f"Retry started: {response.get('status')}")
        else:
            self.log_test("Job Retry", False, f"Retry failed: {response}", response)
    
    def test_results_retrieval(self, job_id: str, job_type: str):
        """Test results retrieval endpoints"""
        if not job_id:
            return
            
        print(f"\n=== TESTING RESULTS RETRIEVAL FOR {job_id} ===")
        
        # Test get results
        endpoint = "/results/" if job_type == "verification" else "/finder-results/"
        
        status, response = self.make_request("GET", f"{endpoint}{job_id}")
        
        if status == 200:
            results = response.get("results", [])
            total = response.get("total", 0)
            self.log_test("Results Retrieval", True, 
                        f"Retrieved {len(results)} of {total} results")
            
            # Test pagination
            status, response = self.make_request("GET", f"{endpoint}{job_id}", 
                                               params={"skip": 0, "limit": 2})
            
            if status == 200:
                self.log_test("Results Pagination", True, 
                            f"Pagination works: {len(response.get('results', []))} results")
            else:
                self.log_test("Results Pagination", False, 
                            f"Pagination failed: {response}", response)
            
            # Test export
            status, response = self.make_request("GET", f"/results/{job_id}/export", 
                                               params={"format": "json"})
            
            if status == 200:
                self.log_test("Results Export", True, 
                            f"Export successful: {len(response) if isinstance(response, list) else 'CSV'} records")
            else:
                self.log_test("Results Export", False, 
                            f"Export failed: {response}", response)
        else:
            self.log_test("Results Retrieval", False, 
                        f"Failed to get results: {response}", response)
    
    def test_settings_and_proxies(self):
        """Test settings and proxy management"""
        print("\n=== TESTING SETTINGS & PROXIES ===")
        
        # Test get settings
        status, response = self.make_request("GET", "/settings")
        
        if status == 200:
            self.log_test("Get Settings", True, f"Settings retrieved: {response.get('threads')} threads")
            
            # Test update settings
            updated_settings = response.copy()
            updated_settings["threads"] = 15
            updated_settings["global_delay"] = 2
            
            status, response = self.make_request("PUT", "/settings", updated_settings)
            
            if status == 200:
                self.log_test("Update Settings", True, f"Settings updated: {response.get('threads')} threads")
            else:
                self.log_test("Update Settings", False, f"Settings update failed: {response}", response)
        else:
            self.log_test("Get Settings", False, f"Failed to get settings: {response}", response)
        
        # Test proxy management
        proxy_data = {
            "host": "proxy.example.com",
            "port": 8080,
            "username": "testuser",
            "password": "testpass",
            "proxy_type": "http"
        }
        
        status, response = self.make_request("POST", "/proxies", proxy_data)
        
        if status == 200:
            proxy_id = response.get("id")
            self.log_test("Add Proxy", True, f"Proxy added: {proxy_id}")
            
            # Test list proxies
            status, response = self.make_request("GET", "/proxies")
            
            if status == 200:
                proxies = response if isinstance(response, list) else []
                self.log_test("List Proxies", True, f"Found {len(proxies)} proxies")
                
                # Test delete proxy
                if proxy_id:
                    status, response = self.make_request("DELETE", f"/proxies/{proxy_id}")
                    
                    if status == 200:
                        self.log_test("Delete Proxy", True, "Proxy deleted successfully")
                    else:
                        self.log_test("Delete Proxy", False, f"Delete failed: {response}", response)
            else:
                self.log_test("List Proxies", False, f"Failed to list proxies: {response}", response)
        else:
            self.log_test("Add Proxy", False, f"Failed to add proxy: {response}", response)
    
    def test_analytics(self):
        """Test analytics dashboard endpoint"""
        print("\n=== TESTING ANALYTICS ===")
        
        status, response = self.make_request("GET", "/analytics/dashboard")
        
        if status == 200:
            total_verified = response.get("total_verified", 0)
            success_rate = response.get("success_rate", 0)
            self.log_test("Analytics Dashboard", True, 
                        f"Analytics: {total_verified} verified, {success_rate:.1f}% success rate")
        else:
            self.log_test("Analytics Dashboard", False, 
                        f"Analytics failed: {response}", response)
    
    def test_jobs_list(self):
        """Test jobs listing endpoint"""
        print("\n=== TESTING JOBS LIST ===")
        
        status, response = self.make_request("GET", "/jobs")
        
        if status == 200:
            jobs = response if isinstance(response, list) else []
            self.log_test("Jobs List", True, f"Retrieved {len(jobs)} jobs")
            return jobs
        else:
            self.log_test("Jobs List", False, f"Failed to get jobs: {response}", response)
            return []
    
    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Email Verification API Testing")
        print(f"🔗 Testing against: {self.base_url}")
        
        # Step 1: Authentication
        if not self.test_authentication_flow():
            print("❌ Authentication failed - stopping tests")
            return
        
        # Step 2: Single email verification
        self.test_single_email_verification()
        
        # Step 3: Single email finder
        self.test_single_email_finder()
        
        # Step 4: Bulk verification
        verification_job_id = self.test_bulk_email_verification()
        
        # Step 5: CSV upload verification
        csv_job_id = self.test_csv_upload_verification()
        
        # Step 6: Bulk finder
        finder_job_id = self.test_bulk_email_finder()
        
        # Step 7: Job management (use first available job)
        test_job_id = verification_job_id or csv_job_id or finder_job_id
        if test_job_id:
            self.test_job_management(test_job_id)
        
        # Step 8: Results retrieval
        if verification_job_id:
            self.test_results_retrieval(verification_job_id, "verification")
        if finder_job_id:
            self.test_results_retrieval(finder_job_id, "finder")
        
        # Step 9: Settings and proxies
        self.test_settings_and_proxies()
        
        # Step 10: Analytics
        self.test_analytics()
        
        # Step 11: Jobs list
        self.test_jobs_list()
        
        # Summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   ❌ {result['test']}: {result['message']}")
        
        print("\n" + "="*60)

if __name__ == "__main__":
    tester = EmailVerificationTester()
    tester.run_comprehensive_test()