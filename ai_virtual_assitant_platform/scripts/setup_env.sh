#!/bin/bash

# AIVA Environment Setup Script
# Creates .env file from template if it doesn't exist

set -e

echo "========================================="
echo "AIVA - Environment Setup"
echo "========================================="
echo ""

# Check if .env already exists
if [ -f ".env" ]; then
    echo "✓ .env file already exists"
    echo ""
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing .env file"
        exit 0
    fi
fi

# Copy template
echo "Creating .env file from template..."
cp .env.example .env
echo "✓ .env file created"
echo ""

# Generate secret key
echo "Generating SECRET_KEY..."
SECRET_KEY=$(openssl rand -hex 32)
sed -i "s/your-secret-key-here-change-this-in-production/$SECRET_KEY/" .env
echo "✓ SECRET_KEY generated"
echo ""

# Generate API key
echo "Generating API_KEY..."
API_KEY=$(openssl rand -hex 16)
sed -i "s/your-api-key-here/$API_KEY/" .env
echo "✓ API_KEY generated"
echo ""

echo "========================================="
echo "Environment Setup Complete!"
echo "========================================="
echo ""
echo "⚠️  IMPORTANT: You still need to configure:"
echo ""
echo "  1. OPENAI_API_KEY - Add your OpenAI API key"
echo "     Get it from: https://platform.openai.com/api-keys"
echo ""
echo "  2. Database credentials (if not using defaults)"
echo "  3. Redis credentials (if not using defaults)"
echo "  4. Qdrant credentials (if not using defaults)"
echo ""
echo "Edit the .env file:"
echo "  nano .env"
echo ""
echo "✓ Ready to configure!"