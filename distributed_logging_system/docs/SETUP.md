# Setup Guide - Observability Platform

## Quick Start (Recommended)

### Step 1: Create Virtual Environment

A virtual environment isolates your project's dependencies from your system Python.

**Why use a virtual environment?**
- Prevents dependency conflicts with other projects
- Keeps your system Python clean
- Makes the project portable
- Follows Python best practices

```bash
# Navigate to project directory
cd observability-platform-poc

# Create virtual environment
make venv

# Or manually:
python3 -m venv venv
```

### Step 2: Activate Virtual Environment

**Linux/Mac:**
```bash
source venv/bin/activate

# You should see (venv) in your prompt:
# (venv) user@machine:~/observability-platform-poc$
```

**Windows:**
```cmd
venv\Scripts\activate

# You should see (venv) in your prompt:
# (venv) C:\observability-platform-poc>
```

**To deactivate later:**
```bash
deactivate
```

### Step 3: Install Dependencies

```bash
# Install development dependencies (includes testing, linting, etc.)
make install-dev

# Or manually:
pip install -e ".[dev]"
```

### Step 4: Complete Setup

```bash
# Setup pre-commit hooks and create .env file
make setup

# Or manually:
pre-commit install
cp .env.example .env
```

### Step 5: Verify Installation

```bash
# Run verification script
make verify

# Should output:
# ✅ All required directories exist
# ✅ All required files exist
# ✅ .env file exists
# ✅ Core modules import successfully
```

---

## Complete Setup Script

If you want to do everything in one go:

```bash
# 1. Create and activate venv
make venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
make install-dev

# 3. Setup hooks and config
make setup

# 4. Verify
make verify
```

---

## Alternative: Without Virtual Environment (Not Recommended)

If you really don't want to use a virtual environment:

```bash
# Install directly to system Python
pip install -e ".[dev]"

# Setup
pre-commit install
cp .env.example .env
```

**⚠️ Warning:** This will install packages globally and may conflict with other projects.

---

## Troubleshooting

### "python3: command not found"

**Linux/Mac:**
```bash
# Check Python version
python --version

# If Python 3.9+, just use 'python'
python -m venv venv
```

**Windows:**
```cmd
# Use 'py' launcher
py -3 -m venv venv
```

### "pip: command not found" after activating venv

```bash
# Make sure venv is activated (you should see (venv) in prompt)
source venv/bin/activate

# Try using python -m pip instead
python -m pip install -e ".[dev]"
```

### Permission errors during pip install

**Linux/Mac:**
```bash
# Make sure you're in the virtual environment!
# You should NOT need sudo if venv is activated

# If you see (venv) in prompt, this should work:
pip install -e ".[dev]"

# If not in venv, activate it first:
source venv/bin/activate
```

### Virtual environment activation doesn't work

**Linux/Mac:**
```bash
# Make sure the file is executable
chmod +x venv/bin/activate

# Use explicit bash/zsh
bash venv/bin/activate
# or
source venv/bin/activate
```

**Windows PowerShell:**
```powershell
# May need to change execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate
.\venv\Scripts\Activate.ps1
```

### "No module named 'observability'" error

```bash
# Make sure you installed in editable mode
pip install -e .

# Verify installation
pip list | grep observability
# Should show: observability-platform 0.1.0

# Try importing
python -c "from observability.common.models import LogEntry"
```

---

## Directory Structure After Setup

```
observability-platform-poc/
├── venv/                    # Virtual environment (created by you)
│   ├── bin/                 # Executables (Linux/Mac)
│   ├── Scripts/             # Executables (Windows)
│   ├── lib/                 # Installed packages
│   └── include/             # C headers
├── observability/           # Main package
├── docs/                    # Documentation
├── tests/                   # Tests
├── .env                     # Your config (created by setup)
├── .gitignore              
├── pyproject.toml          
├── Makefile                
└── README.md               
```

**Note:** `venv/` is in `.gitignore` - it won't be committed to git!

---

## Verifying Virtual Environment

### Check if you're in a virtual environment:

```bash
# Method 1: Check prompt
# You should see (venv) at the start of your prompt

# Method 2: Check VIRTUAL_ENV variable
echo $VIRTUAL_ENV
# Should output: /path/to/observability-platform-poc/venv

# Method 3: Check Python location
which python
# Should output: /path/to/observability-platform-poc/venv/bin/python

# Method 4: Check installed packages
pip list
# Should show only packages you installed, not system packages
```

### Python version check:

```bash
python --version
# Should be Python 3.9 or higher
```

---

## Common Makefile Commands

Once setup is complete, you can use these commands:

```bash
# Verify everything is working
make verify

# Run tests (when we add them in later phases)
make test

# Format code
make format

# Check code quality
make lint

# Clean build artifacts
make clean

# Clean everything including venv
make clean-all

# Run log agent
make run-agent-logs

# Run metrics agent
make run-agent-metrics
```

---

## Best Practices

### Always activate venv before working:

```bash
# Start of each session
cd observability-platform-poc
source venv/bin/activate

# Now you can run Python commands
python -m observability.agents.log_agent --help
```

### Use requirements.txt for deployment:

```bash
# Generate requirements file
pip freeze > requirements.txt

# On another machine:
pip install -r requirements.txt
```

### Keep venv out of version control:

The `.gitignore` file already excludes `venv/`, so it won't be committed.

---

## IDE Setup

### VS Code

Add to `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.terminal.activateEnvironment": true
}
```

### PyCharm

1. Go to: Settings → Project → Python Interpreter
2. Click gear icon → Add
3. Select "Virtual Environment" → Existing
4. Point to: `observability-platform-poc/venv/bin/python`

### Vim/Neovim

Add to your project's `.vimrc` or `init.vim`:
```vim
let g:python3_host_prog = expand('~/observability-platform-poc/venv/bin/python')
```

---

## Next Steps

After setup is complete:

1. ✅ Create the Phase 1 files (models.py, retry.py, agents)
2. ✅ Run `make verify` to ensure everything works
3. ✅ Read `docs/phase-1-complete.md` for details
4. 🚀 Ready for Phase 2!

---

## Full Setup Example Session

Here's what a complete setup session looks like:

```bash
$ cd observability-platform-poc

$ make venv
Creating virtual environment...

Virtual environment created! Activate it with:
  source venv/bin/activate    (Linux/Mac)
  venv\Scripts\activate      (Windows)

$ source venv/bin/activate

(venv) $ make install-dev
Obtaining file:///home/user/observability-platform-poc
  Installing build dependencies ... done
  ...
Successfully installed observability-platform-0.1.0 ...

(venv) $ make setup
pre-commit install
pre-commit installed at .git/hooks/pre-commit
cp .env.example .env
Setup complete! Edit .env with your configuration.

(venv) $ make verify
🔍 Verifying project setup...

Directory structure:
✅ All required directories exist

Required files:
✅ All required files exist

Environment config:
✅ .env file exists

Python imports:
✅ Core modules import successfully
   Environment: development

==================================================
🎉 Setup verification passed!

You're ready to start Phase 1: Data Collection Agents

(venv) $ python -m observability.agents.log_agent --help
usage: log_agent.py [-h] --service SERVICE [--file FILE] ...
```

Perfect! You're all set! 🎉