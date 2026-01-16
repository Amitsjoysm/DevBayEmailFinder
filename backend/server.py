from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import socketio
import os
import logging
from pathlib import Path
from typing import List, Optional
import csv
import io
import json
from datetime import datetime, timezone
import uuid

from models import (
    User, UserCreate, UserLogin, UserResponse, Token,
    VerificationJob, VerificationResult, JobProgress, JobStatus,
    EmailVerificationRequest, EmailFinderRequest, BulkVerificationRequest,
    Proxy, ProxyCreate, UserSettings, ExportRequest,
    VerificationStatus, EmailProvider, FinderResult, BulkFinderRequest, EmailLedger
)
from auth import (
    get_password_hash, verify_password, create_access_token, get_current_user
)
from email_verifier import EmailVerifier
from email_finder import EmailFinder
from queue_manager import VerificationQueue
from ledger_service import LedgerService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Socket.IO setup
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=False
)

# Create the main app
app = FastAPI()

# Create Socket.IO ASGI app
socket_app = socketio.ASGIApp(sio, app)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize services
verifier = EmailVerifier()
finder = EmailFinder()
queue_manager = VerificationQueue(db, sio)

# Socket.IO events
@sio.event
async def connect(sid, environ):
    logging.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logging.info(f"Client disconnected: {sid}")

@sio.event
async def join_room(sid, data):
    """Join user-specific room for updates"""
    room = data.get('user_id')
    if room:
        sio.enter_room(sid, room)
        logging.info(f"Client {sid} joined room {room}")

# Authentication endpoints
@api_router.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name
    )
    
    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    
    await db.users.insert_one(user_dict)
    
    # Create default settings
    settings = UserSettings(user_id=user.id)
    settings_dict = settings.model_dump()
    settings_dict['updated_at'] = settings_dict['updated_at'].isoformat()
    await db.user_settings.insert_one(settings_dict)
    
    # Create token
    token = create_access_token(data={"sub": user.id, "email": user.email})
    
    return Token(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            created_at=user.created_at
        )
    )

