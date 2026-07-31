#!/usr/bin/env python3
"""
Quick setup verification and test script
Run this to verify the new framework is properly set up
"""

import sys
import os
from pathlib import Path


def check_files():
    """Check if all required files exist."""
    required_files = [
        "test_base.py",
        "test_runner.py",
        "test_v2x.py",
        "test_dtc.py",
        "test_diagnostics.py",
        "test_cybersecurity.py",
        "test_geofencing.py",
        "test_map_matching.py",
        "test_objForward.py",
        "test_coding_provisioning.py",
        "__init__.py",
    ]
    
    tests_dir = Path(__file__).parent
    missing = []
    
    for file in required_files:
        filepath = tests_dir / file
        if not filepath.exists():
            missing.append(file)
    
    return missing


def check_imports():
    """Check if imports work correctly."""
    errors = []
    
    try:
        from test_base import TestBase
        print("[OK] test_base imports successfully")
    except Exception as e:
        errors.append(f"[ERROR] test_base import error: {e}")
    
    try:
        from test_runner import TEST_REGISTRY
        if len(TEST_REGISTRY) == 8:
            print(f"[OK] test_runner loaded with {len(TEST_REGISTRY)} tests")
        else:
            errors.append(f"[ERROR] test_runner has {len(TEST_REGISTRY)} tests (expected 8)")
    except Exception as e:
        errors.append(f"[ERROR] test_runner import error: {e}")
    
    return errors


def main():
    """Run verification checks."""
    print("\n" + "="*60)
    print("V2X Automation Framework - SETUP VERIFICATION")
    print("="*60 + "\n")
    
    print("1. Checking files...")
    missing = check_files()
    if not missing:
        print("[OK] All required files present\n")
    else:
        print(f"[ERROR] Missing {len(missing)} files:")
        for file in missing:
            print(f"  - {file}")
        print()
    
    print("2. Checking imports...")
    errors = check_imports()
    if not errors:
        print("[OK] All imports successful\n")
    else:
        for error in errors:
            print(error)
        print()
    
    print("3. Setup Status:")
    if not missing and not errors:
        print("="*60)
        print("SETUP COMPLETE - Ready to run tests!")
        print("="*60)
        print("\nNext steps:")
        print("  1. python test_runner.py --list")
        print("  2. python test_runner.py --test v2x")
        print("\nDocumentation:")
        print("  • QUICK_REFERENCE.md - Quick commands")
        print("  • README.md - Full documentation")
        print("  • INDEX.md - Navigation guide")
        print()
        return 0
    else:
        print("="*60)
        print("SETUP INCOMPLETE - Fix errors above")
        print("="*60 + "\n")
        return 1


if __name__ == "__main__":
    exit(main())
