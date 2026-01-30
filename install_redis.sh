#!/bin/bash
set -e

echo "📦 Installing Redis Server..."

# Update package list
apt-get update -qq

# Install Redis
apt-get install -y redis-server redis-tools

# Check Redis version
redis-server --version

echo "✅ Redis installation complete!"
