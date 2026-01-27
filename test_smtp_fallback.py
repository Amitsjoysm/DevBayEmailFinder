#!/usr/bin/env python3
"""
Test SMTP Fallback Logic with Multiple Sender Addresses
This script tests the enhanced email verification with sender fallback
"""
import sys
import os
sys.path.insert(0, '/app/backend')

import asyncio
from email_verifier import EmailVerifier
from models import VerificationStatus

async def test_smtp_fallback():
    """Test email verification with sender fallback"""
    verifier = EmailVerifier()
    
    print("=" * 80)
    print("🧪 Testing SMTP Verification with Sender Fallback Logic")
    print("=" * 80)
    print()
    
    # Get sender configs
    sender_configs = verifier.get_sender_configs()
    print("📧 Configured Sender Addresses (in priority order):")
    for idx, (email, domain) in enumerate(sender_configs, 1):
        print(f"  {idx}. {email} (domain: {domain})")
    print()
    
    # Test cases
    test_emails = [
        "amits.joys@gmail.com",  # Should work with any sender
        "test@outlook.com",      # May trigger Outlook errors
        "amit@marketjoy.com",    # Custom domain
        "invalid@invaliddomain123456.com"  # Invalid domain
    ]
    
    print("🎯 Testing Email Verification:")
    print("-" * 80)
    
    for email in test_emails:
        print(f"\n✉️  Testing: {email}")
        result = await verifier.verify_email(email, use_api_fallback=False)
        
        print(f"   Status: {result['status'].value}")
        print(f"   Provider: {result['provider'].value}")
        print(f"   Deliverability Score: {result.get('deliverability_score', 'N/A')}")
        print(f"   Response: {result['smtp_response'][:100]}...")
        print(f"   MX Records: {len(result['mx_records'])} found")
        print(f"   Response Time: {result['response_time']:.2f}s")
        
        if result['error_message']:
            print(f"   ⚠️  Error: {result['error_message']}")
        
        print()
    
    print("=" * 80)
    print("✅ SMTP Fallback Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_smtp_fallback())
