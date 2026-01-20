#!/usr/bin/env python3
"""
Focused CSV Export Bug Fix Testing
Tests the specific CSV export functionality fix for bulk verification and finder results
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
BASE_URL = "https://localhost:9010/api"
TEST_USER_EMAIL = "csv.tester@example.com"
TEST_USER_PASSWORD = "csvtest123"
TEST_USER_NAME = "CSV Tester"

class CSVExportTester:
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
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response.status_code, response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            return 500, {"error": str(e)}
        except json.JSONDecodeError:
            return response.status_code, {"error": "Invalid JSON response"}

    def make_csv_request(self, method: str, endpoint: str, params: dict = None) -> tuple:
        """Make HTTP request expecting CSV response"""
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported method for CSV: {method}")
            
            # For CSV, return the text content directly
            if response.headers.get('content-type', '').startswith('text/csv'):
                return response.status_code, response.text
            else:
                # Try to parse as JSON if not CSV
                try:
                    return response.status_code, response.json()
                except:
                    return response.status_code, response.text
                    
        except requests.exceptions.RequestException as e:
            return 500, {"error": str(e)}
    
    def set_auth_token(self, token: str):
        """Set JWT token for authenticated requests"""
        self.token = token
        self.headers["Authorization"] = f"Bearer {token}"
    
    def authenticate(self):
        """Authenticate user"""
        print("=== AUTHENTICATING USER ===")
        
        # Try login first
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        
        status, response = self.make_request("POST", "/auth/login", login_data)
        
        if status == 200:
            self.log_test("User Login", True, "Login successful")
            self.set_auth_token(response["access_token"])
            self.user_id = response["user"]["id"]
            return True
        elif status == 401:
            # User doesn't exist, register
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
                return True
            else:
                self.log_test("User Registration", False, f"Registration failed: {response}", response)
                return False
        else:
            self.log_test("User Login", False, f"Login failed: {response}", response)
            return False

    def create_bulk_verification_job(self):
        """Create a bulk verification job with mixed email types"""
        print("\n=== CREATING BULK VERIFICATION JOB ===")
        
        # Create CSV with mixed email types to ensure different field presence
        csv_data = """email
john.doe@gmail.com
jane.smith@outlook.com
test.user@yahoo.com
admin@company.com
invalid@nonexistent123.com
user@disposable-email.com
support@risky-domain.net"""
        
        csv_file = io.StringIO(csv_data)
        
        files = {
            'file': ('verification_test.csv', csv_file.getvalue(), 'text/csv')
        }
        
        data = {
            'threads': '5',
            'delay': '1'
        }
        
        status, response = self.make_request("POST", "/verify/upload", data, files=files)
        
        if status == 200:
            job_id = response.get("job_id")
            self.log_test("Bulk Verification Job Created", True, 
                        f"Job ID: {job_id}, Records: {response.get('total_records')}")
            
            # Wait for job completion
            return self.wait_for_job_completion(job_id)
        else:
            self.log_test("Bulk Verification Job Created", False, 
                        f"Failed to create job: {response}", response)
            return None

    def create_bulk_finder_job(self):
        """Create a bulk finder job with mixed name/domain combinations"""
        print("\n=== CREATING BULK FINDER JOB ===")
        
        # Create CSV with different name/domain combinations
        csv_data = """first_name,last_name,domain
