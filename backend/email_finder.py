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
    
    def calculate_finder_score(self, result: dict) -> int:
        """
        Calculate deliverability score for finder results
        
        For found emails: Use verification score with pattern confidence adjustment
        For not found: 0 score
        """
        if not result.get('found'):
            return 0
        
        # Get the verification score from the found email
        all_results = result.get('all_results', [])
        found_email = result.get('email')
        
        score = 0
        for verification in all_results:
            if verification.get('email') == found_email:
                # Use the verifier's scoring logic
                score = self.verifier.calculate_deliverability_score(verification)
                
                # Adjust based on pattern confidence
                patterns_tested = result.get('patterns_tested', 1)
                if patterns_tested <= 2:
                    # Found quickly = high confidence, add bonus
                    score = min(100, score + 5)
                elif patterns_tested <= 5:
                    # Found within reasonable attempts
                    score = min(100, score + 2)
                # More patterns = lower confidence, no adjustment
                
                break
        
        return score
    
    def generate_email_variants(self, first_name: str, last_name: str, domain: str, patterns: Optional[List[str]] = None) -> List[str]:
        """Generate email variants based on patterns - ALWAYS checks in priority order"""
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ''
        l = last[0] if last else ''
        
        use_patterns = patterns if patterns else EMAIL_PATTERNS
        emails = []
        
        # CRITICAL FIX: Always check patterns in order, prioritizing cached pattern
        # but never excluding other patterns to ensure first.last@domain is checked before first@domain
        cached_pattern = None
        if domain in self.domain_patterns:
            cached_pattern = self.domain_patterns[domain]
        
        # If we have a cached pattern, put it first, then all others in order
        if cached_pattern and cached_pattern in use_patterns:
            # Add cached pattern first
            try:
                email = cached_pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                emails.append(email)
            except KeyError:
                pass
            
            # Then add all other patterns in their original order
            for pattern in use_patterns:
                if pattern != cached_pattern:  # Skip the cached one we already added
                    try:
                        email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                        if email not in emails:  # Avoid duplicates
                            emails.append(email)
                    except KeyError:
                        continue
        else:
            # No cache or cache not in patterns, use standard order
            for pattern in use_patterns:
                try:
                    email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                    emails.append(email)
                except KeyError:
                    continue
        
        return emails
    
    async def find_email(self, first_name: str, last_name: str, domain: str, 
                        patterns: Optional[List[str]] = None, 
                        stop_on_first_valid: bool = True,
                        proxy: dict = None) -> dict:
        """Find and verify email using pattern matching"""
        start_time = time.time()
        
        try:
            emails = self.generate_email_variants(first_name, last_name, domain, patterns)
            
            results = []
            found_email = None
            
            for email in emails:
                try:
                    verification_result = await self.verifier.verify_email(email, use_api_fallback=True, proxy=proxy)
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
                except Exception as e:
                    # Continue to next pattern on error
                    results.append({
                        'email': email,
                        'status': VerificationStatus.UNKNOWN,
                        'error_message': str(e)
                    })
                    continue
            
            result = {
                'found': found_email is not None,
                'email': found_email,
                'first_name': first_name,
                'last_name': last_name,
                'domain': domain,
                'patterns_tested': len(results),
                'all_results': results,
                'search_time': time.time() - start_time,
                'error_message': None,
                'deliverability_score': 0
            }
            
            # Calculate deliverability score
            result['deliverability_score'] = self.calculate_finder_score(result)
            
            return result
        except Exception as e:
            return {
                'found': False,
                'email': None,
                'first_name': first_name,
                'last_name': last_name,
                'domain': domain,
                'patterns_tested': 0,
                'all_results': [],
                'search_time': time.time() - start_time,
                'error_message': f'Finder error: {str(e)}',
                'deliverability_score': 0
            }
