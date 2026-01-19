# Email Verification Tool - Production Deployment Guide

## Quick Start

```bash
# 1. Upload the production_build directory to your server
scp -r production_build/ user@seo.mj.publicvm.com:/var/www/seo.mj.publicvm.com/

# 2. Install backend dependencies
cd /var/www/seo.mj.publicvm.com/backend
pip install -r requirements.txt

# 3. Run quick start script
cd /var/www/seo.mj.publicvm.com
chmod +x quick_start.sh
./quick_start.sh
```

## Detailed Deployment Steps

### 1. Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Python 3.9+
- Nginx
- MongoDB
- SSL certificates (Let's Encrypt recommended)

### 2. Backend Setup

```bash
cd /var/www/seo.mj.publicvm.com/backend

# Install dependencies
pip install -r requirements.txt

# Verify configuration
cat .env

# Test backend manually
uvicorn server:socket_app --host 0.0.0.0 --port 9010
# Press Ctrl+C after verification
```

### 3. Systemd Service

Copy the systemd service file:

```bash
sudo cp email-verifier-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-verifier-backend
sudo systemctl start email-verifier-backend
sudo systemctl status email-verifier-backend
```

### 4. Nginx Configuration

```bash
# Copy nginx config
sudo cp nginx_seo.mj.publicvm.com.conf /etc/nginx/sites-available/seo.mj.publicvm.com

# Enable site
sudo ln -sf /etc/nginx/sites-available/seo.mj.publicvm.com /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 5. SSL/TLS with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d seo.mj.publicvm.com

# Test auto-renewal
sudo certbot renew --dry-run
```

### 6. MongoDB Setup

```bash
# Ensure MongoDB is running
sudo systemctl status mongodb

# Create production database (optional)
mongo
> use email_verifier_production
> db.createUser({
    user: "email_verifier",
    pwd: "your_secure_password",
    roles: [{role: "readWrite", db: "email_verifier_production"}]
})
> exit
```

## Configuration Files

### Backend (.env)
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=email_verifier_production
CORS_ORIGINS=https://seo.mj.publicvm.com
JWT_SECRET_KEY=<your-secure-key>
ENVIRONMENT=production
```

### Frontend Build
Already configured for `https://seo.mj.publicvm.com`

## Architecture

```
Internet (HTTPS/443)
        ↓
┌────────────────────────┐
│ seo.mj.publicvm.com    │
│ Nginx (Port 443)       │
│ - Serves frontend      │
│ - Proxies /api         │
│ - Proxies /socket.io   │
└───────────┬────────────┘
            │
            ↓ (localhost only)
┌────────────────────────┐
│ Backend (Port 9010)    │
│ - Uvicorn + FastAPI    │
│ - Socket.io server     │
│ - 4 workers            │
│ - NOT exposed          │
└───────────┬────────────┘
            │
            ↓
┌────────────────────────┐
│ MongoDB (27017)        │
└────────────────────────┘
```

## Verification

```bash
# Check backend is running
curl http://localhost:9010/api/docs

# Check frontend
curl https://seo.mj.publicvm.com

# View logs
journalctl -u email-verifier-backend -f
tail -f /var/log/nginx/seo.mj.publicvm.com.access.log
```

## Troubleshooting

### Backend not starting
```bash
journalctl -u email-verifier-backend -n 100
```

### Port already in use
```bash
sudo lsof -i :9010
# Kill the process if needed
```

### MongoDB connection errors
```bash
sudo systemctl status mongodb
mongo --eval 'db.runCommand({ ping: 1 })'
```

### Nginx errors
```bash
tail -f /var/log/nginx/error.log
sudo nginx -t
```

## Monitoring

```bash
# Watch backend logs
journalctl -u email-verifier-backend -f

# Monitor resource usage
htop

# Check disk space
df -h

# Monitor MongoDB
mongo --eval 'db.stats()'
```

## Maintenance

### Update application
```bash
# Stop backend
sudo systemctl stop email-verifier-backend

# Update files
cd /var/www/seo.mj.publicvm.com
# Upload new files

# Restart backend
sudo systemctl start email-verifier-backend
```

### Backup database
```bash
mongodump --db email_verifier_production --out /backup/$(date +%Y%m%d)
```

### Restore database
```bash
mongorestore --db email_verifier_production /backup/20250119/email_verifier_production
```

## Security Checklist

- [ ] Port 9010 NOT accessible from internet (firewall rule)
- [ ] SSL/TLS certificates installed and valid
- [ ] JWT secret is unique and secure (not default)
- [ ] MongoDB authentication enabled (if needed)
- [ ] Nginx security headers configured
- [ ] Regular security updates applied
- [ ] Backups configured and tested

## Performance Tuning

### Nginx
```nginx
worker_processes auto;
worker_connections 1024;
```

### Uvicorn Workers
Adjust based on CPU cores:
```bash
# For 4-core CPU
uvicorn server:socket_app --workers 4

# For 8-core CPU
uvicorn server:socket_app --workers 8
```

### MongoDB
```bash
# Monitor slow queries
mongo
> db.setProfilingLevel(1, 100)
> db.system.profile.find().limit(5).sort({ts: -1})
```

## Support

For issues or questions:
1. Check logs first
2. Review troubleshooting section
3. Verify all configuration files
4. Test each component individually

## Production Checklist

- [ ] Backend running on port 9010 (localhost only)
- [ ] Frontend served via nginx on port 443
- [ ] SSL/TLS certificates valid
- [ ] MongoDB accessible and running
- [ ] Systemd service enabled and running
- [ ] Nginx configuration tested
- [ ] CORS properly configured
- [ ] JWT secret changed from default
- [ ] Logs accessible and monitored
- [ ] Backups configured
- [ ] Firewall rules applied
- [ ] DNS pointing to server
- [ ] Test with multiple concurrent users
