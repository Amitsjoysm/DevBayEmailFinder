# Email Verification & Finder Tool

A comprehensive email verification and finder tool capable of handling 10K+ records with retry mechanisms, bulk operations, and production-ready features.

## Features

### ✅ Email Verification
- **Single Email Verification**: Verify individual emails with real-time results
- **Bulk Email Verification**: Upload CSV files to verify thousands of emails
- **Smart Verification**: SMTP + DNS + MX record verification with provider detection
- **Retry Mechanism**: Automatic and manual retry for failed verifications
- **Job Controls**: Pause, resume, and stop verification jobs anytime

### 🔍 Email Finder
- **Pattern-Based Finding**: Tests 10 common email patterns
- **Single Email Finder**: Find individual emails by name and domain
- **Bulk Email Finder**: Upload CSV to find emails for multiple records
- **Smart Stop**: Stops on first valid email match

### 📊 Advanced Features
- Real-time progress tracking with WebSocket updates
- Success rate indicators
- ETA calculations
- Results filtering by status and provider
- Pagination for large result sets
- Export results as CSV or JSON
- Retry count and timestamp tracking
- Comprehensive error handling and display

## Getting Started

### CSV Format Requirements

#### For Bulk Verification
Your CSV file must contain an `email` column:

```csv
email
john@example.com
jane@company.com
test@organization.org
```

**Download Sample**: Use the "Download Sample CSV" button in the Bulk Verification section

#### For Bulk Finder
Your CSV file must contain three columns: `first_name`, `last_name`, and `domain`:

```csv
first_name,last_name,domain
John,Doe,example.com
Jane,Smith,company.com
Mike,Johnson,organization.org
```

**Download Sample**: Use the "Download Sample CSV" button in the Bulk Email Finder section

### CSV Guidelines
- First row must be the header row
- Maximum recommended file size: 10,000 rows for verification, 5,000 for finder
- Domain should be without http:// or www (e.g., example.com)
- Files must be in .csv format
- UTF-8 encoding recommended

## Usage Instructions

### Single Email Verification
1. Navigate to the **Verifier** page
2. Enter an email address
3. Click "Verify"
4. View detailed results including status, provider, response time, and more

### Bulk Email Verification
1. Navigate to the **Verifier** page
2. Click "Show Instructions" to view format requirements
3. Download sample CSV if needed
4. Upload your CSV file (validated automatically)
5. Adjust threads (1-100) and delay (0-30s) as needed
6. Click "Start Verification"
7. Monitor real-time progress with:
   - Job status indicator
   - Progress bar with percentage
   - Valid/Invalid/Risky/Unknown counts
   - Success rate
   - ETA
8. Use job controls:
   - **Pause**: Temporarily pause the job
   - **Resume**: Continue a paused job
   - **Stop**: Permanently stop the job
9. After completion:
   - **Retry Failed**: Retry all unknown/blocked verifications
   - **Export CSV/JSON**: Download results
10. View detailed results with pagination and filtering

### Single Email Finder
1. Navigate to the **Finder** page
2. Enter first name, last name, and domain
3. Click "Find Email"
4. View found email with verification details

### Bulk Email Finder
1. Navigate to the **Finder** page
2. Click "Show Instructions" to view format requirements
3. Download sample CSV if needed
4. Upload your CSV file (validated automatically)
5. Adjust threads (1-50) as needed
6. Click "Start Finding"
7. Monitor real-time progress with:
   - Job status indicator
   - Progress bar
   - Found/Not Found counts
   - Success rate
   - ETA
8. Use job controls (Pause/Resume/Stop)
9. Export results as CSV or JSON
10. View detailed results with pagination

## Understanding Results

### Verification Statuses
- **Valid**: Email exists and is deliverable
- **Invalid**: Email does not exist
- **Risky**: Email exists but may be a catch-all or temporary
- **Unknown**: Unable to verify (may need retry)
- **Disposable**: Temporary/disposable email provider
- **Blocked**: Verification blocked (IP may be rate-limited)

### Email Providers Detected
- Gmail / GSuite
- Outlook / Office 365
- Yahoo
- Zoho
- AOL
- ProtonMail
- FastMail
- Rediffmail
- Custom (other providers)

## Performance Tips

### For Best Results
1. **Start with lower threads** (10-20) and increase gradually
2. **Use delays** to avoid rate limiting (2-5 seconds recommended)
3. **Monitor error counts** during processing
4. **Use retry mechanism** for unknown results
5. **Export results regularly** for large jobs

### Troubleshooting
- **High error count**: Reduce threads and increase delay
- **Many unknown results**: Use retry after job completion
- **Blocked status**: Your IP may be rate-limited; wait and retry later
- **CSV upload fails**: Check format matches requirements exactly
- **No results showing**: Check filters (Status/Provider) are not too restrictive

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user

### Verification
- `POST /api/verify/single` - Verify single email
- `POST /api/verify/upload` - Upload CSV for bulk verification
- `GET /api/results/{job_id}` - Get verification results
- `GET /api/results/{job_id}/export` - Export results

### Finder
- `POST /api/find/single` - Find single email
- `POST /api/find/upload` - Upload CSV for bulk finder
- `GET /api/finder-results/{job_id}` - Get finder results

### Job Management
- `GET /api/jobs` - List all jobs
- `GET /api/jobs/{job_id}` - Get job details
- `POST /api/jobs/{job_id}/pause` - Pause job
- `POST /api/jobs/{job_id}/resume` - Resume job
- `POST /api/jobs/{job_id}/stop` - Stop job
- `POST /api/jobs/{job_id}/retry` - Retry failed verifications

## Technical Stack

### Backend
- **FastAPI**: Modern Python web framework
- **MongoDB**: Document database for storage
- **Socket.IO**: Real-time WebSocket communication
- **DNS/SMTP**: Email verification protocols

### Frontend
- **React**: UI framework
- **Tailwind CSS**: Styling
- **Socket.IO Client**: Real-time updates
- **Papa Parse**: CSV parsing

## Support

For issues or questions:
1. Check CSV format matches requirements
2. Review error messages in results table
3. Use retry mechanism for unknown results
4. Check job status indicators
5. Monitor error count during processing

## Recent Updates

### Version 1.1 - Production Ready
- ✅ CSV validation with helpful error messages
- ✅ Downloadable sample CSV templates
- ✅ Comprehensive format instructions
- ✅ Pagination for large result sets (50 per page)
- ✅ Enhanced error handling and display
- ✅ Retry count and timestamp tracking
- ✅ Success rate indicators
- ✅ Button tooltips and help text
- ✅ Loading states throughout
- ✅ Job status indicators with animations
- ✅ ETA display with better formatting
- ✅ Empty states with helpful messages
- ✅ Improved job controls on both Verifier and Finder

---

**Built with ❤️ for reliable email verification and finding**
