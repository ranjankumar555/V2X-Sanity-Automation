"""
V2X Automation Tests Package

This package contains unified test implementations that work in both Master and SOP modes.
All tests automatically detect whether they're running in Master mode (using native 'sldd')
or SOP mode (using '/log/sldd') based on the device's binary configuration.

Tests:
  • V2X Testing
  • DTC (Diagnostic Trouble Codes)
  • Diagnostics
  • Cybersecurity
  • Geofencing
  • Map Matching
  • Object Forwarding
  • Coding Provisioning

Usage:
  from test_v2x import V2XTest
  test = V2XTest(test_name="V2X", log_file="logs/v2x.log")
  test.run()

Or use the CLI:
  python test_runner.py --test v2x
  python test_runner.py --list
"""

__all__ = [
    'test_v2x',
    'test_dtc', 
    'test_diagnostics',
    'test_cybersecurity',
    'test_geofencing',
    'test_map_matching',
    'test_objForward',
    'test_coding_provisioning',
    'test_base',
    'test_runner'
]
