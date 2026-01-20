from typing import List, Optional
import asyncio
import time
import logging
from email_verifier import EmailVerifier
from models import VerificationStatus

logger = logging.getLogger(__name__)

# PRIORITY PATTERN: first.last@domain is tested FIRST always
EMAIL_PATTERNS = [
    '{first}.{last}@{domain}',  # PRIORITY: Most common professional format
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
    def __init__(self, domain_cache_service=None):
        self.verifier = EmailVerifier()
        self.domain_patterns = {}  # In-memory cache (legacy)
        self.domain_cache_service = domain_cache_service  # Persistent cache
    
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
        
        logger.info(f"🔍 Generating email variants for {first_name} {last_name} @ {domain}")
        
        # CRITICAL FIX: Always check patterns in order, prioritizing cached pattern
        # but never excluding other patterns to ensure first.last@domain is checked before first@domain
        cached_pattern = None
        if domain in self.domain_patterns:
            cached_pattern = self.domain_patterns[domain]
            logger.info(f"✅ Found cached pattern for {domain}: {cached_pattern}")
        
        # If we have a cached pattern, put it first, then all others in order
        if cached_pattern and cached_pattern in use_patterns:
            # Add cached pattern first
            try:
                email = cached_pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                emails.append(email)
                logger.info(f"📌 Priority #1: {email} (cached pattern)")
            except KeyError:
                pass
            
            # Then add all other patterns in their original order
            for idx, pattern in enumerate(use_patterns):
                if pattern != cached_pattern:  # Skip the cached one we already added
                    try:
                        email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                        if email not in emails:  # Avoid duplicates
                            emails.append(email)
                            if pattern == '{first}.{last}@{domain}':
                                logger.info(f"⭐ Priority #{len(emails)}: {email} (first.last pattern)")
                    except KeyError:
                        continue
        else:
            # No cache or cache not in patterns, use standard order
            # Ensure first.last@domain is ALWAYS first
            for idx, pattern in enumerate(use_patterns):
                try:
                    email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                    emails.append(email)
                    if idx == 0 and pattern == '{first}.{last}@{domain}':
                        logger.info(f"⭐ Priority #1: {email} (first.last pattern - DEFAULT)")
                except KeyError:
                    continue
        
        logger.info(f"📋 Generated {len(emails)} email variants, testing in order")
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
            found_pattern = None
            
            for idx, email in enumerate(emails, 1):
                try:
                    logger.info(f"🔍 Testing pattern {idx}/{len(emails)}: {email}")
                    verification_result = await self.verifier.verify_email(email, use_api_fallback=True, proxy=proxy)
                    results.append(verification_result)
                    
                    if verification_result['status'] == VerificationStatus.VALID:
                        found_email = email
                        logger.info(f"✅ SUCCESS! Found valid email: {email} on attempt {idx}/{len(emails)}")
                        
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
                                    found_pattern = pattern
                                    self.domain_patterns[domain] = pattern
                                    logger.info(f"💾 Cached pattern for {domain}: {pattern}")
                                    if pattern == '{first}.{last}@{domain}':
                                        logger.info(f"⭐ CONFIRMED: first.last@domain pattern works for {domain}")
                                    break
                            except:
                                continue
                        
                        if stop_on_first_valid:
                            break
                    else:
                        logger.info(f"❌ Pattern {idx} failed: {email} -> {verification_result['status']}")
                except Exception as e:
                    # Continue to next pattern on error
                    logger.error(f"⚠️ Error testing {email}: {str(e)}")
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
                'found_pattern': found_pattern,
                'all_results': results,
                'search_time': time.time() - start_time,
                'error_message': None,
                'deliverability_score': 0
            }
            
            # Calculate deliverability score
            result['deliverability_score'] = self.calculate_finder_score(result)
            
            if found_email:
                logger.info(f"🎉 Email found in {result['search_time']:.2f}s after testing {len(results)} patterns")
            else:
                logger.info(f"😞 No valid email found after testing {len(results)} patterns in {result['search_time']:.2f}s")
            
            return result
        except Exception as e:
            logger.error(f"💥 Finder error: {str(e)}")
            return {
                'found': False,
                'email': None,
                'first_name': first_name,
                'last_name': last_name,
                'domain': domain,
                'patterns_tested': 0,
                'found_pattern': None,
                'all_results': [],
                'search_time': time.time() - start_time,
                'error_message': f'Finder error: {str(e)}',
                'deliverability_score': 0
            }
