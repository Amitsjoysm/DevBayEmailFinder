#!/usr/bin/env python3
"""
Test Specific SMTP Error Scenarios
Tests the handling of specific SMTP errors mentioned by user:
- 5.4.1 Recipient address rejected: Access denied
- 5.7.1 Sender address rejected: Domain MX misconfigured
"""
import sys
sys.path.insert(0, '/app/backend')

from email_verifier import EmailVerifier

def test_error_detection():
    """Test that error detection works for specific error codes"""
    verifier = EmailVerifier()
    
    print("=" * 80)
    print("🧪 Testing SMTP Error Detection Logic")
    print("=" * 80)
    print()
    
    # Test cases for is_sender_rejected_error()
    test_cases = [
        ("5.4.1 Recipient address rejected: Access denied. For more information see https://aka.ms/EXOSmtpErrors [CY4PEPF0000EDD0.namprd03.prod.outlook.com 2026-01-27T07:38:02.312Z 08DE59859994FAE5]", True),
        ("5.7.1 <verify@verifymail.com>: Sender address rejected: Inform your own DNS administrator urgently: Domain MX misconfigured, in loopback network", True),
        ("5.1.1 User unknown", False),  # Recipient invalid, not sender issue
        ("5.5.0 Requested action not taken: mailbox unavailable", False),
        ("sender address rejected", True),
        ("access denied", True),
        ("relay access denied", True),
        ("authentication required", True),
        ("250 OK", False),
    ]
    
    print("📋 Error Detection Tests:")
    print("-" * 80)
    
    for error_msg, expected in test_cases:
        result = verifier.is_sender_rejected_error(error_msg)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"{status} | Expected: {expected}, Got: {result}")
        print(f"   Error: {error_msg[:80]}...")
        print()
    
    print("=" * 80)
    print("✅ Error Detection Test Complete")
    print("=" * 80)
    print()
    
    # Test sender configurations
    print("=" * 80)
    print("📧 Configured Sender Addresses:")
    print("=" * 80)
    sender_configs = verifier.get_sender_configs()
    for idx, (email, domain) in enumerate(sender_configs, 1):
        print(f"{idx}. Email: {email}")
        print(f"   Domain: {domain}")
        print()
    
    print("=" * 80)
    print("Fallback Order:")
    print("1️⃣  Try Gmail sender first (amits.joys@gmail.com)")
    print("2️⃣  If rejected, try MarketJoy sender (amit@marketjoy.com)")  
    print("3️⃣  If still rejected, try legacy sender (verify@verifymail.com)")
    print("=" * 80)

if __name__ == "__main__":
    test_error_detection()
