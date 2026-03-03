#!/bin/bash

################################################################################
# AIVA Complete Project Setup Script
# Run this script to create the entire AIVA project structure from scratch
#
# Usage:
#   bash setup_aiva.sh [project_name]
#
# Example:
#   bash setup_aiva.sh              # Creates ./aiva
#   bash setup_aiva.sh my-ai-app    # Creates ./my-ai-app
################################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_info() { echo -e "${YELLOW}→${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Get project name from argument or use default
PROJECT_NAME="${1:-aiva}"

print_header "AIVA Project Setup - ${PROJECT_NAME}"
echo ""

# Check if directory already exists
if [ -d "${PROJECT_NAME}" ]; then
    print_error "Directory '${PROJECT_NAME}' already exists!"
    echo "Please choose a different name or remove the existing directory."
    exit 1
fi

# Create and enter project directory
print_info "Creating project: ${PROJECT_NAME}"
mkdir -p ${PROJECT_NAME}
cd ${PROJECT_NAME}
print_success "Project directory created"
echo ""

# Create folder structure
print_info "Creating folder structure..."
mkdir -p app/api/routes app/core app/services app/models app/schemas app/db app/utils
mkdir -p tests/unit tests/integration
mkdir -p scripts docs logs
print_success "Folder structure created"
echo ""

# Create .gitignore
print_info "Creating .gitignore..."
cat > .gitignore << 'GITIGNORE_EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environment
venv/
env/
ENV/
.venv

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# Logs
*.log
logs/

# Database
*.db
*.sqlite3

# OS
.DS_Store
Thumbs.db

# Celery
celerybeat-schedule
celerybeat.pid

# Temporary files
*.tmp
*.bak
.cache/
GITIGNORE_EOF
print_success ".gitignore created"
echo ""

# Create README.md
print_info "Creating README.md..."
cat > README.md << 'README_EOF'
# AIVA – AI Virtual Assistant Platform

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)

## 🎯 Overview

AIVA is a production-ready AI backend platform with:
- AI Integration (OpenAI, LangChain)
- RAG (Retrieval-Augmented Generation)
- Scalable Architecture
- Production-Ready Features

## 🏗️ Architecture

```
FastAPI API → Services → LLM (OpenAI)
     ↓           ↓
 Rate Limit   Vector DB
 Auth         PostgreSQL
 Cache        Redis
```

## 📁 Structure

```
aiva/
├── app/              # Application code
├── tests/            # Tests
├── scripts/          # Helper scripts
├── docs/             # Documentation
└── logs/             # Logs
```

## 🚀 Quick Start

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload
```

## 🛠️ Tech Stack

- FastAPI, OpenAI, LangChain
- Qdrant, PostgreSQL, Redis
- Celery, Docker

---

**Status**: Phase 1 - Setup ✅
README_EOF
print_success "README.md created"
echo ""

# Create TODO.md
print_info "Creating TODO.md..."
cat > TODO.md << 'TODO_EOF'
# 🚀 AIVA - Progress Tracker

## ✅ Phase 1 — Project Setup
- [x] Step 0: Initialize structure
- [ ] Step 1: Virtual environment
- [ ] Step 2: Dependencies
- [ ] Step 3: Environment variables
- [ ] Step 4: Logging
- [ ] Step 5: Health endpoint

## ⏳ Phase 2 — FastAPI Backend
## ⏳ Phase 3 — AI Integration
## ⏳ Phase 4 — RAG
## ⏳ Phase 5 — Background Jobs
## ⏳ Phase 6 — Caching
## ⏳ Phase 7 — Database
## ⏳ Phase 8 — Testing
## ⏳ Phase 9 — Docker
## ⏳ Phase 10 — Monitoring
## ⏳ Phase 11 — Security
## ⏳ Phase 12 — Documentation

---
**Current**: Phase 1, Step 0 ✅
TODO_EOF
print_success "TODO.md created"
echo ""

# Create __init__.py files
print_info "Creating Python packages..."
cat > app/__init__.py << 'INIT_EOF'
"""AIVA - AI Virtual Assistant Platform"""

__version__ = "0.1.0"
__author__ = "AIVA Team"
INIT_EOF

for dir in app/api app/api/routes app/core app/services app/models app/schemas app/db app/utils tests tests/unit tests/integration; do
    touch ${dir}/__init__.py
done
print_success "Python packages created"
echo ""

# Initialize git
if command -v git &> /dev/null; then
    print_info "Initializing Git repository..."
    git init > /dev/null 2>&1
    git config user.name "AIVA Developer" 2>/dev/null || true
    git config user.email "dev@aiva.local" 2>/dev/null || true
    git add . > /dev/null 2>&1
    git commit -m "Phase 1, Step 0: Initialize project structure" > /dev/null 2>&1
    print_success "Git repository initialized"
else
    print_info "Git not found, skipping repository initialization"
fi
echo ""

# Display summary
print_header "Setup Complete!"
echo ""
echo -e "${GREEN}✨ Project '${PROJECT_NAME}' created successfully!${NC}"
echo ""
echo "📁 Structure:"
echo "   ├── app/              Application code"
echo "   ├── tests/            Test files"
echo "   ├── scripts/          Helper scripts"
echo "   ├── docs/             Documentation"
echo "   └── logs/             Application logs"
echo ""
echo "📝 Files:"
echo "   ├── .gitignore        Git exclusions"
echo "   ├── README.md         Project overview"
echo "   └── TODO.md           Progress tracker"
echo ""
echo -e "${YELLOW}🚀 Next Steps:${NC}"
echo "   1. cd ${PROJECT_NAME}"
echo "   2. python3 -m venv venv"
echo "   3. source venv/bin/activate"
echo "   4. pip install fastapi uvicorn"
echo ""
echo -e "${GREEN}✓ Ready to build AIVA!${NC}"
echo ""
SETUP_EOF
print_success "Setup script saved"
echo ""