@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    # Find user
    user_dict = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_dict:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not verify_password(credentials.password, user_dict['hashed_password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create token
    token = create_access_token(data={"sub": user_dict['id'], "email": user_dict['email']})
    
    return Token(
        access_token=token,
        user=UserResponse(
            id=user_dict['id'],
            email=user_dict['email'],
            full_name=user_dict.get('full_name'),
            role=user_dict['role'],
            created_at=datetime.fromisoformat(user_dict['created_at'])
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    user_dict = await db.users.find_one({"id": current_user['id']}, {"_id": 0})
    if not user_dict:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user_dict['id'],
        email=user_dict['email'],
        full_name=user_dict.get('full_name'),
        role=user_dict['role'],
        created_at=datetime.fromisoformat(user_dict['created_at'])
    )

# Email verification endpoints
@api_router.post("/verify/single")
async def verify_single_email(
    request: EmailVerificationRequest,
    current_user: dict = Depends(get_current_user)
):
    result = await verifier.verify_email(request.email, use_api_fallback=True)
    return result

@api_router.post("/verify/bulk")
async def verify_bulk_emails(
    background_tasks: BackgroundTasks,
    emails: List[str],
    threads: int = 10,
    delay: int = 0,
    current_user: dict = Depends(get_current_user)
):
    # Get user settings
    settings_dict = await db.user_settings.find_one({"user_id": current_user['id']}, {"_id": 0})
    if not settings_dict:
        settings_dict = UserSettings(user_id=current_user['id']).model_dump()
    
    # Override with request params
    settings_dict['threads'] = threads
    settings_dict['global_delay'] = delay
    
    # Create job
    job = VerificationJob(
        user_id=current_user['id'],
        job_type="verification",
        status=JobStatus.QUEUED,
        total_records=len(emails),
        settings=settings_dict
    )
    
    job_dict = job.model_dump()
    job_dict['created_at'] = job_dict['created_at'].isoformat()
    
    await db.verification_jobs.insert_one(job_dict)
    
    # Start processing in background
    background_tasks.add_task(
        queue_manager.start_verification_job,
        job.id,
        current_user['id'],
        emails,
        settings_dict
    )
    
    return {"job_id": job.id, "status": "queued", "total_records": len(emails)}

@api_router.post("/verify/upload")
async def upload_verification_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    threads: int = 10,
    delay: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """
    Upload CSV for bulk verification with production-ready error handling
    - Max 5000 records
    - Comprehensive validation
    - Error tracking
    """
    try:
        # Validate file extension
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file format. Only CSV files are allowed."
            )
        
        # Read CSV with size limit (approx 5MB for 5K records)
        max_size = 5 * 1024 * 1024  # 5MB
        contents = await file.read()
        
        if len(contents) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum file size is 5MB (approximately 5000 records)."
            )
        
        if len(contents) == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file. Please upload a CSV with email addresses."
            )
        
        # Parse CSV with error handling
        try:
            csv_content = contents.decode('utf-8')
        except UnicodeDecodeError:
            try:
                csv_content = contents.decode('latin-1')
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to decode file. Please ensure it's a valid UTF-8 or Latin-1 encoded CSV."
                )
        
        # Validate CSV structure
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Check if required column exists
            if csv_reader.fieldnames is None:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid CSV format. File appears to be empty or corrupted."
                )
            
            has_email_column = any(
                col.lower().strip() in ['email', 'e-mail', 'emails'] 
                for col in csv_reader.fieldnames
            )
            
            if not has_email_column:
                raise HTTPException(
                    status_code=400,
                    detail=f"CSV must contain an 'email' column. Found columns: {', '.join(csv_reader.fieldnames)}"
                )
            
        except csv.Error as e:
            raise HTTPException(
                status_code=400,
                detail=f"CSV parsing error: {str(e)}. Please ensure proper CSV formatting."
            )
        
        # Extract emails with validation
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        emails = []
        invalid_rows = []
        
        for idx, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Try common column names
                email = row.get('email') or row.get('Email') or row.get('EMAIL') or row.get('e-mail') or row.get('E-mail')
                
                if email and email.strip():
                    email_clean = email.strip()
                    
                    # Basic email format validation
                    if '@' in email_clean and '.' in email_clean.split('@')[-1]:
                        emails.append(email_clean)
                    else:
                        invalid_rows.append(f"Row {idx}: Invalid email format '{email_clean}'")
                        
            except Exception as e:
                invalid_rows.append(f"Row {idx}: Error processing row - {str(e)}")
                continue
            
            # Stop at 5000 records limit
            if len(emails) >= 5000:
                logging.warning(f"CSV contains more than 5000 records. Processing first 5000 only.")
                break
        
        if not emails:
            error_msg = "No valid emails found in CSV."
            if invalid_rows:
                error_msg += f" Issues found:\n" + "\n".join(invalid_rows[:10])
                if len(invalid_rows) > 10:
                    error_msg += f"\n... and {len(invalid_rows) - 10} more errors"
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Log warnings for invalid rows
        if invalid_rows:
            logging.warning(f"Found {len(invalid_rows)} invalid rows in CSV upload by user {current_user['id']}")
        
        # Get user settings
        settings_dict = await db.user_settings.find_one({"user_id": current_user['id']}, {"_id": 0})
        if not settings_dict:
            settings_dict = UserSettings(user_id=current_user['id']).model_dump()
        
        settings_dict['threads'] = min(threads, 100)  # Cap at 100
        settings_dict['global_delay'] = max(0, min(delay, 30))  # 0-30 seconds
        
        # Create job
        job = VerificationJob(
            user_id=current_user['id'],
            job_type="verification",
            status=JobStatus.QUEUED,
            total_records=len(emails),
            settings=settings_dict
        )
        
        job_dict = job.model_dump()
        job_dict['created_at'] = job_dict['created_at'].isoformat()
        
        await db.verification_jobs.insert_one(job_dict)
        
        # Start processing in background
        background_tasks.add_task(
            queue_manager.start_verification_job,
            job.id,
            current_user['id'],
            emails,
            settings_dict
        )
        
        response = {
            "job_id": job.id, 
            "status": "queued", 
            "total_records": len(emails)
        }
        
        if invalid_rows:
            response["warnings"] = {
                "invalid_rows_count": len(invalid_rows),
                "message": f"Skipped {len(invalid_rows)} invalid rows. Processing {len(emails)} valid emails."
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in CSV upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Server error while processing CSV: {str(e)}"
        )

