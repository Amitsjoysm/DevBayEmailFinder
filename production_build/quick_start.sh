#!/bin/bash

echo "Quick Start Script for Production Deployment"
echo "============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo ./quick_start.sh"
    exit 1
fi

echo "[1/5] Installing systemd service..."
cp email-verifier-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable email-verifier-backend
systemctl start email-verifier-backend
echo "✓ Backend service installed"

sleep 2

echo ""
echo "[2/5] Installing nginx configuration..."
cp nginx_seo.mj.publicvm.com.conf /etc/nginx/sites-available/seo.mj.publicvm.com
ln -sf /etc/nginx/sites-available/seo.mj.publicvm.com /etc/nginx/sites-enabled/
echo "✓ Nginx configuration installed"

echo ""
echo "[3/5] Testing nginx configuration..."
if nginx -t; then
    echo "✓ Nginx configuration valid"
    systemctl reload nginx
    echo "✓ Nginx reloaded"
else
    echo "✗ Nginx configuration error! Please check the config."
    exit 1
fi

echo ""
echo "[4/5] Checking backend service..."
sleep 3
if systemctl is-active --quiet email-verifier-backend; then
    echo "✓ Backend service is running"
else
    echo "✗ Backend service failed to start!"
    echo "Check logs: journalctl -u email-verifier-backend -n 50"
    exit 1
fi

echo ""
echo "[5/5] Testing endpoints..."
sleep 2
if curl -s http://localhost:9010/api/docs > /dev/null; then
    echo "✓ Backend API accessible on port 9010"
else
    echo "⚠ Backend API not responding yet (might still be starting up)"
fi

echo ""
echo "============================================="
echo "✓ Deployment Complete!"
echo "============================================="
echo ""
echo "Service Status:"
systemctl status email-verifier-backend --no-pager --lines=5
echo ""
echo "Next Steps:"
echo "1. Install SSL certificate: sudo certbot --nginx -d seo.mj.publicvm.com"
echo "2. Test frontend: https://seo.mj.publicvm.com"
echo "3. Test backend: https://seo.mj.publicvm.com/api/docs"
echo ""
echo "Monitoring:"
echo "  Backend logs: journalctl -u email-verifier-backend -f"
echo "  Nginx logs: tail -f /var/log/nginx/seo.mj.publicvm.com.access.log"
echo ""
echo "Important: Port 9010 is only accessible from localhost (not exposed externally)"
echo ""
