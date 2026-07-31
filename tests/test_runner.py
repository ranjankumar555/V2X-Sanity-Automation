"""
Unified Test Runner - Execute any V2X test by name

Usage:
    python test_runner.py --test v2x          # Run V2X test
    python test_runner.py --test dtc           # Run DTC test
    python test_runner.py --test basic_sanity      # Run full one-shot sequence
    python test_runner.py --list              # List all available tests
    
Tests automatically detect and adapt to Master or SOP mode.
"""

import sys
import argparse
from pathlib import Path

# Import all test classes
from test_v2x import V2XTest
from test_dtc import DTCTest
from test_diagnostics import DiagnosticsTest
from test_cybersecurity import CybersecurityTest
from test_geofencing import GeofencingTest
from test_map_matching import MapMatchingTest
from test_objForward import ObjectForwardingTest
from test_coding_provisioning import CodingProvisioningTest
from basic_sanity import BasicSanityTest
from test_certificate_download import TestCertificateDownload


# Test registry - maps test name to test class and log file
TEST_REGISTRY = {
    "v2x": {
        "class": V2XTest,
        "display": "V2X Test",
        "log": r"../logs/v2x_test.log"
    },
    "dtc": {
        "class": DTCTest,
        "display": "DTC Test",
        "log": r"../logs/dtc_testcases.log"
    },
    "diagnostics": {
        "class": DiagnosticsTest,
        "display": "Diagnostics Test",
        "log": r"../logs/diagnostics_test.log"
    },
    "cybersecurity": {
        "class": CybersecurityTest,
        "display": "Cybersecurity Test",
        "log": r"../logs/cybersecurity_test.log"
    },
    "certificate_download": {
        "class": TestCertificateDownload,
        "display": "Certificate Download Test",
        "log": r"../logs/certificate_download.log"
    },
    "geofencing": {
        "class": GeofencingTest,
        "display": "Geofencing Test",
        "log": r"../logs/geofencing.log"
    },
    "map_matching": {
        "class": MapMatchingTest,
        "display": "Map Matching Test",
        "log": r"../logs/map_matching.log"
    },
    "objforward": {
        "class": ObjectForwardingTest,
        "display": "Object Forwarding Test",
        "log": r"../logs/objForward_test.log"
    },
    "coding_prov": {
        "class": CodingProvisioningTest,
        "display": "Coding Provisioning Test",
        "log": r"../logs/coding_prov_test.log"
    },
    "basic_sanity": {
        "class": BasicSanityTest,
        "display": "Basic Sanity Test",
        "log": r"../logs/basic_sanity.log"
    },
}


def list_tests():
    """Display all available tests."""
    print("\n" + "="*60)
    print("Available Tests (Master/SOP compatible)")
    print("="*60)
    for name, info in sorted(TEST_REGISTRY.items()):
        print(f"  • {name:<20} - {info['display']}")
    print("="*60 + "\n")


def run_test(test_name: str):
    """Run a specific test by name."""
    test_name = test_name.lower()
    
    if test_name not in TEST_REGISTRY:
        print(f"\n❌ Error: Test '{test_name}' not found.")
        print("\nAvailable tests:")
        for name in sorted(TEST_REGISTRY.keys()):
            print(f"  • {name}")
        return 1
    
    test_info = TEST_REGISTRY[test_name]
    test_class = test_info["class"]
    log_file = test_info["log"]
    
    print(f"\n{'='*60}")
    print(f"Running: {test_info['display']}")
    print(f"{'='*60}")
    
    try:
        test = test_class(
            test_name=test_info["display"],
            log_file=log_file
        )
        success = test.run()
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Error running test: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified V2X Test Runner (Master/SOP compatible)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py --test v2x           Run V2X test
  python test_runner.py --test dtc           Run DTC test  
    python test_runner.py --test basic_sanity      Run full one-shot sequence
  python test_runner.py --list               List all tests
  
All tests automatically detect and adapt to Master or SOP mode.
        """
    )
    
    parser.add_argument(
        "--test",
        type=str,
        help="Name of the test to run"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available tests"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_tests()
        return 0
    elif args.test:
        return run_test(args.test)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
