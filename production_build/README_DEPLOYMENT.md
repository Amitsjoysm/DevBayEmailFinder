# Email Verification Tool - Production Deployment

## Deployment Steps

### 1. Upload to Server
Upload the entire `production_build` directory to your server at:
```
/var/www/seo.mj.publicvm.com/
```

### 2. Backend Setup

```bash
cd /var/www/seo.mj.publicvm.com/backend

# Install Python dependencies
pip install -r requirements.txt

# Start backend with uvicorn (runs on port 9010, not exposed externally)
nohup uvicorn server:socket_app --host 0.0.0.0 --port 9010 --workers 4 > backend.log 2>&1 &
```

### 3. Frontend Setup (Nginx Configuration)

Create nginx configuration at `/etc/nginx/sites-available/seo.mj.publicvm.com`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name seo.mj.publicvm.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name seo.mj.publicvm.com;

    # SSL certificates (update paths)
    ssl_certificate /etc/ssl/certs/seo.mj.publicvm.com.crt;
    ssl_certificate_key /etc/ssl/private/seo.mj.publicvm.com.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Root directory for frontend
    root /var/www/seo.mj.publicvm.com/frontend_build;
    index index.html;

    # Frontend - serve static files
    location / {
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API proxy (port 9010 not exposed, only accessible via nginx)
    location /api/ {
        proxy_pass http://127.0.0.1:9010;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running requests
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # Socket.io WebSocket proxy
    location /socket.io/ {
        proxy_pass http://127.0.0.1:9010;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Logging
    access_log /var/log/nginx/seo.mj.publicvm.com.access.log;
    error_log /var/log/nginx/seo.mj.publicvm.com.error.log;

    # Max upload size (for CSV files)
    client_max_body_size 10M;
}
```

Enable the site:
```bash
ln -s /etc/nginx/sites-available/seo.mj.publicvm.com /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 4. MongoDB Setup

```bash
# Ensure MongoDB is running
systemctl status mongodb

# Create database and user (optional but recommended)
mongo
> use email_verifier_production
> db.createUser({
    user: "email_verifier",
    pwd: "your_secure_password",
    roles: [{role: "readWrite", db: "email_verifier_production"}]
})
```

### 5. Process Management (Systemd)

Create systemd service at `/etc/systemd/system/email-verifier-backend.service`:

```ini
[Unit]
Description=Email Verifier Backend Service
After=network.target mongodb.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/seo.mj.publicvm.com/backend
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/uvicorn server:socket_app --host 0.0.0.0 --port 9010 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable email-verifier-backend
systemctl start email-verifier-backend
systemctl status email-verifier-backend
```

### 6. Verify Deployment

```bash
# Check backend is running on port 9010
curl http://localhost:9010/api/docs

# Check frontend is accessible
curl https://seo.mj.publicvm.com

# Check logs
journalctl -u email-verifier-backend -f
tail -f /var/log/nginx/seo.mj.publicvm.com.access.log
```

## Important Notes

1. **Port 9010**: Backend runs ONLY on localhost:9010 and is NOT exposed to external traffic. Only nginx can access it.

2. **CORS**: Backend is configured to accept requests only from `https://seo.mj.publicvm.com`

3. **SSL**: You need valid SSL certificates. You can use Let's Encrypt:
   ```bash
   certbot --nginx -d seo.mj.publicvm.com
   ```

4. **JWT Secret**: A random JWT secret is generated. Save it securely!

5. **MongoDB**: Update MONGO_URL in `.env` if using authentication or remote MongoDB.

6. **Workers**: Backend runs with 4 uvicorn workers for better performance. Adjust based on CPU cores.

## Troubleshooting

### Backend not starting
```bash
journalctl -u email-verifier-backend -n 50
```

### Frontend 404 errors
Check nginx error log:
```bash
tail -f /var/log/nginx/seo.mj.publicvm.com.error.log
```

### Socket.io connection issues
Ensure WebSocket upgrade headers are properly configured in nginx.

### MongoDB connection errors
Check MongoDB is running and credentials are correct in backend/.env
