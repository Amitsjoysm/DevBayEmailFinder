from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

class VerificationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    RISKY = "risky"
    UNKNOWN = "unknown"
    PENDING = "pending"
    RETRY = "retry"
    DISPOSABLE = "disposable"
    BLOCKED = "blocked"

class EmailProvider(str, Enum):
    GMAIL = "Gmail"
    GSUITE = "GSuite"
    OUTLOOK = "Outlook"
    O365 = "O365"
    YAHOO = "Yahoo"
    ZOHO = "Zoho"
    AOL = "AOL"
    PROTONMAIL = "ProtonMail"
    FASTMAIL = "FastMail"
    REDIFFMAIL = "Rediffmail"
    CUSTOM = "Custom"

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

# User Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Verification Models
class EmailVerificationRequest(BaseModel):
    email: EmailStr

class EmailFinderRequest(BaseModel):
    first_name: str
    last_name: str
    domain: str
    patterns: Optional[List[str]] = None

class BulkVerificationRequest(BaseModel):
    emails: List[str]
    use_proxies: bool = False
    threads: int = 10
    delay: int = 0

class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    user_id: str
    row_index: int = 0  # Track original CSV row order
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    status: VerificationStatus
    provider: EmailProvider
    mx_records: Optional[List[str]] = []
    response_time: Optional[float] = 0
    smtp_response: Optional[str] = None
    is_catch_all: bool = False
    is_role_based: bool = False
    is_disposable: bool = False
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    max_retry_attempts: int = 3
    last_retry_at: Optional[datetime] = None
    error_message: Optional[str] = None
    patterns_tested: Optional[int] = None
    deliverability_score: int = 0  # 0-100 score

class VerificationJob(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    job_type: str  # "verification" or "finder"
    status: JobStatus
    total_records: int
    processed_records: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    risky_count: int = 0
    unknown_count: int = 0
    found_count: int = 0  # For finder jobs
    not_found_count: int = 0  # For finder jobs
    settings: Dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    eta_seconds: Optional[int] = None
    error_count: int = 0
    error_message: Optional[str] = None

class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    total_records: int
    processed_records: int
    valid_count: int
    invalid_count: int
    risky_count: int
    unknown_count: int
    found_count: int = 0
    not_found_count: int = 0
    progress_percentage: float
    eta_seconds: Optional[int] = None
    active_threads: int
    error_count: int = 0

# Bulk Finder Models
class BulkFinderRequest(BaseModel):
    records: List[Dict[str, str]]  # [{first_name, last_name, domain}]
    threads: int = 10
    stop_on_first_valid: bool = True

class FinderResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    user_id: str
    row_index: int = 0  # Track original CSV row order
    first_name: str
    last_name: str
    domain: str
    found: bool
    email: Optional[str] = None
    status: Optional[VerificationStatus] = None
    provider: Optional[EmailProvider] = None
    patterns_tested: int = 0
    search_time: float = 0
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    deliverability_score: int = 0  # 0-100 score

# Proxy Models
class ProxyCreate(BaseModel):
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: str = "http"  # http, https, socks4, socks5

class Proxy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: str = "http"
    is_active: bool = True
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Settings Models
class UserSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    threads: int = 10
    batch_size: int = 100
    global_delay: int = 0
    domain_delay: int = 2
    server_delay: int = 5
    randomize_delays: bool = True
    max_retries: int = 3
    retry_interval: int = 5
    auto_retry: bool = True
    use_proxies: bool = False
    stop_on_first_valid: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Export Models
class ExportRequest(BaseModel):
    job_id: str
    format: str = "csv"  # csv, xlsx, json
    filter_status: Optional[List[VerificationStatus]] = None
    filter_provider: Optional[List[EmailProvider]] = None

# Email Ledger Model - Unified history for all verifications and finds
class EmailLedger(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr  # Unique index
    status: VerificationStatus
    provider: EmailProvider
    mx_records: Optional[List[str]] = []
    response_time: Optional[float] = 0
    smtp_response: Optional[str] = None
    is_catch_all: bool = False
    is_role_based: bool = False
    is_disposable: bool = False
    deliverability_score: int = 0
    
    # Source tracking
    source: str  # "verification" or "finder"
    first_verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verification_count: int = 1
    
    # Finder-specific metadata (optional)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    domain: Optional[str] = None
    patterns_tested: Optional[int] = None
    
    # Additional metadata
    user_id: str
    last_job_id: Optional[str] = None


# Domain Pattern Cache Model
class DomainPatternCache(BaseModel):
    """Persistent cache for successful email patterns per domain"""
    model_config = ConfigDict(extra="ignore")
    
    domain: str  # e.g., "example.com"
    pattern: str  # e.g., "{first}.{last}@{domain}"
    success_count: int = 1
    confidence_score: int = 50  # 0-100 based on success_count
    first_success_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_success_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by_user_id: str
    last_user_id: str
    last_example: Optional[Dict] = None  # {email, first_name, last_name}
    pattern_changed_at: Optional[datetime] = None
