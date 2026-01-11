#!/usr/bin/env python3
"""Verify the project setup is correct."""
import sys
from pathlib import Path


def check_structure() -> bool:
    """Check if all required directories exist."""
    required_dirs = [
        "observability/agents",
        "observability/ingestion",
        "observability/processing",
        "observability/storage",
        "observability/api",
        "observability/common",
        "observability/tests",
        "config",
        "scripts",
        "docs",
    ]
    
    missing = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing.append(dir_path)
    
    if missing:
        print("❌ Missing directories:")
        for d in missing:
            print(f"  - {d}")
        return False
    
    print("✅ All required directories exist")
    return True


def check_files() -> bool:
    """Check if all required files exist."""
    required_files = [
        "pyproject.toml",
        "Makefile",
        "README.md",
        "TODO.md",
        ".gitignore",
        ".env.example",
        ".pre-commit-config.yaml",
        "observability/common/config.py",
        "observability/common/logger.py",
    ]
    
    missing = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing.append(file_path)
    
    if missing:
        print("❌ Missing files:")
        for f in missing:
            print(f"  - {f}")
        return False
    
    print("✅ All required files exist")
    return True


def check_env() -> bool:
    """Check if .env file exists or needs to be created."""
    if not Path(".env").exists():
        print("⚠️  .env file not found")
        print("   Run: cp .env.example .env")
        print("   Then edit .env with your configuration")
        return False
    
    print("✅ .env file exists")
    return True


def check_imports() -> bool:
    """Check if critical imports work."""
    try:
        from observability.common.config import get_settings
        from observability.common.logger import get_logger
        
        # Try to instantiate
        settings = get_settings()
        logger = get_logger(__name__)
        
        print("✅ Core modules import successfully")
        print(f"   Environment: {settings.environment}")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Run: pip install -e '.[dev]'")
        return False
    except Exception as e:
        print(f"❌ Error loading modules: {e}")
        return False


def main() -> int:
    """Run all checks."""
    print("🔍 Verifying project setup...\n")
    
    checks = [
        ("Directory structure", check_structure),
        ("Required files", check_files),
        ("Environment config", check_env),
        ("Python imports", check_imports),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        results.append(check_func())
    
    print("\n" + "=" * 50)
    if all(results):
        print("🎉 Setup verification passed!")
        print("\nYou're ready to start Phase 1: Data Collection Agents")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
