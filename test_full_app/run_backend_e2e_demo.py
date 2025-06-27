#!/usr/bin/env python3
"""
Orchestrator script for DRSearch backend testing.

This script can run component demos, E2E tests, or both.
By default, it runs only the E2E tests for efficiency.

Usage:
    cd drsearch_backend
    poetry run python ../test_full_app/run_backend_e2e_demo.py [--with-demo] [--demo-only]
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


# Legacy functions removed - functionality moved to separate scripts


def run_demo_script():
    """Run the standalone demo script."""
    current_dir = Path.cwd()
    demo_script = current_dir.parent / "test_full_app" / "demo_fake_components.py"
    
    print("🎭 Running fake components demo...")
    result = subprocess.run([
        "poetry", "run", "python", str(demo_script)
    ], cwd=current_dir)
    
    return result.returncode == 0


def run_test_script():
    """Run the standalone test script."""
    current_dir = Path.cwd()
    test_script = current_dir.parent / "test_full_app" / "run_backend_e2e_tests.py"
    
    print("🧪 Running backend E2E tests...")
    result = subprocess.run([
        "poetry", "run", "python", str(test_script)
    ], cwd=current_dir)
    
    return result.returncode == 0


def main():
    """Main orchestrator script."""
    parser = argparse.ArgumentParser(description="DRSearch backend testing orchestrator")
    parser.add_argument("--with-demo", action="store_true", 
                       help="Run component demo before tests")
    parser.add_argument("--demo-only", action="store_true", 
                       help="Run only the component demo")
    
    args = parser.parse_args()
    
    print("🚀 DRSearch Backend Testing Orchestrator")
    print("=" * 50)
    
    success = True
    
    if args.demo_only:
        print("🎯 Running component demo only...")
        success = run_demo_script()
    elif args.with_demo:
        print("🎯 Running demo followed by tests...")
        if not run_demo_script():
            print("\n❌ Demo failed")
            success = False
        elif not run_test_script():
            print("\n❌ Tests failed")
            success = False
    else:
        print("🎯 Running E2E tests only (use --with-demo to include component demo)...")
        success = run_test_script()
    
    if success:
        print("\n🎉 All operations completed successfully!")
        print("\nAvailable scripts:")
        print("• demo_fake_components.py - Quick component demonstration")
        print("• run_backend_e2e_tests.py - Focused E2E test execution")
        print("• run_backend_e2e_demo.py - This orchestrator script")
    else:
        print("\n❌ Some operations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 
