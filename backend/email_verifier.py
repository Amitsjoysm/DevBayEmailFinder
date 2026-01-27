import dns.resolver
import smtplib
import socket
import re
import aiohttp
import asyncio
import os
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
    
    def calculate_deliverability_score(self, result: dict) -> int:
        """
        Calculate deliverability score (0-100) based on multiple factors
        
        Scoring breakdown:
        - Valid: 80-100 (base 80 + bonuses)
        - Risky: 40-60 
        - Unknown: 20-40
        - Invalid/Disposable/Blocked: 0-20
        """
        score = 0
        status = result.get('status')
        
        # Base score based on status
        if status == VerificationStatus.VALID:
            score = 80
            
            # Bonus for fast response time (<2s)
            if result.get('response_time', 999) < 2.0:
                score += 5
            
            # Bonus for reputable provider
            provider = result.get('provider')
            reputable_providers = [
                EmailProvider.GMAIL, EmailProvider.GSUITE, 
                EmailProvider.O365, EmailProvider.OUTLOOK
            ]
            if provider in reputable_providers:
                score += 5
            
            # Bonus for not catch-all
            if not result.get('is_catch_all', False):
                score += 5
            
            # Bonus for not role-based
            if not result.get('is_role_based', False):
                score += 5
        
        elif status == VerificationStatus.RISKY:
            score = 45
            # Adjust based on factors
            if result.get('is_catch_all', False):
                score = 45  # Catch-all is risky
            if result.get('is_role_based', False):
                score = 50  # Role-based slightly better
            
            # Small bonus for reputable provider even if risky
            provider = result.get('provider')
            if provider in [EmailProvider.GMAIL, EmailProvider.GSUITE, EmailProvider.O365]:
                score += 10
        
        elif status == VerificationStatus.UNKNOWN:
            score = 30
            # Adjust based on retry count
            retry_count = result.get('retry_count', 0)
            if retry_count == 0:
                score = 35  # First attempt, might just be network issue
            elif retry_count > 2:
                score = 20  # Multiple retries failed, likely problematic
        
        elif status == VerificationStatus.BLOCKED:
            score = 15  # IP blocked, email might be valid but can't verify
        
        elif status == VerificationStatus.DISPOSABLE:
            score = 10  # Disposable emails are low quality
        
        elif status == VerificationStatus.INVALID:
            score = 5  # Invalid emails
            if result.get('error_message') and 'format' in result.get('error_message', '').lower():
                score = 0  # Format errors are definitive
        
        elif status == VerificationStatus.PENDING:
            score = 0  # Not yet verified
        
        # Ensure score is within bounds
        return max(0, min(100, score))
    
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
    
    def get_sender_configs(self) -> List[Tuple[str, str]]:
        """
        Get sender email configurations in priority order.
        Returns list of tuples: [(sender_email, sender_domain), ...]
        """
        configs = []
        
        # Priority 1: Gmail sender
        primary_email = os.getenv('PRIMARY_SENDER_EMAIL', 'amits.joys@gmail.com')
        primary_domain = os.getenv('PRIMARY_SENDER_DOMAIN', 'gmail.com')
        configs.append((primary_email, primary_domain))
        
        # Priority 2: MarketJoy sender
        fallback_email = os.getenv('FALLBACK_SENDER_EMAIL', 'amit@marketjoy.com')
        fallback_domain = os.getenv('FALLBACK_SENDER_DOMAIN', 'marketjoy.com')
        configs.append((fallback_email, fallback_domain))
        
        # Priority 3: Legacy sender (if both above fail)
        legacy_email = os.getenv('LEGACY_SENDER_EMAIL', 'verify@verifymail.com')
        legacy_domain = os.getenv('LEGACY_SENDER_DOMAIN', 'verifymail.com')
        configs.append((legacy_email, legacy_domain))
        
        return configs

    def is_sender_rejected_error(self, error_message: str) -> bool:
        """
        Check if error is related to sender being rejected.
        Handles: 5.4.1, 5.7.1, and other sender rejection errors
        """
        error_lower = error_message.lower()
        rejection_indicators = [
            '5.4.1',  # Recipient address rejected: Access denied
            '5.7.1',  # Sender address rejected
            'sender address rejected',
            'domain mx misconfigured',
            'access denied',
            'sender not authenticated',
            'relay access denied',
            'authentication required'
        ]
        return any(indicator in error_lower for indicator in rejection_indicators)

    async def verify_smtp_with_sender(self, email: str, mx_host: str, sender_email: str, sender_domain: str, timeout: int = 10) -> Tuple[VerificationStatus, str, bool, bool]:
        """
        Verify email via SMTP handshake with specific sender.
        Returns: (status, message, is_catch_all, should_retry_with_different_sender)
        """
        try:
            # Connect to SMTP server
            server = smtplib.SMTP(timeout=timeout)
            server.connect(mx_host, 25)
            server.helo(sender_domain)
            server.mail(sender_email)
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
                    server2.helo(sender_domain)
                    server2.mail(sender_email)
                    code2, _ = server2.rcpt(f'nonexistent{int(time.time())}@{email.split("@")[1]}')
                    server2.quit()
                    if code2 == 250:
                        is_catch_all = True
                except Exception:
                    # If random check fails, not a catch-all
                    pass
            
            if code == 250:
                status = VerificationStatus.RISKY if is_catch_all else VerificationStatus.VALID
                return status, message_str, is_catch_all, False
            elif code >= 500:
                return VerificationStatus.INVALID, message_str, False, False
            else:
                return VerificationStatus.UNKNOWN, message_str, False, False
                
        except smtplib.SMTPResponseException as e:
            error_msg = str(e)
            # Check if error is sender-related and we should try different sender
            should_retry = self.is_sender_rejected_error(error_msg)
            
            if e.smtp_code >= 500:
                return VerificationStatus.INVALID, error_msg, False, should_retry
            return VerificationStatus.UNKNOWN, error_msg, False, should_retry
            
        except socket.timeout:
            return VerificationStatus.UNKNOWN, "SMTP timeout", False, False
        except smtplib.SMTPServerDisconnected:
            return VerificationStatus.UNKNOWN, "Server disconnected", False, False
        except ConnectionRefusedError:
            return VerificationStatus.BLOCKED, "Connection refused - IP may be blocked", False, False
        except Exception as e:
            error_msg = f"SMTP Error: {str(e)}"
            should_retry = self.is_sender_rejected_error(error_msg)
            return VerificationStatus.UNKNOWN, error_msg, False, should_retry

    async def verify_smtp(self, email: str, mx_host: str, timeout: int = 10, proxy: dict = None) -> Tuple[VerificationStatus, str, bool]:
        """
        Verify email via SMTP handshake with automatic sender fallback.
        Tries multiple sender addresses if sender is rejected.
        """
        sender_configs = self.get_sender_configs()
        last_error = "No sender configurations available"
        
        for idx, (sender_email, sender_domain) in enumerate(sender_configs):
            try:
                status, message, is_catch_all, should_retry = await self.verify_smtp_with_sender(
                    email, mx_host, sender_email, sender_domain, timeout
                )
                
                # If verification succeeded or got definitive result, return it
                if status in [VerificationStatus.VALID, VerificationStatus.RISKY]:
                    # Add note about which sender worked
                    if idx > 0:  # Not the primary sender
                        message = f"✅ Verified using {sender_email}: {message}"
                    return status, message, is_catch_all
                
                # If it's INVALID but NOT sender-related, return it (definitive result)
                if status == VerificationStatus.INVALID and not should_retry:
                    return status, message, is_catch_all
                
                # If we got sender rejection error, try next sender
                if should_retry and idx < len(sender_configs) - 1:
                    last_error = f"❌ Sender {sender_email} rejected: {message}. Trying next sender..."
                    print(f"[SMTP Fallback] {last_error}")
                    continue
                else:
                    # Last sender or no retry needed
                    last_error = message
                    if status != VerificationStatus.VALID:
                        return status, message, is_catch_all
                    
            except Exception as e:
                last_error = f"Error with sender {sender_email}: {str(e)}"
                print(f"[SMTP Fallback] {last_error}")
                # Try next sender
                if idx < len(sender_configs) - 1:
                    continue
                else:
                    return VerificationStatus.UNKNOWN, last_error, False
        
        # If all senders failed
        return VerificationStatus.UNKNOWN, f"All sender addresses failed. Last error: {last_error}", False
    
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
    
    async def verify_email(self, email: str, use_api_fallback: bool = True, proxy: dict = None, retry_count: int = 0) -> dict:
        """Main verification function with retry support"""
        start_time = time.time()
        
        # Check cache
        if email in self.verification_cache and retry_count == 0:
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
            'verified_at': datetime.now(timezone.utc),
            'retry_count': retry_count,
            'error_message': None
        }
        
        try:
            # Format validation
            if not self.is_valid_email_format(email):
                result['status'] = VerificationStatus.INVALID
                result['smtp_response'] = 'Invalid email format'
                result['error_message'] = 'Email format is invalid'
                result['response_time'] = time.time() - start_time
                result['deliverability_score'] = self.calculate_deliverability_score(result)
                return result
            
            # Check disposable
            result['is_disposable'] = self.is_disposable(email)
            if result['is_disposable']:
                result['status'] = VerificationStatus.DISPOSABLE
                result['smtp_response'] = 'Disposable email provider'
                result['response_time'] = time.time() - start_time
                result['deliverability_score'] = self.calculate_deliverability_score(result)
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
                result['error_message'] = 'Domain has no valid MX records'
                result['response_time'] = time.time() - start_time
                result['deliverability_score'] = self.calculate_deliverability_score(result)
                return result
            
            # Detect provider
            result['provider'] = self.detect_provider(mx_records)
            
            # SMTP verification
            status, response, is_catch_all = await self.verify_smtp(email, mx_records[0], proxy=proxy)
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
            
            # Intelligent status adjustment for UNKNOWN emails
            # If SMTP returns UNKNOWN but email has valid MX records and proper format,
            # it's likely valid (just cautious SMTP server)
            if result['status'] == VerificationStatus.UNKNOWN:
                # Check if we have strong indicators of validity
                has_valid_mx = mx_records and len(mx_records) > 0
                has_good_format = self.is_valid_email_format(email)
                is_reputable_provider = result['provider'] in [
                    EmailProvider.GMAIL, EmailProvider.GSUITE,
                    EmailProvider.O365, EmailProvider.OUTLOOK,
                    EmailProvider.YAHOO, EmailProvider.ZOHO
                ]
                
                # For reputable providers with valid MX, UNKNOWN likely means VALID
                # (they often don't reveal email existence for privacy)
                if is_reputable_provider and has_valid_mx and has_good_format:
                    result['status'] = VerificationStatus.VALID
                    result['smtp_response'] += ' (Adjusted: Reputable provider with valid MX)'
                
                # For custom domains with valid MX and fast response, likely VALID
                elif has_valid_mx and has_good_format and result['response_time'] < 3.0:
                    # If server responded quickly but said UNKNOWN, it's probably valid
                    # (many custom domains use greylisting or privacy protection)
                    result['status'] = VerificationStatus.VALID
                    result['smtp_response'] += ' (Adjusted: Valid MX, fast response, likely valid)'
            
            # Calculate deliverability score
            result['deliverability_score'] = self.calculate_deliverability_score(result)
            
            # Cache successful results
            if result['status'] in [VerificationStatus.VALID, VerificationStatus.INVALID]:
                self.verification_cache[email] = {
                    'result': result,
                    'timestamp': datetime.now(timezone.utc)
                }
        
        except Exception as e:
            result['status'] = VerificationStatus.UNKNOWN
            result['smtp_response'] = f'Verification error: {str(e)}'
            result['error_message'] = str(e)
            result['response_time'] = time.time() - start_time
        
        # Calculate deliverability score even for errors
        result['deliverability_score'] = self.calculate_deliverability_score(result)
        
        return result
