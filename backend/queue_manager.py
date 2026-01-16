import asyncio
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timezone
import time
from models import VerificationJob, VerificationResult, JobStatus, VerificationStatus
from email_verifier import EmailVerifier
from email_finder import EmailFinder
import random

class VerificationQueue:
    def __init__(self, db, socketio):
        self.db = db
        self.socketio = socketio
        self.verifier = EmailVerifier()
        self.finder = EmailFinder()
        self.active_jobs = {}  # job_id -> job_state
        self.proxies = []
        self.current_proxy_index = 0
    
    def get_next_proxy(self) -> Optional[dict]:
        """Get next proxy from rotation"""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy
    
    async def update_job_progress(self, job_id: str, user_id: str):
        """Update and broadcast job progress"""
        if job_id not in self.active_jobs:
            return
        
        job_state = self.active_jobs[job_id]
        job = job_state['job']
        
        # Calculate progress
        progress_percentage = (job['processed_records'] / job['total_records'] * 100) if job['total_records'] > 0 else 0
        
        # Calculate ETA
        if job['processed_records'] > 0 and job['started_at']:
            elapsed = (datetime.now(timezone.utc) - job['started_at']).total_seconds()
            avg_time_per_record = elapsed / job['processed_records']
            remaining_records = job['total_records'] - job['processed_records']
            eta_seconds = int(avg_time_per_record * remaining_records)
            job['eta_seconds'] = eta_seconds
        
        # Update database
        await self.db.verification_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "processed_records": job['processed_records'],
                "valid_count": job['valid_count'],
                "invalid_count": job['invalid_count'],
                "risky_count": job['risky_count'],
                "unknown_count": job['unknown_count'],
                "eta_seconds": job.get('eta_seconds')
            }}
        )
        
        # Broadcast progress via WebSocket
        await self.socketio.emit('job_progress', {
            'job_id': job_id,
            'status': job['status'],
            'total_records': job['total_records'],
            'processed_records': job['processed_records'],
            'valid_count': job['valid_count'],
            'invalid_count': job['invalid_count'],
            'risky_count': job['risky_count'],
            'unknown_count': job['unknown_count'],
            'progress_percentage': progress_percentage,
            'eta_seconds': job.get('eta_seconds'),
            'active_threads': job_state['active_threads']
        }, room=user_id)
    
    async def process_verification_batch(self, job_id: str, user_id: str, emails: List[str], settings: dict):
        """Process a batch of email verifications"""
        if job_id not in self.active_jobs:
            return
        
        job_state = self.active_jobs[job_id]
        job = job_state['job']
        
        for email in emails:
            if job['status'] == JobStatus.PAUSED:
                break
            
            if job['status'] != JobStatus.PROCESSING:
                break
            
            # Apply delays
            if settings.get('global_delay', 0) > 0:
                delay = settings['global_delay']
                if settings.get('randomize_delays'):
                    delay = delay * random.uniform(0.5, 1.5)
                await asyncio.sleep(delay)
            
            # Verify email
            result = await self.verifier.verify_email(email, use_api_fallback=True)
            
            # Create result document
            result_doc = {
                'id': str(uuid.uuid4()),
                'job_id': job_id,
                'user_id': user_id,
                'email': email,
                'status': result['status'].value,
                'provider': result['provider'].value,
                'mx_records': result['mx_records'],
                'response_time': result['response_time'],
                'smtp_response': result['smtp_response'],
                'is_catch_all': result['is_catch_all'],
                'is_role_based': result['is_role_based'],
                'is_disposable': result['is_disposable'],
                'verified_at': result['verified_at'].isoformat(),
                'retry_count': 0
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
            else:
                job['unknown_count'] += 1
            
            # Update progress every 10 records
            if job['processed_records'] % 10 == 0:
                await self.update_job_progress(job_id, user_id)
            
            # Emit individual result
            await self.socketio.emit('verification_result', result_doc, room=user_id)
    
    async def start_verification_job(self, job_id: str, user_id: str, emails: List[str], settings: dict):
        """Start a verification job with thread management"""
        # Initialize job state
        self.active_jobs[job_id] = {
            'job': {
                'id': job_id,
                'user_id': user_id,
                'status': JobStatus.PROCESSING,
                'total_records': len(emails),
                'processed_records': 0,
                'valid_count': 0,
                'invalid_count': 0,
                'risky_count': 0,
                'unknown_count': 0,
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
        threads = settings.get('threads', 10)
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
        job['processed_records'] = len(emails)
        
        await self.db.verification_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": JobStatus.COMPLETED.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "processed_records": len(emails),
                "valid_count": job['valid_count'],
                "invalid_count": job['invalid_count'],
                "risky_count": job['risky_count'],
                "unknown_count": job['unknown_count']
            }}
        )
        
        # Final progress update
        await self.update_job_progress(job_id, user_id)
        
        # Emit completion
        await self.socketio.emit('job_completed', {'job_id': job_id}, room=user_id)
        
        # Clean up
        del self.active_jobs[job_id]
    
    async def pause_job(self, job_id: str):
        """Pause a running job"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id]['job']['status'] = JobStatus.PAUSED
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": JobStatus.PAUSED.value}}
            )
    
    async def resume_job(self, job_id: str):
        """Resume a paused job"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id]['job']['status'] = JobStatus.PROCESSING
            await self.db.verification_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": JobStatus.PROCESSING.value}}
            )
    
    async def stop_job(self, job_id: str):
        """Stop a running job"""
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