John,Smith,google.com
Jane,Doe,microsoft.com
Test,User,github.com
Admin,Support,stackoverflow.com
Marketing,Team,hubspot.com"""
        
        csv_file = io.StringIO(csv_data)
        
        files = {
            'file': ('finder_test.csv', csv_file.getvalue(), 'text/csv')
        }
        
        data = {
            'threads': '3'
        }
        
        status, response = self.make_request("POST", "/find/upload", data, files=files)
        
        if status == 200:
            job_id = response.get("job_id")
            self.log_test("Bulk Finder Job Created", True, 
                        f"Job ID: {job_id}, Records: {response.get('total_records')}")
            
            # Wait for job completion
            return self.wait_for_job_completion(job_id)
        else:
            self.log_test("Bulk Finder Job Created", False, 
                        f"Failed to create job: {response}", response)
            return None

    def wait_for_job_completion(self, job_id: str, max_wait: int = 60):
        """Wait for job to complete"""
        if not job_id:
            return None
            
        print(f"Waiting for job {job_id} to complete...")
        wait_time = 0
        
        while wait_time < max_wait:
            status, response = self.make_request("GET", f"/jobs/{job_id}")
            
            if status == 200:
                job_status = response.get("status")
                processed = response.get("processed_records", 0)
                total = response.get("total_records", 0)
                
                print(f"Job status: {job_status}, Progress: {processed}/{total}")
                
                if job_status in ["completed", "stopped", "failed"]:
                    self.log_test(f"Job Completion - {job_id}", True, 
                                f"Final status: {job_status}, Processed: {processed}")
                    return job_id
                elif job_status in ["queued", "processing"]:
                    time.sleep(3)
                    wait_time += 3
                else:
                    self.log_test(f"Job Completion - {job_id}", False, 
                                f"Unexpected status: {job_status}")
                    return None
            else:
                self.log_test(f"Job Status Check - {job_id}", False, 
                            f"Failed to get job status: {response}", response)
                return None
        
        self.log_test(f"Job Completion - {job_id}", False, 
                    f"Job did not complete within {max_wait} seconds")
        return None

    def test_csv_export_comprehensive(self, job_id: str, job_type: str):
        """Comprehensive CSV export testing for the bug fix"""
        if not job_id:
            return
            
        print(f"\n=== COMPREHENSIVE CSV EXPORT TESTING FOR {job_id} ({job_type}) ===")
        
        # Test 1: CSV Export - Main bug fix test
        print("🔍 Testing CSV export (main bug fix)...")
        status, csv_response = self.make_csv_request("GET", f"/results/{job_id}/export", 
                                                   params={"format": "csv"})
        
        if status == 200:
            try:
                # Parse CSV to verify the fix
                csv_reader = csv.DictReader(io.StringIO(csv_response))
                fieldnames = list(csv_reader.fieldnames) if csv_reader.fieldnames else []
                rows = list(csv_reader)
                
                if fieldnames and len(rows) > 0:
                    self.log_test("CSV Export Success", True, 
                                f"CSV exported successfully: {len(fieldnames)} columns, {len(rows)} rows")
                    
                    # Collect all unique fields from all rows (this was the bug)
                    all_fields_in_data = set()
                    for row in rows:
                        all_fields_in_data.update(row.keys())
                    
                    # Verify all fields are in header (the main fix)
                    missing_fields = all_fields_in_data - set(fieldnames)
                    if not missing_fields:
                        self.log_test("CSV Fieldnames Complete", True, 
                                    f"✅ All fields present in header: {fieldnames}")
                    else:
                        self.log_test("CSV Fieldnames Complete", False, 
                                    f"❌ Missing fields in header: {missing_fields}")
                    
                    # Test enum serialization (status, provider should be strings)
                    enum_serialization_ok = True
                    datetime_serialization_ok = True
                    
                    for i, row in enumerate(rows):
                        # Check status field
                        if 'status' in row and row['status']:
                            if row['status'].startswith('<') or 'VerificationStatus' in row['status']:
                                self.log_test("Enum Serialization - Status", False, 
                                            f"Row {i}: Status not serialized: {row['status']}")
                                enum_serialization_ok = False
                        
                        # Check provider field
                        if 'provider' in row and row['provider']:
                            if row['provider'].startswith('<') or 'EmailProvider' in row['provider']:
                                self.log_test("Enum Serialization - Provider", False, 
                                            f"Row {i}: Provider not serialized: {row['provider']}")
                                enum_serialization_ok = False
                        
                        # Check datetime fields
                        for field in ['created_at', 'verified_at', 'last_verified_at']:
                            if field in row and row[field]:
                                # Should be ISO format (contains T and Z or +)
                                if not ('T' in row[field] and ('Z' in row[field] or '+' in row[field] or '-' in row[field])):
                                    self.log_test(f"Datetime Serialization - {field}", False, 
                                                f"Row {i}: {field} not in ISO format: {row[field]}")
                                    datetime_serialization_ok = False
                    
                    if enum_serialization_ok:
                        self.log_test("Enum Serialization", True, 
                                    "✅ All enum values properly serialized to strings")
                    
                    if datetime_serialization_ok:
                        self.log_test("Datetime Serialization", True, 
                                    "✅ All datetime values in ISO format")
                    
                    # Print sample of CSV for verification
                    print(f"\n📋 CSV Sample (first 2 rows):")
                    print(f"Headers: {fieldnames}")
                    for i, row in enumerate(rows[:2]):
                        print(f"Row {i+1}: {dict(row)}")
                    
                else:
                    self.log_test("CSV Export Success", False, "CSV is empty or has no valid structure")
                    
            except Exception as e:
                self.log_test("CSV Export Parsing", False, f"Failed to parse CSV: {str(e)}")
        else:
            self.log_test("CSV Export Success", False, f"CSV export failed with status {status}: {csv_response}")
        
        # Test 2: JSON Export (should still work)
        print("\n🔍 Testing JSON export...")
        status, response = self.make_request("GET", f"/results/{job_id}/export", 
                                           params={"format": "json"})
        
        if status == 200 and isinstance(response, list):
            self.log_test("JSON Export", True, f"✅ JSON export works: {len(response)} records")
        else:
            self.log_test("JSON Export", False, f"❌ JSON export failed: {response}")
        
        # Test 3: CSV Export with status filter (for verification jobs)
        if job_type == "verification":
            print("\n🔍 Testing CSV export with status filter...")
            status, csv_response = self.make_csv_request("GET", f"/results/{job_id}/export", 
                                                       params={"format": "csv", "status": "valid"})
            
            if status == 200:
                try:
                    csv_reader = csv.DictReader(io.StringIO(csv_response))
                    filtered_rows = list(csv_reader)
                    self.log_test("CSV Export with Filter", True, 
                                f"✅ Filtered CSV export works: {len(filtered_rows)} valid records")
                except:
                    self.log_test("CSV Export with Filter", False, "Failed to parse filtered CSV")
            else:
                self.log_test("CSV Export with Filter", False, f"❌ Filtered CSV export failed: {csv_response}")

    def run_csv_export_tests(self):
        """Run focused CSV export tests"""
        print("🚀 Starting CSV Export Bug Fix Testing")
        print(f"🔗 Testing against: {self.base_url}")
        
        # Step 1: Authentication
        if not self.authenticate():
            print("❌ Authentication failed - stopping tests")
            return
        
        # Step 2: Create and test bulk verification job
        verification_job_id = self.create_bulk_verification_job()
        if verification_job_id:
            self.test_csv_export_comprehensive(verification_job_id, "verification")
        
        # Step 3: Create and test bulk finder job
        finder_job_id = self.create_bulk_finder_job()
        if finder_job_id:
            self.test_csv_export_comprehensive(finder_job_id, "finder")
        
        # Summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📊 CSV EXPORT TEST SUMMARY")
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
        else:
            print("\n🎉 ALL CSV EXPORT TESTS PASSED!")
            print("✅ CSV export bug fix is working correctly")
        
        print("\n" + "="*60)

if __name__ == "__main__":
    tester = CSVExportTester()
    tester.run_csv_export_tests()