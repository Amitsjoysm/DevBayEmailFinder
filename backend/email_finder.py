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
    
    async def generate_email_variants_with_cache(self, first_name: str, last_name: str, domain: str, patterns: Optional[List[str]] = None) -> List[str]:
        """Generate email variants with persistent domain cache lookup
        CRITICAL: first.last@domain is ALWAYS tested FIRST, before any cached pattern
        """
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ''
        l = last[0] if last else ''
        
        use_patterns = patterns if patterns else EMAIL_PATTERNS
        emails = []
        
        logger.info(f"🔍 Generating email variants for {first_name} {last_name} @ {domain}")
        
        cached_pattern = None
        
        # Check persistent cache first (database)
        if self.domain_cache_service:
            try:
                cache_entry = await self.domain_cache_service.get_domain_pattern(domain)
                if cache_entry:
                    cached_pattern = cache_entry['pattern']
                    logger.info(f"✅ Found PERSISTENT cached pattern for {domain}: {cached_pattern} (confidence: {cache_entry.get('confidence_score', 0)})")
            except Exception as e:
                logger.error(f"Error fetching from persistent cache: {e}")
        
        # Fallback to in-memory cache if no persistent cache
        if not cached_pattern and domain in self.domain_patterns:
            cached_pattern = self.domain_patterns[domain]
            logger.info(f"✅ Found IN-MEMORY cached pattern for {domain}: {cached_pattern}")
        
        # CRITICAL: ALWAYS add first.last@domain as #1 priority (unless it's the cached pattern)
        first_last_pattern = '{first}.{last}@{domain}'
        if first_last_pattern != cached_pattern:
            try:
                email = first_last_pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                emails.append(email)
                logger.info(f"⭐ Priority #1: {email} (first.last pattern - ALWAYS FIRST)")
            except KeyError:
                pass
        
        # If we have a cached pattern, add it as #2 priority (or #1 if it's first.last)
        if cached_pattern and cached_pattern in use_patterns:
            try:
                email = cached_pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                if email not in emails:  # Avoid duplicates
                    emails.append(email)
                    priority_num = len(emails)
                    logger.info(f"📌 Priority #{priority_num}: {email} (cached pattern)")
            except KeyError:
                pass
        
        # Then add all other patterns in their original order
        for idx, pattern in enumerate(use_patterns):
            if pattern not in [first_last_pattern, cached_pattern]:  # Skip already added patterns
                try:
                    email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
                    if email not in emails:  # Avoid duplicates
                        emails.append(email)
                except KeyError:
                    continue
        
        logger.info(f"📋 Generated {len(emails)} email variants, testing in order")
        logger.info(f"🔢 Pattern order: {emails[:3]}...")  # Show first 3 for verification
        return emails
    
    
    async def find_email(self, first_name: str, last_name: str, domain: str, 
                        patterns: Optional[List[str]] = None, 
                        stop_on_first_valid: bool = True,
                        proxy: dict = None,
                        user_id: str = None) -> dict:
        """Find and verify email using pattern matching with persistent cache"""
        start_time = time.time()
        
        try:
            emails = await self.generate_email_variants_with_cache(first_name, last_name, domain, patterns)
            
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
                        
                        # Determine which pattern matched
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
                                    
                                    # Save to in-memory cache (legacy)
                                    self.domain_patterns[domain] = pattern
                                    
                                    # Save to persistent cache (database)
                                    if self.domain_cache_service and user_id:
                                        try:
                                            await self.domain_cache_service.save_domain_pattern(
                                                domain=domain,
                                                pattern=pattern,
                                                user_id=user_id,
                                                email_found=email,
                                                first_name=first_name,
                                                last_name=last_name
                                            )
                                        except Exception as e:
                                            logger.error(f"Failed to save to persistent cache: {e}")
                                    
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
