from typing import List, Optional
import asyncio
import time
from email_verifier import EmailVerifier
from models import VerificationStatus

EMAIL_PATTERNS = [
    '{first}.{last}@{domain}',
    '{first}{last}@{domain}',
    '{first}@{domain}',
    '{last}@{domain}',
    '{f}{last}@{domain}',
    '{first}{l}@{domain}',
    '{f}{l}@{domain}',
    '{first}_{last}@{domain}',
    '{first}-{last}@{domain}',
    '{last}{f}@{domain}'
]

class EmailFinder:
    def __init__(self):
        self.verifier = EmailVerifier()
        self.domain_patterns = {}  # Cache successful patterns per domain
    
    def generate_email_variants(self, first_name: str, last_name: str, domain: str, patterns: Optional[List[str]] = None) -> List[str]:
        """Generate email variants based on patterns"""
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ''
        l = last[0] if last else ''
        
        # Check if we have a successful pattern cached for this domain
        if domain in self.domain_patterns:
            cached_pattern = self.domain_patterns[domain]
            try:
                email = cached_pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                return [email]  # Return cached pattern first
            except:
                pass
        
        use_patterns = patterns if patterns else EMAIL_PATTERNS
        emails = []
        
        for pattern in use_patterns:
            try:
                email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                emails.append(email)
            except KeyError:
                continue
        
        return emails
    
    async def find_email(self, first_name: str, last_name: str, domain: str, 
                        patterns: Optional[List[str]] = None, 
                        stop_on_first_valid: bool = True) -> dict:
        """Find and verify email using pattern matching"""
        start_time = time.time()
        
        emails = self.generate_email_variants(first_name, last_name, domain, patterns)
        
        results = []
        found_email = None
        
        for email in emails:
            verification_result = await self.verifier.verify_email(email, use_api_fallback=True)
            results.append(verification_result)
            
            if verification_result['status'] == VerificationStatus.VALID:
                found_email = email
                # Cache successful pattern for this domain
                for pattern in EMAIL_PATTERNS:
                    try:
                        test_email = pattern.format(
                            first=first_name.lower(), 
                            last=last_name.lower(), 
                            f=first_name[0].lower(), 
                            l=last_name[0].lower(), 
                            domain=domain
                        )
                        if test_email == email:
                            self.domain_patterns[domain] = pattern
                            break
                    except:
                        continue
                
                if stop_on_first_valid:
                    break
        
        return {
            'found': found_email is not None,
            'email': found_email,
            'first_name': first_name,
            'last_name': last_name,
            'domain': domain,
            'patterns_tested': len(results),
            'all_results': results,
            'search_time': time.time() - start_time
        }
