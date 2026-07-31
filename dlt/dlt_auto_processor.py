#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dlt_auto_processor.py

Automated DLT Log Processing Monitor
- Watches D:\sanity\extract_date\extract_device_variant\ directory
- Detects DLT files matching pattern: basic_sanity_<device_version>.dlt
- Automatically processes logs and generates verification results
- Moves processed files to archive subdirectory

Usage:
    python dlt_auto_processor.py                    # Start watcher (continuous mode)
    python dlt_auto_processor.py --process <path>   # Process single DLT file
    python dlt_auto_processor.py --watch            # Continuous monitoring mode
"""

import os
import sys
import json
import time
import re
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from fnmatch import fnmatchcase

# Add parent directory to path
PARENT_DIR = Path(__file__).parent.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

# Import advanced verifier
from dlt_verifier import DLTVerifier, verify_dlt_file

# Constants
WATCH_DIR = r"D:\sanity\extract_date\extract_device_variant"
ARCHIVE_DIR = os.path.join(WATCH_DIR, "archived")
RESULTS_DIR = os.path.join(WATCH_DIR, "results")
DLT_VIEWER_EXE = r"..\dlt\DltViewerSDK-2.21.3\dlt-viewer.exe"

# DLT verification rules matching basic_sanity test cases
RULES_LIST = [
    ("DIAG", "DIAG"),
    ("V2X*", "MAIN"),
    ("V2X*", "V2X"),
    ("APP", "*"),
    ("*", "CON"),
]

# Legacy test cases (kept for backward compatibility)
# The new system uses comprehensive verification in dlt_verifier.py
TESTS = [
    {"name": "Coding Provisioning Success", "needle": "Coding provisioning completed"},
    {"name": "Diagnostics Response OK", "needle": "diagnostic response"},
    {"name": "DTC Report Generated", "needle": "DTC report"},
    {"name": "Cybersecurity Certificate OK", "needle": "certificate validation"},
    {"name": "V2X Stack Ready", "needle": "V2X stack ready"},
    {"name": "Radio Access Error Check", "needle": "DTC Info"},
]

# Regions for cybersecurity verification
CYBERSECURITY_REGIONS = ["EU", "CN"]

# Column overrides for CSV parsing
COLUMN_OVERRIDES = {
    "APID": "Apid",
    "CTID": "Ctid",
    "PAYLOAD": "Payload",
}


def _log(msg: str, level: str = "INFO") -> None:
    """Print timestamped log message."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def extract_device_version(filename: str) -> Optional[str]:
    """
    Extract device version from DLT filename.
    Pattern: basic_sanity_v040.040.065.iconsf25.oem_260525.dlt
    Extracts: v040.040.065.iconsf25.oem_260525
    """
    match = re.search(r"basic_sanity_([vV][\w.]+)\.dlt$", filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def find_dlt_files(directory: str) -> List[str]:
    """Find all DLT files matching pattern in directory."""
    if not os.path.exists(directory):
        _log(f"Watch directory does not exist: {directory}", "ERROR")
        return []
    
    dlt_files = []
    for filename in os.listdir(directory):
        if filename.startswith("basic_sanity_") and filename.endswith(".dlt"):
            full_path = os.path.join(directory, filename)
            if os.path.isfile(full_path):
                dlt_files.append(full_path)
    
    return sorted(dlt_files)


def normalize(name: str) -> str:
    """Normalize column name for matching."""
    return (name or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def quick_detect_delimiter(header_line: str) -> str:
    """Detect CSV delimiter (comma or semicolon)."""
    sc = header_line.count(';')
    cc = header_line.count(',')
    if sc == 0 and cc == 0:
        return ','
    return ';' if sc > cc else ','


def locate_columns(header: List[str], overrides: Optional[Dict] = None) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Locate APID, CTID, and PAYLOAD columns in header."""
    norm = [normalize(h) for h in header]
    
    def find_one(name_norm: str) -> Optional[int]:
        for i, n in enumerate(norm):
            if n == name_norm or name_norm in n:
                return i
        return None
    
    ap_i = ct_i = pl_i = None
    
    if overrides:
        if overrides.get("APID"):
            ap_i = find_one(normalize(overrides["APID"]))
        if overrides.get("CTID"):
            ct_i = find_one(normalize(overrides["CTID"]))
        if overrides.get("PAYLOAD"):
            pl_i = find_one(normalize(overrides["PAYLOAD"]))
    
    # Fallback search
    if ap_i is None:
        ap_i = find_one("apid") or find_one("appid")
    if ct_i is None:
        ct_i = find_one("ctid") or find_one("ctxid")
    if pl_i is None:
        pl_i = find_one("payload") or find_one("text")
    
    if pl_i is None and header:
        pl_i = len(header) - 1
    
    return ap_i, ct_i, pl_i


def rule_matches(apid_val: str, ctid_val: str, rules_list: List) -> bool:
    """Check if APID/CTID matches any rule."""
    for rule in rules_list:
        if isinstance(rule, dict):
            ap_pat = rule.get("apid", "*")
            ct_pat = rule.get("ctid", "*")
        else:
            ap_pat, ct_pat = rule
        
        ap_ok = (ap_pat == "*") or fnmatchcase(apid_val, ap_pat)
        ct_ok = (ct_pat == "*") or fnmatchcase(ctid_val, ct_pat)
        
        if ap_ok and ct_ok:
            return True
    
    return False


def convert_dlt_to_csv(dlt_file: str) -> Optional[str]:
    """Convert DLT file to CSV using DLT Viewer."""
    csv_file = dlt_file.replace(".dlt", ".csv")
    
    try:
        _log(f"Converting DLT to CSV: {dlt_file}")
        args = [DLT_VIEWER_EXE, "-s", "-csv", "-u", "-c", dlt_file, csv_file]
        
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            _log(f"DLT Viewer failed: {result.stderr}", "ERROR")
            return None
        
        if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
            _log(f"CSV conversion resulted in empty file: {csv_file}", "ERROR")
            return None
        
        _log(f"Successfully converted to CSV: {csv_file}")
        return csv_file
    
    except FileNotFoundError:
        _log(f"DLT Viewer not found: {DLT_VIEWER_EXE}", "ERROR")
        return None
    except subprocess.TimeoutExpired:
        _log(f"DLT conversion timeout for: {dlt_file}", "ERROR")
        return None
    except Exception as e:
        _log(f"Error during DLT conversion: {str(e)}", "ERROR")
        return None


def prefilter_csv(csv_file: str, filtered_csv: str) -> bool:
    """Pre-filter CSV using RULES_LIST."""
    try:
        import csv as csv_module
        
        _log(f"Pre-filtering CSV: {csv_file}")
        
        with open(csv_file, "r", encoding="utf-8", errors="replace", newline="") as rf:
            first = rf.readline()
            if not first:
                _log("CSV file is empty", "ERROR")
                return False
            
            delim = quick_detect_delimiter(first)
            rf.seek(0)
            
            reader = csv_module.reader(rf, delimiter=delim, quotechar='"', escapechar='\\')
            header = next(reader, None) or []
            
            ap_i, ct_i, pl_i = locate_columns(header, overrides=COLUMN_OVERRIDES)
            
            if ap_i is None or ct_i is None:
                _log("APID/CTID columns not found in CSV", "ERROR")
                return False
            
            # Find timestamp column
            ts_i = None
            for i, h in enumerate(header):
                if normalize(h) in ("timestamp", "time"):
                    ts_i = i
                    break
            
            keep_idx = [ap_i, ct_i, pl_i] + ([ts_i] if ts_i is not None else [])
            out_header = [header[i] for i in keep_idx]
            
            os.makedirs(os.path.dirname(filtered_csv) or ".", exist_ok=True)
            
            with open(filtered_csv, "w", encoding="utf-8", newline="") as wf:
                writer = csv_module.writer(wf, delimiter=',', quotechar='"', lineterminator="\n")
                writer.writerow(out_header)
                
                row_count = 0
                for row in reader:
                    if ap_i >= len(row) or ct_i >= len(row):
                        continue
                    
                    apv = (row[ap_i] or "").strip().strip('"')
                    ctv = (row[ct_i] or "").strip().strip('"')
                    
                    if rule_matches(apv, ctv, RULES_LIST):
                        writer.writerow([row[i] if i < len(row) else "" for i in keep_idx])
                        row_count += 1
            
            _log(f"Pre-filtered CSV created with {row_count} rows: {filtered_csv}")
            return True
    
    except Exception as e:
        _log(f"Error during CSV pre-filtering: {str(e)}", "ERROR")
        return False


def search_tests_in_csv(csv_file: str, tests: List[Dict]) -> List[Dict]:
    """Search for test patterns in filtered CSV (legacy method)."""
    try:
        import csv as csv_module
        
        _log(f"Searching test patterns in: {csv_file}")
        
        # Prepare test needles
        prepared = [
            {
                "name": t["name"],
                "needle": t["needle"].lower(),
                "passed": False
            }
            for t in tests
        ]
        
        with open(csv_file, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv_module.reader(f, delimiter=',', quotechar='"', escapechar='\\')
            header = next(reader, None) or []
            
            # Find payload column
            payload_idx = None
            for i, h in enumerate(header):
                if normalize(h) == "payload":
                    payload_idx = i
                    break
            
            if payload_idx is None:
                payload_idx = len(header) - 1 if header else 0
            
            # Search through all rows
            for row in reader:
                if payload_idx >= len(row):
                    continue
                
                hay = (row[payload_idx] or "").lower()
                
                for t in prepared:
                    if not t["passed"] and t["needle"] in hay:
                        t["passed"] = True
                        _log(f"  [+] Found: {t['name']}", "DEBUG")
        
        results = [
            {
                "Testcase Name": t["name"],
                "Result": "Pass" if t["passed"] else "Fail"
            }
            for t in prepared
        ]
        
        return results
    
    except Exception as e:
        _log(f"Error during test search: {str(e)}", "ERROR")
        return [
            {"Testcase Name": t["name"], "Result": "Fail"}
            for t in tests
        ]


def verify_with_advanced_verifier(csv_file: str, device_version: str) -> Dict[str, Any]:
    """
    Advanced verification using timeline and ECUID analysis.
    
    This replaces the legacy needle-based search with comprehensive
    verification that includes:
    - Timeline analysis
    - ECUID filtering
    - Region-aware verification (EU/CN)
    - Detailed evidence collection
    
    Args:
        csv_file: Path to filtered CSV file
        device_version: Device version string
    
    Returns:
        Verification report dictionary
    """
    try:
        _log(f"[ADVANCED] Starting timeline-based verification")
        
        # Determine regions from device version
        regions = []
        if "cn" in device_version.lower():
            regions.append("CN")
        if "eu" in device_version.lower() or not regions:
            regions.append("EU")
        
        _log(f"[ADVANCED] Detected regions: {', '.join(regions)}")
        
        # Run comprehensive verification
        report = verify_dlt_file(csv_file, device_version, regions=regions)
        
        # Log summary
        summary = report.get("summary", {})
        _log(f"[ADVANCED] Verification Summary:")
        _log(f"  Total Tests: {summary.get('total_tests', 0)}")
        _log(f"  Passed: {summary.get('passed', 0)}")
        _log(f"  Failed: {summary.get('failed', 0)}")
        _log(f"  Inconclusive: {summary.get('inconclusive', 0)}")
        _log(f"  Pass Rate: {summary.get('pass_rate', 'N/A')}")
        
        # Log individual test results
        _log(f"[ADVANCED] Test Results:")
        for test_name, result in report.get("results", {}).items():
            status = result.get("status", "Unknown")
            details = result.get("details", "")
            icon = "[+]" if status == "Pass" else "[!]" if status == "Fail" else "[?]"
            _log(f"  {icon} {test_name}: {status}")
            if details:
                _log(f"      {details}")
        
        return report
    
    except Exception as e:
        _log(f"[ADVANCED] Verification failed: {str(e)}", "ERROR")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": device_version
        }


def write_results_json(output_json: str, version: str, results: List[Dict]) -> bool:
    """Write test results to JSON file."""
    try:
        os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
        
        data = {
            "Version": version,
            "Timestamp": datetime.now().isoformat(),
            "Results": results
        }
        
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        _log(f"Results saved: {output_json}")
        return True
    
    except Exception as e:
        _log(f"Error writing results JSON: {str(e)}", "ERROR")
        return False


def process_dlt_file(dlt_file: str, use_advanced_verification: bool = True) -> bool:
    """
    Process a single DLT file: convert, filter, and verify.
    
    Args:
        dlt_file: Path to DLT file
        use_advanced_verification: Use timeline/ECUID-based verification (default) or legacy needle search
    """
    try:
        if not os.path.exists(dlt_file):
            _log(f"DLT file not found: {dlt_file}", "ERROR")
            return False
        
        _log(f"Processing DLT file: {dlt_file}")
        
        # Extract device version from filename
        filename = os.path.basename(dlt_file)
        device_version = extract_device_version(filename)
        
        if not device_version:
            _log(f"Could not extract device version from filename: {filename}", "ERROR")
            return False
        
        _log(f"Device version: {device_version}")
        
        # Step 1: Convert DLT to CSV
        csv_file = convert_dlt_to_csv(dlt_file)
        if not csv_file:
            return False
        
        # Step 2: Pre-filter CSV
        filtered_csv = csv_file.replace(".csv", ".prefiltered.csv")
        if not prefilter_csv(csv_file, filtered_csv):
            return False
        
        # Step 3: Verification (use advanced or legacy)
        if use_advanced_verification:
            _log("=" * 60)
            _log("ADVANCED VERIFICATION (Timeline + ECUID Analysis)")
            _log("=" * 60)
            verification_report = verify_with_advanced_verifier(filtered_csv, device_version)
            
            # Convert advanced report to legacy format for backward compatibility
            results = []
            for test_name, test_result in verification_report.get("results", {}).items():
                results.append({
                    "Testcase Name": test_name,
                    "Result": "Pass" if test_result.get("status") == "Pass" else "Fail"
                })
        else:
            _log("=" * 60)
            _log("LEGACY VERIFICATION (Pattern Matching)")
            _log("=" * 60)
            results = search_tests_in_csv(filtered_csv, TESTS)
            verification_report = {
                "summary": {
                    "total_tests": len(results),
                    "passed": sum(1 for r in results if r["Result"] == "Pass"),
                    "failed": sum(1 for r in results if r["Result"] == "Fail"),
                },
                "results": {r["Testcase Name"]: {"status": r["Result"]} for r in results}
            }
        
        # Print test results summary
        _log("TEST RESULTS SUMMARY")
        _log("-" * 60)
        for result in results:
            status_icon = "[+]" if result["Result"] == "Pass" else "[!]"
            _log(f"  {status_icon} {result['Testcase Name']}: {result['Result']}")
        _log("=" * 60)
        
        # Step 4: Write comprehensive results JSON
        results_json = os.path.join(RESULTS_DIR, f"result_{device_version}.json")
        
        # Enhance report with version and timestamp
        final_report = {
            "Version": device_version,
            "Timestamp": datetime.now().isoformat(),
            "VerificationMethod": "Advanced" if use_advanced_verification else "Legacy",
            **verification_report,
            "Results": results  # Include legacy format for compatibility
        }
        
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(results_json, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        
        _log(f"Results saved: {results_json}")
        
        # Step 5: Archive processed files
        archive_subdir = os.path.join(ARCHIVE_DIR, device_version)
        os.makedirs(archive_subdir, exist_ok=True)
        
        shutil.move(dlt_file, os.path.join(archive_subdir, filename))
        if os.path.exists(csv_file):
            shutil.move(csv_file, os.path.join(archive_subdir, os.path.basename(csv_file)))
        if os.path.exists(filtered_csv):
            shutil.move(filtered_csv, os.path.join(archive_subdir, os.path.basename(filtered_csv)))
        
        _log(f"Archived processed files to: {archive_subdir}")
        _log(f"[OK] Successfully processed DLT file")
        
        return True
    
    except Exception as e:
        _log(f"Unexpected error processing DLT file: {str(e)}", "ERROR")
        return False


def watch_directory(interval: int = 5) -> None:
    """Continuously monitor directory for new DLT files."""
    _log(f"Starting DLT watcher on directory: {WATCH_DIR}")
    _log(f"Check interval: {interval} seconds")
    
    processed_files = set()
    
    while True:
        try:
            dlt_files = find_dlt_files(WATCH_DIR)
            
            for dlt_file in dlt_files:
                if dlt_file not in processed_files:
                    processed_files.add(dlt_file)
                    _log(f"\n{'='*60}")
                    _log(f"New DLT file detected: {os.path.basename(dlt_file)}")
                    _log(f"{'='*60}")
                    
                    success = process_dlt_file(dlt_file)
                    
                    if success:
                        _log(f"[OK] File processing completed successfully\n")
                    else:
                        _log(f"[ERROR] File processing failed\n")
            
            time.sleep(interval)
        
        except KeyboardInterrupt:
            _log("Watcher stopped by user")
            break
        except Exception as e:
            _log(f"Error in watch loop: {str(e)}", "ERROR")
            time.sleep(interval)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automated DLT Log Processing Monitor"
    )
    parser.add_argument(
        "--process",
        type=str,
        help="Process a single DLT file and exit"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Start continuous monitoring mode (default)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Check interval in seconds (default: 5)"
    )
    
    args = parser.parse_args()
    
    if args.process:
        # Process single file
        _log(f"Processing single DLT file: {args.process}")
        success = process_dlt_file(args.process)
        sys.exit(0 if success else 1)
    else:
        # Start watcher (default)
        watch_directory(interval=args.interval)


if __name__ == "__main__":
    main()
