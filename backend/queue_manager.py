import asyncio
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import time
from models import VerificationJob, VerificationResult, JobStatus, VerificationStatus, FinderResult, EmailProvider
from email_verifier import EmailVerifier
from email_finder import EmailFinder
from ledger_service import LedgerService
import random
import logging

logger = logging.getLogger(__name__)

class VerificationQueue:
    def __init__(self, db, socketio):
        self.db = db
        self.socketio = socketio
        self.verifier = EmailVerifier()
        self.finder = EmailFinder()
        self.ledger = LedgerService(db)
        self.active_jobs = {}  # job_id -> job_state
        self.proxies = []
        self.current_proxy_index = 0
        self.retry_queue = asyncio.Queue()
        self.domain_last_request = {}  # Track last request time per domain
    
    async def load_proxies(self, user_id: str):
        """Load active proxies for user"""
        try:
            proxies = await self.db.proxies.find(
                {"user_id": user_id, "is_active": True},
                {"_id": 0}
            ).to_list(None)
            self.proxies = proxies
            logger.info(f"Loaded {len(proxies)} proxies for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
            self.proxies = []
    
    def get_next_proxy(self) -> Optional[dict]:
        """Get next proxy from rotation"""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy
    
    async def apply_domain_delay(self, domain: str, delay_seconds: int):
        """Apply domain-specific delay to prevent rate limiting"""
        if domain in self.domain_last_request:
            elapsed = time.time() - self.domain_last_request[domain]
            if elapsed < delay_seconds:
                await asyncio.sleep(delay_seconds - elapsed)
        self.domain_last_request[domain] = time.time()
    
    async def update_job_progress(self, job_id: str, user_id: str, current_email: str = None):
        """Update and broadcast job progress with live counter"""
        if job_id not in self.active_jobs:
            return
        
        try:
            job_state = self.active_jobs[job_id]
            job = job_state['job']
            
            # Calculate progress
            progress_percentage = (job['processed_records'] / job['total_records'] * 100) if job['total_records'] > 0 else 0
            
            # Calculate ETA and processing rate
            processing_rate = 0
            if job['processed_records'] > 0 and job['started_at']:
                elapsed = (datetime.now(timezone.utc) - job['started_at']).total_seconds()
                avg_time_per_record = elapsed / job['processed_records']
                remaining_records = job['total_records'] - job['processed_records']
                eta_seconds = int(avg_time_per_record * remaining_records)
                job['eta_seconds'] = eta_seconds
                
                # Calculate processing rate (emails per second)
                processing_rate = round(job['processed_records'] / elapsed, 2) if elapsed > 0 else 0
            
            # Update database
            update_data = {
                "processed_records": job['processed_records'],
                "valid_count": job['valid_count'],
                "invalid_count": job['invalid_count'],
                "risky_count": job['risky_count'],
                "unknown_count": job['unknown_count'],
                "error_count": job.get('error_count', 0),
                "eta_seconds": job.get('eta_seconds')
            }
            
            # Add finder-specific counts
            if job.get('job_type') == 'finder':
                update_data['found_count'] = job.get('found_count', 0)
                update_data['not_found_count'] = job.get('not_found_count', 0)
            
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": update_data}
            )
            
            # Broadcast progress via WebSocket with enhanced live counter data
            progress_data = {
                'job_id': job_id,
                'status': job['status'],
                'total_records': job['total_records'],
                'processed_records': job['processed_records'],
                'valid_count': job['valid_count'],
                'invalid_count': job['invalid_count'],
                'risky_count': job['risky_count'],
                'unknown_count': job['unknown_count'],
                'found_count': job.get('found_count', 0),
                'not_found_count': job.get('not_found_count', 0),
                'error_count': job.get('error_count', 0),
                'progress_percentage': round(progress_percentage, 1),
                'eta_seconds': job.get('eta_seconds'),
                'active_threads': job_state['active_threads'],
                'processing_rate': processing_rate,  # NEW: emails/second
                'current_email': current_email  # NEW: current email being processed
            }
            
            await self.socketio.emit('job_progress', progress_data, room=user_id)
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
    
    async def process_verification_batch(self, job_id: str, user_id: str, emails: List[str], settings: dict):
        """Process a batch of email verifications with ledger caching and retry support"""
        if job_id not in self.active_jobs:
            return
        
        job_state = self.active_jobs[job_id]
        job = job_state['job']
        
        for email in emails:
            try:
                if job['status'] == JobStatus.PAUSED:
                    break
                
                if job['status'] != JobStatus.PROCESSING:
                    break
                
                # Emit current email being processed for live counter
                await self.update_job_progress(job_id, user_id, current_email=email)
                
                # Check ledger first for cached result
                cached_result = await self.ledger.get_from_ledger(email, user_id)
                
                if cached_result:
                    # Use cached result from ledger
                    logger.info(f"Using cached result for {email}")
                    result = {
                        'status': VerificationStatus(cached_result['status']),
                        'provider': EmailProvider(cached_result['provider']),
                        'mx_records': cached_result.get('mx_records', []),
                        'response_time': cached_result.get('response_time', 0),
                        'smtp_response': cached_result.get('smtp_response', ''),
                        'is_catch_all': cached_result.get('is_catch_all', False),
                        'is_role_based': cached_result.get('is_role_based', False),
                        'is_disposable': cached_result.get('is_disposable', False),
                        'deliverability_score': cached_result.get('deliverability_score', 0),
                        'verified_at': datetime.now(timezone.utc),
                        'retry_count': 0,
                        'error_message': None
                    }
                else:
                    # Get domain for delay management
                    domain = email.split('@')[1] if '@' in email else ''
                    
                    # Apply domain-specific delay
                    domain_delay = settings.get('domain_delay', 2)
                    if domain and domain_delay > 0:
                        await self.apply_domain_delay(domain, domain_delay)
                    
                    # Apply global delay
                    if settings.get('global_delay', 0) > 0:
                        delay = settings['global_delay']
                        if settings.get('randomize_delays'):
                            delay = delay * random.uniform(0.5, 1.5)
                        await asyncio.sleep(delay)
                    
                    # Get proxy if enabled
                    proxy = None
                    if settings.get('use_proxies') and self.proxies:
                        proxy = self.get_next_proxy()
                    
                    # Verify email
                    result = await self.verifier.verify_email(email, use_api_fallback=True, proxy=proxy)
                    
                    # Save to ledger
                    await self.ledger.save_to_ledger(email, user_id, result, source="verification", job_id=job_id)
                
                # Create result document
                result_doc = {
                    'id': str(uuid.uuid4()),
                    'job_id': job_id,
                    'user_id': user_id,
                    'email': email,
                    'status': result['status'].value,
                    'provider': result['provider'].value,
                    'mx_records': result.get('mx_records', []),
                    'response_time': result.get('response_time', 0),
                    'smtp_response': result.get('smtp_response', ''),
                    'is_catch_all': result.get('is_catch_all', False),
                    'is_role_based': result.get('is_role_based', False),
                    'is_disposable': result.get('is_disposable', False),
                    'verified_at': result.get('verified_at', datetime.now(timezone.utc)).isoformat() if isinstance(result.get('verified_at'), datetime) else result.get('verified_at'),
                    'retry_count': result.get('retry_count', 0),
                    'max_retry_attempts': settings.get('max_retries', 3),
                    'error_message': result.get('error_message'),
                    'deliverability_score': result.get('deliverability_score', 0),
                    'from_cache': cached_result is not None  # NEW: Indicate if from cache
                }
                
                await self.db.verification_results.insert_one(result_doc)
                
                # Update counts
                job['processed_records'] += 1
                if result['status'] == VerificationStatus.VALID:
                    job['valid_count'] += 1
                elif result['status'] == VerificationStatus.INVALID:
                    job['invalid_count'] += 1
                elif result['status'] in [VerificationStatus.RISKY, VerificationStatus.DISPOSABLE]:
                    job['risky_count'] += 1
                elif result['status'] in [VerificationStatus.UNKNOWN, VerificationStatus.BLOCKED]:
                    job['unknown_count'] += 1
                    # Add to retry queue if auto-retry enabled and not from cache
                    if not cached_result and settings.get('auto_retry', True) and result.get('retry_count', 0) < settings.get('max_retries', 3):
                        await self.schedule_retry(result_doc, settings)
                
                # Update progress every 5 records for more responsive live counter
                if job['processed_records'] % 5 == 0:
                    await self.update_job_progress(job_id, user_id, current_email=email)
                
                # Emit individual result
                await self.socketio.emit('verification_result', result_doc, room=user_id)
                
            except Exception as e:
                logger.error(f"Error processing email {email}: {e}")
                job['error_count'] = job.get('error_count', 0) + 1
                continue
    
    async def process_finder_batch(self, job_id: str, user_id: str, records: List[Dict], settings: dict):
        """Process a batch of email finder requests"""
        if job_id not in self.active_jobs:
            return
        
        job_state = self.active_jobs[job_id]
        job = job_state['job']
        
        for record in records:
            try:
                if job['status'] == JobStatus.PAUSED:
                    break
                
                if job['status'] != JobStatus.PROCESSING:
                    break
                
                first_name = record.get('first_name', '')
                last_name = record.get('last_name', '')
                domain = record.get('domain', '')
                
                if not first_name or not last_name or not domain:
                    logger.warning(f"Skipping invalid record: {record}")
                    job['processed_records'] += 1
                    continue
                
                # Apply domain-specific delay
                domain_delay = settings.get('domain_delay', 2)
                if domain_delay > 0:
                    await self.apply_domain_delay(domain, domain_delay)
                
                # Apply global delay
                if settings.get('global_delay', 0) > 0:
                    delay = settings['global_delay']
                    if settings.get('randomize_delays'):
                        delay = delay * random.uniform(0.5, 1.5)
                    await asyncio.sleep(delay)
                
                # Get proxy if enabled
                proxy = None
                if settings.get('use_proxies') and self.proxies:
                    proxy = self.get_next_proxy()
                
                # Find email
                result = await self.finder.find_email(
                    first_name, 
                    last_name, 
                    domain,
                    stop_on_first_valid=settings.get('stop_on_first_valid', True),
                    proxy=proxy
                )
                
                # Create finder result document
                finder_doc = {
                    'id': str(uuid.uuid4()),
                    'job_id': job_id,
                    'user_id': user_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'domain': domain,
                    'found': result.get('found', False),
                    'email': result.get('email'),
                    'patterns_tested': result.get('patterns_tested', 0),
                    'search_time': result.get('search_time', 0),
                    'verified_at': datetime.now(timezone.utc).isoformat(),
                    'error_message': result.get('error_message'),
                    'deliverability_score': result.get('deliverability_score', 0)
                }
                
                # Add verification details if email was found
                if result.get('found') and result.get('all_results'):
                    found_result = next((r for r in result['all_results'] if r.get('email') == result['email']), None)
                    if found_result:
                        finder_doc['status'] = found_result.get('status', VerificationStatus.UNKNOWN).value if hasattr(found_result.get('status'), 'value') else str(found_result.get('status'))
                        finder_doc['provider'] = found_result.get('provider', '').value if hasattr(found_result.get('provider'), 'value') else str(found_result.get('provider'))
                
                await self.db.finder_results.insert_one(finder_doc)
                
                # Update counts
                job['processed_records'] += 1
                if result.get('found'):
                    job['found_count'] = job.get('found_count', 0) + 1
                    job['valid_count'] += 1
                else:
                    job['not_found_count'] = job.get('not_found_count', 0) + 1
                
                # Update progress every 5 records
                if job['processed_records'] % 5 == 0:
                    await self.update_job_progress(job_id, user_id)
                
                # Emit individual result
                await self.socketio.emit('finder_result', finder_doc, room=user_id)
                
            except Exception as e:
                logger.error(f"Error processing finder record {record}: {e}")
                job['error_count'] = job.get('error_count', 0) + 1
                continue
    
    async def schedule_retry(self, result_doc: dict, settings: dict):
        """Schedule a verification for retry"""
        retry_interval = settings.get('retry_interval', 5) * 60  # Convert to seconds
        retry_time = datetime.now(timezone.utc) + timedelta(seconds=retry_interval)
        
        await self.db.retry_queue.insert_one({
            'result_id': result_doc['id'],
            'job_id': result_doc['job_id'],
            'user_id': result_doc['user_id'],
            'email': result_doc['email'],
            'retry_count': result_doc.get('retry_count', 0) + 1,
            'scheduled_at': retry_time.isoformat(),
            'status': 'scheduled'
        })
    
    async def start_verification_job(self, job_id: str, user_id: str, emails: List[str], settings: dict):
        """Start a verification job with thread management"""
        try:
            # Load proxies if enabled
            if settings.get('use_proxies'):
                await self.load_proxies(user_id)
            
            # Initialize job state
            self.active_jobs[job_id] = {
                'job': {
                    'id': job_id,
                    'user_id': user_id,
                    'job_type': 'verification',
                    'status': JobStatus.PROCESSING,
                    'total_records': len(emails),
                    'processed_records': 0,
                    'valid_count': 0,
                    'invalid_count': 0,
                    'risky_count': 0,
                    'unknown_count': 0,
                    'error_count': 0,
                    'started_at': datetime.now(timezone.utc)
                },
                'active_threads': 0,
                'tasks': []
            }
            
            job_state = self.active_jobs[job_id]
            job = job_state['job']
            
            # Update job status in database
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": JobStatus.PROCESSING.value,
                    "started_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Split emails into batches based on thread count
            threads = min(settings.get('threads', 10), len(emails))
            batch_size = max(1, len(emails) // threads)
            batches = [emails[i:i + batch_size] for i in range(0, len(emails), batch_size)]
            
            # Create tasks for each batch
            tasks = []
            for batch in batches:
                task = asyncio.create_task(self.process_verification_batch(job_id, user_id, batch, settings))
                tasks.append(task)
                job_state['active_threads'] += 1
            
            job_state['tasks'] = tasks
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Mark job as completed
            job['status'] = JobStatus.COMPLETED
            
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": JobStatus.COMPLETED.value,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "processed_records": job['processed_records'],
                    "valid_count": job['valid_count'],
                    "invalid_count": job['invalid_count'],
                    "risky_count": job['risky_count'],
                    "unknown_count": job['unknown_count'],
                    "error_count": job.get('error_count', 0)
                }}
            )
            
            # Final progress update
            await self.update_job_progress(job_id, user_id)
            
            # Emit completion
            await self.socketio.emit('job_completed', {'job_id': job_id}, room=user_id)
            
            # Clean up
            del self.active_jobs[job_id]
            
        except Exception as e:
            logger.error(f"Error in verification job {job_id}: {e}")
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": JobStatus.FAILED.value,
                    "error_message": str(e)
                }}
            )
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    async def start_finder_job(self, job_id: str, user_id: str, records: List[Dict], settings: dict):
        """Start a finder job with thread management"""
        try:
            # Load proxies if enabled
            if settings.get('use_proxies'):
                await self.load_proxies(user_id)
            
            # Initialize job state
            self.active_jobs[job_id] = {
                'job': {
                    'id': job_id,
                    'user_id': user_id,
                    'job_type': 'finder',
                    'status': JobStatus.PROCESSING,
                    'total_records': len(records),
                    'processed_records': 0,
                    'valid_count': 0,
                    'found_count': 0,
                    'not_found_count': 0,
                    'error_count': 0,
                    'started_at': datetime.now(timezone.utc)
                },
                'active_threads': 0,
                'tasks': []
            }
            
            job_state = self.active_jobs[job_id]
            job = job_state['job']
            
            # Update job status in database
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": JobStatus.PROCESSING.value,
                    "started_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Split records into batches based on thread count
            threads = min(settings.get('threads', 10), len(records))
            batch_size = max(1, len(records) // threads)
            batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]
            
            # Create tasks for each batch
            tasks = []
            for batch in batches:
                task = asyncio.create_task(self.process_finder_batch(job_id, user_id, batch, settings))
                tasks.append(task)
                job_state['active_threads'] += 1
            
            job_state['tasks'] = tasks
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Mark job as completed
            job['status'] = JobStatus.COMPLETED
            
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": JobStatus.COMPLETED.value,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "processed_records": job['processed_records'],
                    "found_count": job.get('found_count', 0),
                    "not_found_count": job.get('not_found_count', 0),
                    "error_count": job.get('error_count', 0)
                }}
            )
            
            # Final progress update
            await self.update_job_progress(job_id, user_id)
            
            # Emit completion
            await self.socketio.emit('job_completed', {'job_id': job_id, 'job_type': 'finder'}, room=user_id)
            
            # Clean up
            del self.active_jobs[job_id]
            
        except Exception as e:
            logger.error(f"Error in finder job {job_id}: {e}")
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": JobStatus.FAILED.value,
                    "error_message": str(e)
                }}
            )
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    async def pause_job(self, job_id: str):
        """Pause a running job"""
        try:
            if job_id in self.active_jobs:
                self.active_jobs[job_id]['job']['status'] = JobStatus.PAUSED
                await self.db.verification_jobs.update_one(
                    {"id": job_id},
                    {"$set": {
                        "status": JobStatus.PAUSED.value,
                        "paused_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                logger.info(f"Job {job_id} paused")
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {e}")
    
    async def resume_job(self, job_id: str):
        """Resume a paused job"""
        try:
            if job_id in self.active_jobs:
                self.active_jobs[job_id]['job']['status'] = JobStatus.PROCESSING
                await self.db.verification_jobs.update_one(
                    {"id": job_id},
                    {"$set": {"status": JobStatus.PROCESSING.value}}
                )
                logger.info(f"Job {job_id} resumed")
        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {e}")
    
    async def stop_job(self, job_id: str):
        """Stop a running job"""
        try:
            if job_id in self.active_jobs:
                job_state = self.active_jobs[job_id]
                job_state['job']['status'] = JobStatus.FAILED
                
                # Cancel all tasks
                for task in job_state['tasks']:
                    task.cancel()
                
                await self.db.verification_jobs.update_one(
                    {"id": job_id},
                    {"$set": {"status": JobStatus.FAILED.value}}
                )
                
                del self.active_jobs[job_id]
                logger.info(f"Job {job_id} stopped")
        except Exception as e:
            logger.error(f"Error stopping job {job_id}: {e}")
    
    async def retry_failed_verifications(self, job_id: str, user_id: str):
        """Retry all failed/unknown verifications for a job"""
        try:
            # Get failed results
            failed_results = await self.db.verification_results.find({
                "job_id": job_id,
                "status": {"$in": [VerificationStatus.UNKNOWN.value, VerificationStatus.BLOCKED.value]},
                "retry_count": {"$lt": 3}
            }, {"_id": 0}).to_list(None)
            
            if not failed_results:
                logger.info(f"No failed verifications to retry for job {job_id}")
                return
            
            # Get job settings
            job = await self.db.verification_jobs.find_one({"id": job_id}, {"_id": 0})
            settings = job.get('settings', {})
            
            # Process retries
            for result in failed_results:
                try:
                    email = result['email']
                    retry_count = result.get('retry_count', 0) + 1
                    
                    # Verify again
                    new_result = await self.verifier.verify_email(
                        email, 
                        use_api_fallback=True, 
                        retry_count=retry_count
                    )
                    
                    # Update result
                    await self.db.verification_results.update_one(
                        {"id": result['id']},
                        {"$set": {
                            "status": new_result['status'].value,
                            "provider": new_result['provider'].value,
                            "smtp_response": new_result.get('smtp_response'),
                            "response_time": new_result.get('response_time'),
                            "retry_count": retry_count,
                            "last_retry_at": datetime.now(timezone.utc).isoformat(),
                            "error_message": new_result.get('error_message')
                        }}
                    )
                    
                    logger.info(f"Retried verification for {email}, new status: {new_result['status']}")
                    
                except Exception as e:
                    logger.error(f"Error retrying verification for {result.get('email')}: {e}")
                    continue
                
                # Small delay between retries
                await asyncio.sleep(1)
            
            logger.info(f"Completed retry for {len(failed_results)} failed verifications")
            
        except Exception as e:
            logger.error(f"Error in retry_failed_verifications: {e}")