# Email finder endpoints
@api_router.post("/find/single")
async def find_single_email(
    request: EmailFinderRequest,
    current_user: dict = Depends(get_current_user)
):
    result = await finder.find_email(
        request.first_name,
        request.last_name,
        request.domain,
        patterns=request.patterns,
        stop_on_first_valid=True
    )
    return result

@api_router.post("/find/upload")
async def upload_finder_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    threads: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """
    Upload CSV for bulk email finder with production-ready error handling
    - Max 5000 records
    - Comprehensive validation
    - Error tracking
    """
    try:
        # Validate file extension
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Only CSV files are allowed."
            )
        
        # Read CSV with size limit
        max_size = 5 * 1024 * 1024  # 5MB
        contents = await file.read()
        
        if len(contents) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum file size is 5MB (approximately 5000 records)."
            )
        
        if len(contents) == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file. Please upload a CSV with name and domain data."
            )
        
        # Parse CSV with error handling
        try:
            csv_content = contents.decode('utf-8')
        except UnicodeDecodeError:
            try:
                csv_content = contents.decode('latin-1')
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to decode file. Please ensure it's a valid UTF-8 or Latin-1 encoded CSV."
                )
        
        # Validate CSV structure
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            if csv_reader.fieldnames is None:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid CSV format. File appears to be empty or corrupted."
                )
            
            # Check for required columns
            fieldnames_lower = [col.lower().strip().replace(' ', '_') for col in csv_reader.fieldnames]
            
            has_first_name = any('first' in col and 'name' in col for col in fieldnames_lower)
            has_last_name = any('last' in col and 'name' in col for col in fieldnames_lower)
            has_domain = any('domain' in col for col in fieldnames_lower)
            
            if not (has_first_name and has_last_name and has_domain):
                raise HTTPException(
                    status_code=400,
                    detail=f"CSV must contain 'first_name', 'last_name', and 'domain' columns. Found: {', '.join(csv_reader.fieldnames)}"
                )
                
        except csv.Error as e:
            raise HTTPException(
                status_code=400,
                detail=f"CSV parsing error: {str(e)}. Please ensure proper CSV formatting."
            )
        
        # Extract records with validation
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        records = []
        invalid_rows = []
        
        for idx, row in enumerate(csv_reader, start=2):
            try:
                first_name = (row.get('first_name') or row.get('FirstName') or 
                            row.get('First Name') or row.get('firstname') or row.get('First_Name'))
                last_name = (row.get('last_name') or row.get('LastName') or 
                           row.get('Last Name') or row.get('lastname') or row.get('Last_Name'))
                domain = (row.get('domain') or row.get('Domain') or 
                         row.get('company_domain') or row.get('Company Domain'))
                
                if first_name and last_name and domain:
                    first_clean = first_name.strip()
                    last_clean = last_name.strip()
                    domain_clean = domain.strip().lower()
                    
                    # Remove protocol and www from domain
                    domain_clean = domain_clean.replace('http://', '').replace('https://', '').replace('www.', '')
                    
                    # Basic domain validation
                    if '.' in domain_clean and len(domain_clean) > 3:
                        records.append({
                            'first_name': first_clean,
                            'last_name': last_clean,
                            'domain': domain_clean
                        })
                    else:
                        invalid_rows.append(f"Row {idx}: Invalid domain format '{domain}'")
                else:
                    missing_fields = []
                    if not first_name:
                        missing_fields.append('first_name')
                    if not last_name:
                        missing_fields.append('last_name')
                    if not domain:
                        missing_fields.append('domain')
                    invalid_rows.append(f"Row {idx}: Missing required fields: {', '.join(missing_fields)}")
                    
            except Exception as e:
                invalid_rows.append(f"Row {idx}: Error processing row - {str(e)}")
                continue
            
            # Stop at 5000 records limit
            if len(records) >= 5000:
                logging.warning(f"CSV contains more than 5000 records. Processing first 5000 only.")
                break
        
        if not records:
            error_msg = "No valid records found in CSV."
            if invalid_rows:
                error_msg += f" Issues found:\n" + "\n".join(invalid_rows[:10])
                if len(invalid_rows) > 10:
                    error_msg += f"\n... and {len(invalid_rows) - 10} more errors"
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Log warnings for invalid rows
        if invalid_rows:
            logging.warning(f"Found {len(invalid_rows)} invalid rows in finder CSV upload by user {current_user['id']}")
        
        # Get user settings
        settings_dict = await db.user_settings.find_one({"user_id": current_user['id']}, {"_id": 0})
        if not settings_dict:
            settings_dict = UserSettings(user_id=current_user['id']).model_dump()
        
        settings_dict['threads'] = min(threads, 50)  # Cap at 50 for finder
        
        # Create job
        job = VerificationJob(
            user_id=current_user['id'],
            job_type="finder",
            status=JobStatus.QUEUED,
            total_records=len(records),
            settings=settings_dict
        )
        
        job_dict = job.model_dump()
        job_dict['created_at'] = job_dict['created_at'].isoformat()
        
        await db.verification_jobs.insert_one(job_dict)
        
        # Start processing in background
        background_tasks.add_task(
            queue_manager.start_finder_job,
            job.id,
            current_user['id'],
            records,
            settings_dict
        )
        
        response = {
            "job_id": job.id,
            "status": "queued",
            "total_records": len(records)
        }
        
        if invalid_rows:
            response["warnings"] = {
                "invalid_rows_count": len(invalid_rows),
                "message": f"Skipped {len(invalid_rows)} invalid rows. Processing {len(records)} valid records."
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in finder CSV upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Server error while processing CSV: {str(e)}"
        )
    
    return {"job_id": job.id, "status": "queued", "total_records": len(records)}

