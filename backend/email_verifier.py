import dns.resolver
import smtplib
import socket
import re
import aiohttp
import asyncio
from typing import Tuple, List, Optional
from datetime import datetime, timezone
import time
from models import VerificationStatus, EmailProvider

DISPOSABLE_DOMAINS = [
    'tempmail.com', 'guerrillamail.com', '10minutemail.com', 'throwaway.email',
    'mailinator.com', 'maildrop.cc', 'trashmail.com', 'yopmail.com'
]

ROLE_BASED_PREFIXES = [
    'admin', 'info', 'support', 'sales', 'contact', 'help', 'service',
    'noreply', 'no-reply', 'webmaster', 'postmaster', 'abuse'
]

class EmailVerifier:
    def __init__(self):
        self.verification_cache = {}
        self.mx_cache = {}
        self.pattern_cache = {}
        self.domain_request_times = {}  # Track last request time per domain
        self.current_proxy = None
    
    def is_valid_email_format(self, email: str) -> bool:
        """Validate email format using RFC 5322 regex"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def is_disposable(self, email: str) -> bool:
        """Check if email is from disposable provider"""
        domain = email.split('@')[1].lower()
        return domain in DISPOSABLE_DOMAINS
    
    def is_role_based(self, email: str) -> bool:
        """Check if email is role-based"""
        local_part = email.split('@')[0].lower()
        return any(local_part.startswith(prefix) for prefix in ROLE_BASED_PREFIXES)
    
    async def get_mx_records(self, domain: str) -> Tuple[List[str], bool]:
        """Get MX records for domain"""
        if domain in self.mx_cache:
            return self.mx_cache[domain]
        
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_hosts = [str(r.exchange).rstrip('.') for r in mx_records]
            self.mx_cache[domain] = (mx_hosts, True)
            return mx_hosts, True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
            self.mx_cache[domain] = ([], False)
            return [], False
        except Exception as e:
            return [], False
    
    def detect_provider(self, mx_records: List[str]) -> EmailProvider:
        """Detect email provider from MX records"""
        if not mx_records:
            return EmailProvider.CUSTOM
        
        mx_str = ' '.join(mx_records).lower()
        
        if 'google' in mx_str or 'googlemail' in mx_str:
            if 'aspmx.l.google.com' in mx_str:
                return EmailProvider.GSUITE
            return EmailProvider.GMAIL
        elif 'outlook' in mx_str or 'protection.outlook.com' in mx_str:
            return EmailProvider.O365
        elif 'mail.protection.outlook.com' in mx_str:
            return EmailProvider.O365
        elif 'outlook.com' in mx_str:
            return EmailProvider.OUTLOOK
        elif 'yahoodns' in mx_str or 'yahoo.com' in mx_str:
            return EmailProvider.YAHOO
        elif 'zoho' in mx_str:
            return EmailProvider.ZOHO
        elif 'aol.com' in mx_str:
            return EmailProvider.AOL
        elif 'protonmail' in mx_str:
            return EmailProvider.PROTONMAIL
        elif 'messagingengine.com' in mx_str or 'fastmail' in mx_str:
            return EmailProvider.FASTMAIL
        elif 'rediffmail' in mx_str:
            return EmailProvider.REDIFFMAIL
        else:
            return EmailProvider.CUSTOM
    
    async def verify_smtp(self, email: str, mx_host: str, timeout: int = 10) -> Tuple[VerificationStatus, str, bool]:
        """Verify email via SMTP handshake"""
        try:
            # Connect to SMTP server
            server = smtplib.SMTP(timeout=timeout)
            server.connect(mx_host, 25)
            server.helo('verifymail.com')
            server.mail('verify@verifymail.com')
            code, message = server.rcpt(email)
            server.quit()
            
            message_str = message.decode() if isinstance(message, bytes) else str(message)
            
            # Check for catch-all
            is_catch_all = False
            if code == 250:
                # Test with random email
                try:
                    server2 = smtplib.SMTP(timeout=timeout)
                    server2.connect(mx_host, 25)
                    server2.helo('verifymail.com')
                    server2.mail('verify@verifymail.com')
                    code2, _ = server2.rcpt(f'nonexistent{int(time.time())}@{email.split("@")[1]}')
                    server2.quit()
                    if code2 == 250:
                        is_catch_all = True
                except:
                    pass
            
            if code == 250:
                status = VerificationStatus.RISKY if is_catch_all else VerificationStatus.VALID
                return status, message_str, is_catch_all
            elif code >= 500:
                return VerificationStatus.INVALID, message_str, False
            else:
                return VerificationStatus.UNKNOWN, message_str, False
                
        except socket.timeout:
            return VerificationStatus.UNKNOWN, "SMTP timeout", False
        except smtplib.SMTPServerDisconnected:
            return VerificationStatus.UNKNOWN, "Server disconnected", False
        except smtplib.SMTPResponseException as e:
            if e.smtp_code >= 500:
                return VerificationStatus.INVALID, str(e), False
            return VerificationStatus.UNKNOWN, str(e), False
        except Exception as e:
            return VerificationStatus.UNKNOWN, str(e), False
    
    async def verify_external_api(self, email: str) -> Tuple[VerificationStatus, str]:
        """Fallback verification using external API"""
        try:
            verification_url = 'http://158.69.113.127:8080/v0/check_email'
            payload = {"to_email": email}
            headers = {
                "Authorization": "",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(verification_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Parse response based on API format
                        if data.get('valid') or data.get('status') == 'valid':
                            return VerificationStatus.VALID, "External API: Valid"
                        elif data.get('status') == 'invalid':
                            return VerificationStatus.INVALID, "External API: Invalid"
                        else:
                            return VerificationStatus.UNKNOWN, "External API: Unknown"
                    else:
                        return VerificationStatus.UNKNOWN, f"API Error: {response.status}"
        except asyncio.TimeoutError:
            return VerificationStatus.UNKNOWN, "External API timeout"
        except Exception as e:
            return VerificationStatus.UNKNOWN, f"External API error: {str(e)}"
    
    async def verify_email(self, email: str, use_api_fallback: bool = True) -> dict:
        """Main verification function"""
        start_time = time.time()
        
        # Check cache
        if email in self.verification_cache:
            cached = self.verification_cache[email]
            if (datetime.now(timezone.utc) - cached['timestamp']).seconds < 3600:
                return cached['result']
        
        result = {
            'email': email,
            'status': VerificationStatus.UNKNOWN,
            'provider': EmailProvider.CUSTOM,
            'mx_records': [],
            'response_time': 0,
            'smtp_response': '',
            'is_catch_all': False,
            'is_role_based': False,
            'is_disposable': False,
            'verified_at': datetime.now(timezone.utc)
        }
        
        # Format validation
        if not self.is_valid_email_format(email):
            result['status'] = VerificationStatus.INVALID
            result['smtp_response'] = 'Invalid email format'
            result['response_time'] = time.time() - start_time
            return result
        
        # Check disposable
        result['is_disposable'] = self.is_disposable(email)
        if result['is_disposable']:
            result['status'] = VerificationStatus.DISPOSABLE
            result['smtp_response'] = 'Disposable email provider'
            result['response_time'] = time.time() - start_time
            return result
        
        # Check role-based
        result['is_role_based'] = self.is_role_based(email)
        
        # Get MX records
        domain = email.split('@')[1]
        mx_records, mx_valid = await self.get_mx_records(domain)
        result['mx_records'] = mx_records
        
        if not mx_valid or not mx_records:
            result['status'] = VerificationStatus.INVALID
            result['smtp_response'] = 'No MX records found'
            result['response_time'] = time.time() - start_time
            return result
        
        # Detect provider
        result['provider'] = self.detect_provider(mx_records)
        
        # SMTP verification
        status, response, is_catch_all = await self.verify_smtp(email, mx_records[0])
        result['status'] = status
        result['smtp_response'] = response
        result['is_catch_all'] = is_catch_all
        
        # Fallback to external API if SMTP fails
        if use_api_fallback and status == VerificationStatus.UNKNOWN:
            api_status, api_response = await self.verify_external_api(email)
            if api_status != VerificationStatus.UNKNOWN:
                result['status'] = api_status
                result['smtp_response'] = api_response
        
        result['response_time'] = time.time() - start_time
        
        # Cache result
        self.verification_cache[email] = {
            'result': result,
            'timestamp': datetime.now(timezone.utc)
        }
        
        return result
