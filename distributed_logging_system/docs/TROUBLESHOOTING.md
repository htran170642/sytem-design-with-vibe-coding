# Troubleshooting Guide

## Installation Issues

### Error: "Multiple top-level packages discovered"

**Problem:** Setuptools finds multiple packages at the root level.

**Solution:** Already fixed in `pyproject.toml`. Make sure you have the latest version with:

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["observability*"]
exclude = ["tests*", "docs*", "scripts*", "config*"]
```

### Error: "No module named 'observability'"

**Problem:** Package not installed in editable mode.

**Solution:**
```bash
pip install -e ".[dev]"
```

### Error: Pre-commit hooks failing

**Problem:** Pre-commit not installed or outdated.

**Solution:**
```bash
pip install pre-commit
pre-commit install
pre-commit autoupdate
```

## Environment Issues

### Settings not loading

**Problem:** `.env` file missing or not in the right location.

**Solution:**
```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env  # or vim, code, etc.
```

### Import errors with pydantic-settings

**Problem:** Older version of pydantic-settings.

**Solution:**
```bash
pip install --upgrade pydantic-settings
```

## Development Workflow

### Quick Setup
```bash
# Clone/extract project
cd observability-platform-poc

# Create virtual environment (recommended)
python3.9 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
make setup

# Verify everything works
make verify
```

### Verify Installation
```bash
# Run verification script
python scripts/verify_setup.py

# Or use make
make verify
```

### Running Tests
```bash
# Install dependencies first
make install-dev

# Run tests (when we add them in Phase 1)
make test
```

## Common Issues

### Import paths not working

Make sure you're importing from `observability.*`:
```python
# ✅ Correct
from observability.common.config import get_settings
from observability.common.logger import get_logger

# ❌ Incorrect
from common.config import get_settings
```

### .env not being read

Make sure `.env` is in the project root (same directory as `pyproject.toml`):
```bash
# Check location
ls -la .env

# If missing
cp .env.example .env
```

### Black/isort conflicts

Already configured to work together in `pyproject.toml`. If you see conflicts:
```bash
# Format code
make format

# This runs both black and isort with compatible settings
```

## Helpful Commands

```bash
# Check project structure
find . -type d -name "__pycache__" -prune -o -type f -name "*.py" -print | head -20

# Verify Python version
python --version  # Should be 3.9+

# Check installed packages
pip list | grep observability

# Clean build artifacts
make clean

# Format and lint
make format
make lint
```

## Getting Help

If you encounter issues not covered here:

1. Check the error message carefully
2. Verify your Python version (3.9+)
3. Make sure virtual environment is activated
4. Try `make clean` and reinstall
5. Check that all files from the archive were extracted

## Next Steps

Once installation is working:
1. Run `make verify` to ensure everything is set up
2. You're ready for Phase 1: Data Collection Agents! 🚀
