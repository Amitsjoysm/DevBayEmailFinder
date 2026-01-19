# Production Deployment Guide - seo.mj.publicvm.com

## Quick Setup Guide

### Step 1: Build Frontend
```bash
cd /app/frontend

# Create production env
cat > .env.production << EOF
REACT_APP_BACKEND_URL=https://seo.mj.publicvm.com
GENERATE_SOURCEMAP=false
EOF

# Build
yarn build
```

### Step 2: Backend Configuration
```bash
cd /app/backend

# Create production env
cat > .env.production << EOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=email_verifier_production
CORS_ORIGINS=https://seo.mj.publicvm.com
JWT_SECRET_KEY=$(openssl rand -hex 32)
EOF
```

### Step 3: Copy Files to Server
```bash
# On production server at seo.mj.publicvm.com
mkdir -p /var/www/seo.mj.publicvm.com

# Copy frontend build
scp -r /app/frontend/build/* user@seo.mj.publicvm.com:/var/www/seo.mj.publicvm.com/

# Copy backend
scp -r /app/backend user@seo.mj.publicvm.com:/opt/email-verifier-backend/
```

### Step 4: Start Backend on Production
```bash
# On production server
cd /opt/email-verifier-backend

# Install dependencies
pip install -r requirements.txt

# Start with uvicorn (port 9010, not exposed externally)
uvicorn server:socket_app --host 0.0.0.0 --port 9010 --workers 4 &

# Or use systemd (recommended)
sudo systemctl start email-verifier-backend
```

### Step 5: Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/seo.mj.publicvm.com
```

Paste this configuration:
```nginx
server {
    listen 80;
    server_name seo.mj.publicvm.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seo.mj.publicvm.com;

    ssl_certificate /etc/ssl/certs/seo.mj.publicvm.com.crt;
    ssl_certificate_key /etc/ssl/private/seo.mj.publicvm.com.key;

    root /var/www/seo.mj.publicvm.com;
    index index.html;

    # Frontend
    location / {
        try_files $uri /index.html;
    }

    # Backend API (port 9010 accessible only via nginx)
    location /api/ {
        proxy_pass http://127.0.0.1:9010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /socket.io/ {
        proxy_pass http://127.0.0.1:9010;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 10M;
}
```

Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/seo.mj.publicvm.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Systemd Service (Recommended)

Create `/etc/systemd/system/email-verifier-backend.service`:
```ini
[Unit]
Description=Email Verifier Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/email-verifier-backend
ExecStart=/usr/bin/uvicorn server:socket_app --host 0.0.0.0 --port 9010 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable email-verifier-backend
sudo systemctl start email-verifier-backend
```

## Verification

```bash
# Check backend
curl http://localhost:9010/api/docs

# Check frontend
curl https://seo.mj.publicvm.com

# View logs
journalctl -u email-verifier-backend -f
```

## Key Points

1. ✅ Backend runs on **port 9010** (localhost only)
2. ✅ Port 9010 is **NOT exposed** to external traffic
3. ✅ Nginx proxies `/api/` requests to port 9010
4. ✅ CORS configured for `https://seo.mj.publicvm.com`
5. ✅ Multi-user async issues **FIXED** (per-user domain delays and proxy rotation)

## Multi-User Fixes Applied

The application now supports multiple concurrent users with:
- Per-user domain delay tracking
- Per-user proxy rotation
- Isolated Socket.io rooms
- Independent job state management

See `MULTI_USER_FIX.md` for technical details.
