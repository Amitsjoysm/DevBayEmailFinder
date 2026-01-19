#!/bin/bash

echo "Quick Start Script for Production Deployment"
echo "============================================="

# Copy systemd service
echo "Installing systemd service..."
sudo cp email-verifier-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-verifier-backend
sudo systemctl start email-verifier-backend

# Copy nginx configuration
echo "Installing nginx configuration..."
sudo cp nginx_seo.mj.publicvm.com.conf /etc/nginx/sites-available/seo.mj.publicvm.com
sudo ln -sf /etc/nginx/sites-available/seo.mj.publicvm.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Check status
echo ""
echo "Status Check:"
echo "============="
sudo systemctl status email-verifier-backend --no-pager
echo ""
echo "Backend should be running on http://localhost:9010"
echo "Frontend accessible at https://seo.mj.publicvm.com"
echo ""
echo "View logs:"
echo "  Backend: journalctl -u email-verifier-backend -f"
echo "  Nginx: tail -f /var/log/nginx/seo.mj.publicvm.com.access.log"