# Job management endpoints
@api_router.get("/jobs")
async def get_jobs(
    current_user: dict = Depends(get_current_user)
):
    jobs = await db.verification_jobs.find(
        {"user_id": current_user['id']},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    return jobs

@api_router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    job = await db.verification_jobs.find_one(
        {"id": job_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job

@api_router.post("/jobs/{job_id}/pause")
async def pause_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    await queue_manager.pause_job(job_id)
    return {"status": "paused"}

@api_router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    await queue_manager.resume_job(job_id)
    return {"status": "resumed"}

@api_router.post("/jobs/{job_id}/stop")
async def stop_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    await queue_manager.stop_job(job_id)
    return {"status": "stopped"}

@api_router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Retry all failed/unknown verifications in a job"""
    # Verify job ownership
    job = await db.verification_jobs.find_one(
        {"id": job_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Start retry in background
    background_tasks.add_task(
        queue_manager.retry_failed_verifications,
        job_id,
        current_user['id']
    )
    
    return {"status": "retry_started", "job_id": job_id}

# Results endpoints
@api_router.get("/results/{job_id}")
async def get_results(
    job_id: str,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    # Verify job ownership
    job = await db.verification_jobs.find_one(
        {"id": job_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build filter
    filter_query = {"job_id": job_id}
    if status:
        filter_query["status"] = status
    if provider:
        filter_query["provider"] = provider
    
    # Get results
    results = await db.verification_results.find(
        filter_query,
        {"_id": 0}
    ).skip(skip).limit(limit).to_list(limit)
    
    # Get total count
    total = await db.verification_results.count_documents(filter_query)
    
    return {
        "results": results,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@api_router.get("/finder-results/{job_id}")
async def get_finder_results(
    job_id: str,
    skip: int = 0,
    limit: int = 100,
    found: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get finder results for a job"""
    # Verify job ownership
    job = await db.verification_jobs.find_one(
        {"id": job_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build filter
    filter_query = {"job_id": job_id}
    if found is not None:
        filter_query["found"] = found
    
    # Get results
    results = await db.finder_results.find(
        filter_query,
        {"_id": 0}
    ).skip(skip).limit(limit).to_list(limit)
    
    # Get total count
    total = await db.finder_results.count_documents(filter_query)
    
    return {
        "results": results,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@api_router.get("/results/{job_id}/export")
async def export_results(
    job_id: str,
    format: str = "csv",
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    # Verify job ownership
    job = await db.verification_jobs.find_one(
        {"id": job_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Determine collection based on job type
    job_type = job.get('job_type', 'verification')
    
    # Build filter
    filter_query = {"job_id": job_id}
    if status:
        filter_query["status"] = status
    
    # Get all results from appropriate collection
    if job_type == 'finder':
        results = await db.finder_results.find(filter_query, {"_id": 0}).to_list(None)
    else:
        results = await db.verification_results.find(filter_query, {"_id": 0}).to_list(None)
    
    if format == "json":
        return results
    elif format == "csv":
        # Create CSV
        output = io.StringIO()
        if results:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=verification_results_{job_id}.csv"
            }
        )

# Settings endpoints
@api_router.get("/settings")
async def get_settings(
    current_user: dict = Depends(get_current_user)
):
    settings = await db.user_settings.find_one(
        {"user_id": current_user['id']},
        {"_id": 0}
    )
    
    if not settings:
        settings = UserSettings(user_id=current_user['id']).model_dump()
        settings['updated_at'] = settings['updated_at'].isoformat()
        await db.user_settings.insert_one(settings)
    
    return settings

@api_router.put("/settings")
async def update_settings(
    settings: UserSettings,
    current_user: dict = Depends(get_current_user)
):
    settings.user_id = current_user['id']
    settings.updated_at = datetime.now(timezone.utc)
    
    settings_dict = settings.model_dump()
    settings_dict['updated_at'] = settings_dict['updated_at'].isoformat()
    
    await db.user_settings.update_one(
        {"user_id": current_user['id']},
        {"$set": settings_dict},
        upsert=True
    )
    
    return settings_dict

# Proxy endpoints
@api_router.post("/proxies")
async def add_proxy(
    proxy: ProxyCreate,
    current_user: dict = Depends(get_current_user)
):
    proxy_obj = Proxy(
        user_id=current_user['id'],
        **proxy.model_dump()
    )
    
    proxy_dict = proxy_obj.model_dump()
    proxy_dict['created_at'] = proxy_dict['created_at'].isoformat()
    
    # Insert without returning the MongoDB _id
    await db.proxies.insert_one(proxy_dict.copy())
    
    # Return clean proxy dict without _id
    return proxy_dict

@api_router.get("/proxies")
async def get_proxies(
    current_user: dict = Depends(get_current_user)
):
    proxies = await db.proxies.find(
        {"user_id": current_user['id']},
        {"_id": 0}
    ).to_list(None)
    
    return proxies

@api_router.delete("/proxies/{proxy_id}")
async def delete_proxy(
    proxy_id: str,
    current_user: dict = Depends(get_current_user)
):
    result = await db.proxies.delete_one({
        "id": proxy_id,
        "user_id": current_user['id']
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    return {"status": "deleted"}

# Analytics endpoints
@api_router.get("/analytics/dashboard")
async def get_dashboard_analytics(
    current_user: dict = Depends(get_current_user)
):
    # Get all user jobs
    jobs = await db.verification_jobs.find(
        {"user_id": current_user['id']},
        {"_id": 0}
    ).to_list(None)
    
    # Calculate totals
    total_verified = sum(job.get('processed_records', 0) for job in jobs)
    total_valid = sum(job.get('valid_count', 0) for job in jobs)
    total_invalid = sum(job.get('invalid_count', 0) for job in jobs)
    total_risky = sum(job.get('risky_count', 0) for job in jobs)
    
    # Get provider distribution
    provider_pipeline = [
        {"$match": {"user_id": current_user['id']}},
        {"$group": {"_id": "$provider", "count": {"$sum": 1}}}
    ]
    provider_stats = await db.verification_results.aggregate(provider_pipeline).to_list(None)
    
    return {
        "total_verified": total_verified,
        "total_valid": total_valid,
        "total_invalid": total_invalid,
        "total_risky": total_risky,
        "success_rate": (total_valid / total_verified * 100) if total_verified > 0 else 0,
        "provider_distribution": provider_stats,
        "recent_jobs": jobs[:5]
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
