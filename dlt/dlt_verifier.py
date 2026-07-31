#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dlt_verifier.py

Advanced DLT Log Verification System
- Timeline-based verification with timestamp analysis
- ECUID filtering and grouping
- Region-aware verification (EU/CN)
- Test-specific verification rules
- Detailed evidence collection and reporting

CSV Format (headless conversion):
    index | time | timestamp | Ecuid | Apid | Ctid | Payload
"""

import csv
import os
import subprocess
import tempfile
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from pathlib import Path
import re


@dataclass
class VerificationEvidence:
    """Single evidence item from DLT log."""
    index: int
    time: str
    timestamp: float
    ecuid: int
    payload: str
    apid: str
    ctid: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TestVerificationResult:
    """Result for a single test."""
    test_name: str
    status: str  # "Pass", "Fail", "Inconclusive"
    details: str
    evidence_count: int
    first_occurrence: Optional[datetime] = None
    last_occurrence: Optional[datetime] = None
    ecuids_involved: List[int] = field(default_factory=list)
    evidence: List[Dict] = field(default_factory=list)


class DLTVerificationConfig:
    """Verification configuration for different tests."""
    
    # V2X Test Verification
    V2X_RULES = {
        "name": "V2X Test Verification",
        "ecuid": "IV2X",  # Filter by ECUID
        "ctid": "STCK",   # Context ID
        "apid": "V2XM",   # Application ID
        "rules": [
            {
                "name": "Stack Initialization",
                "needle": "STACK_IN_RUNNING",
                "count": 2,  # Must appear exactly 2 times
            },
            {
                "name": "Stack Start Sequence",
                "needle": "STACK_IN_START",
                "count_min": 4,  # Must appear at least 4 times
            },
            {
                "name": "Stack Stop Event",
                "needle": "STACK_IN_STOP",
                "count_min": 1,  # Must appear at least 1 time
            },
        ]
    }
    
    # Coding Provisioning Verification
    CODING_PROV_RULES = {
        "name": "Coding Provisioning Verification",
        "ecuid": "IV2X",
        "ctid": "CONF",
        "apid": "V2XM",
        "rules": [
            {
                "name": "Antenna Configuration",
                "needle": "V2X_ANTENNAS_CONFIG value:0",
                "is_regex": False,
            },
            {
                "name": "Vehicle Height Configuration",
                "needle": "VEHICLE_HEIGHT : 150",
                "is_regex": False,
            },
            {
                "name": "Vehicle Length Configuration",
                "needle": "VEHICLE_LENGTH : 300",
                "is_regex": False,
            },
            {
                "name": "Vehicle Width Configuration",
                "needle": "VEHICLE_WIDTH : 150",
                "is_regex": False,
            },
        ]
    }
    
    # DTC (Diagnostic Trouble Code) Verification
    DTC_RULES = {
        "name": "DTC (Diagnostic Trouble Code) Verification",
        "ecuid": "IV2X",
        "rules": [
            {
                "name": "V2X Deactivated by Diagnosis",
                "needle": "DTC Info : (active|inactive) 0xb7f2d0",
                "is_regex": True,
            },
            {
                "name": "V2X Function Unavailable",
                "needle": "DTC Info : (active|inactive) 0xb7f2d1",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: HSM Access Error",
                "needle": "DTC Info : (active|inactive) 0xb7f186",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Authorization Request Failed",
                "needle": "DTC Info : (active|inactive) 0x610027",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Update Certificate List Failed",
                "needle": "DTC Info : (active|inactive) 0x61002d",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Unable to Connect to V2X SW Stack",
                "needle": "DTC Info : (active|inactive) 0x61002c",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Unable to Connect to V2X PKI Server",
                "needle": "DTC Info : (active|inactive) 0x61002b",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: File System Access Error",
                "needle": "DTC Info : (active|inactive) 0x61002a",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Enrollment Failed",
                "needle": "DTC Info : (active|inactive) 0x610028",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Authorization Download Failed",
                "needle": "DTC Info : (active|inactive) 0x610026",
                "is_regex": True,
            },
            {
                "name": "V2X PKI Client: Enrollment Renewal Failed",
                "needle": "DTC Info : (active|inactive) 0x610029",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: ECDSA Accelerator Access Error",
                "needle": "DTC Info : (active|inactive) 0x61002e",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: File System Access Error",
                "needle": "DTC Info : (active|inactive) 0x61002f",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: Missing V2X Authorization Certificate",
                "needle": "DTC Info : (active|inactive) 0x610033",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: Missing V2X Certificate List",
                "needle": "DTC Info : (active|inactive) 0x610037",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: V2X Radio Access Error",
                "needle": "DTC Info : (active|inactive) 0x610039",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: Missing Navigation Information",
                "needle": "DTC Info : (active|inactive) 0x610032",
                "is_regex": True,
            },
            {
                "name": "V2X SW Stack: Missing Map Information",
                "needle": "DTC Info : (active|inactive) 0x610031",
                "is_regex": True,
            },
        ]
    }
    
    # Cybersecurity Verification (EU/CN variant)
    CYBERSECURITY_EU_RULES = {
        "name": "Cybersecurity Verification (EU Region)",
        "ecuid": "IV2X",
        "region": "EU",
        "rules": [
            {
                "name": "Message Verification Failed",
                "needle": "Call unwrap callback from message verify with result: Invalid signature",
                "is_regex": False,
            },
            {
                "name": "Message Verification Success (EU)",
                "needle": "Call unwrap callback from message verify with result: Verified \\(1\\)",
                "is_regex": True,
            },
            {
                "name": "Replayed Message Detection",
                "needle": "Call unwrap callback from message verify with result: Replayed message \\(15\\)",
                "is_regex": False,
            }
        ]
    }
    
    CYBERSECURITY_CN_RULES = {
        "name": "Cybersecurity Verification (CN Region)",
        "ecuid": "IV2X",
        "region": "CN",
        "rules": [
            {
                "name": "Message Verification Failed",
                "needle": "Call unwrap callback from message verify with result: Invalid signature",
                "is_regex": False,
            },
            {
                "name": "Message Verification Success (CN)",
                "needle": "Call unwrap callback from message verify with result: Verified \\(1\\)",
                "is_regex": True,
            },
            {
                "name": "Replayed Message Detection",
                "needle": "Call unwrap callback from message verify with result: Replayed message \\(15\\)",
                "is_regex": False,
            }
        ]
    }
    
    # Diagnostics Verification
    DIAGNOSTICS_RULES = {
        "name": "Diagnostics Verification",
        "ecuid": "IV2X",
        "rules": [
            {
                "name": "Antenna Configuration",
                "needle": "V2X_ANTENNAS_CONFIG value:0",
                "is_regex": False,
            },
            {
                "name": "Vehicle Height Configuration",
                "needle": "VEHICLE_HEIGHT : 150",
                "is_regex": False,
            },
            {
                "name": "Vehicle Length Configuration",
                "needle": "VEHICLE_LENGTH : 300",
                "is_regex": False,
            },
            {
                "name": "Vehicle Width Configuration",
                "needle": "VEHICLE_WIDTH : 150",
                "is_regex": False,
            },
        ]
    }


class DLTVerifier:
    """Advanced DLT log verifier with timeline and ECUID support."""
    
    def __init__(self, dlt_file: str):
        """
        Initialize verifier.
        
        Args:
            dlt_file: Path to DLT or CSV file
                     - If DLT: will be converted to CSV internally
                     - If CSV: used directly
        """
        self.input_file = dlt_file
        self.csv_file = dlt_file
        self.rows = []
        self.has_header = False
        
        # Check if input is DLT and convert to CSV if needed
        if dlt_file.lower().endswith('.dlt'):
            self.csv_file = self._convert_dlt_to_csv(dlt_file)
            if not self.csv_file:
                raise RuntimeError(f"Failed to convert DLT file: {dlt_file}")
        
        self._load_csv()
    
    def _convert_dlt_to_csv(self, dlt_file: str) -> Optional[str]:
        """
        Convert DLT file to CSV using dlt-viewer.exe.
        
        Args:
            dlt_file: Path to DLT file
        
        Returns:
            Path to generated CSV file, or None if conversion failed
        """
        # Create temp CSV file
        temp_dir = tempfile.gettempdir()
        temp_csv = os.path.join(temp_dir, f"dlt_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        # Try method 1: dlt-viewer.exe from SDK
        sdk_path = Path(__file__).resolve().parent / "DltViewerSDK-2.21.3" / "dlt-viewer.exe"
        if sdk_path.exists():
            try:
                result = subprocess.run(
                    [str(sdk_path), "-s", "-csv", "-c", dlt_file, temp_csv],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0 and os.path.exists(temp_csv) and os.path.getsize(temp_csv) > 0:
                    print(f"[OK] DLT converted to CSV (SDK): {temp_csv}")
                    return temp_csv
            except Exception as e:
                print(f"[WARN] SDK conversion failed: {e}")
        
        # Try method 2: System dlt-viewer
        try:
            result = subprocess.run(
                ["dlt-viewer", "-s", "-csv", "-c", dlt_file, temp_csv],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0 and os.path.exists(temp_csv) and os.path.getsize(temp_csv) > 0:
                print(f"[OK] DLT converted to CSV (system): {temp_csv}")
                return temp_csv
        except Exception as e:
            print(f"[WARN] System conversion failed: {e}")
        
        print(f"[ERROR] Failed to convert DLT file: {dlt_file}")
        return None
    
    @staticmethod
    def parse_version(version_str: str) -> Tuple[str, str]:
        """
        Parse device version and extract date and variant.
        
        Expected format: v{x}.{x}.{x}.{device_variant}.oem_{date}
        Example: v040.040.065.iconsf25.oem_260525
        
        Args:
            version_str: Version string
        
        Returns:
            Tuple of (device_variant, date)
        """
        pattern = r'v[\d.]+\.([a-z0-9]+)\.oem_(\d{6})'
        match = re.search(pattern, version_str, re.IGNORECASE)
        
        if match:
            device_variant = match.group(1)
            date = match.group(2)
            return device_variant, date
        
        return "unknown", "unknown"
    
    @staticmethod
    def find_dlt_for_version(version: str, base_path: str = "logs/sanity") -> Optional[str]:
        """
        Find DLT file for a specific version.
        
        Directory structure: {base_path}/{date}/{device_variant}/basic_sanity_{version}.dlt
        
        Args:
            version: Device version string
            base_path: Base directory for sanity logs
        
        Returns:
            Path to DLT file if found, None otherwise
        """
        device_variant, date = DLTVerifier.parse_version(version)
        
        # Build expected path
        version_dir = Path(base_path) / date / device_variant
        
        if not version_dir.exists():
            return None
        
        # Try exact filename
        expected_file = version_dir / f"basic_sanity_{version}.dlt"
        if expected_file.exists():
            return str(expected_file)
        
        # Try any basic_sanity_*.dlt file
        dlt_files = list(version_dir.glob("basic_sanity_*.dlt"))
        if dlt_files:
            return str(dlt_files[0])
        
        return None
    
    @staticmethod
    def create_version_directory(version: str, base_path: str = "logs/sanity") -> str:
        """
        Create version-specific directory structure.
        
        Expected structure: {base_path}/{date}/{device_variant}/
        
        Args:
            version: Device version string
            base_path: Base directory for sanity logs
        
        Returns:
            Path to created directory
        """
        device_variant, date = DLTVerifier.parse_version(version)
        version_dir = Path(base_path) / date / device_variant
        version_dir.mkdir(parents=True, exist_ok=True)
        return str(version_dir)
    
    @staticmethod
    def get_expected_dlt_filename(version: str) -> str:
        """
        Get expected DLT filename for version.
        
        Expected format: basic_sanity_{full_version}.dlt
        
        Args:
            version: Device version string
        
        Returns:
            Expected filename
        """
        return f"basic_sanity_{version}.dlt"
    
    def _load_csv(self) -> None:
        """Load and parse CSV file."""
        if not os.path.exists(self.csv_file):
            raise FileNotFoundError(f"CSV file not found: {self.csv_file}")
        
        with open(self.csv_file, "r", encoding="utf-8", errors="replace") as f:
            # Detect if file has header
            first_line = f.readline()
            f.seek(0)
            
            if first_line.startswith("index") or "timestamp" in first_line.lower():
                self.has_header = True
            
            reader = csv.reader(f, delimiter=',', quotechar='"')
            
            if self.has_header:
                header = next(reader)
                self.header = header
            else:
                # Headless format - use standard header
                self.header = ["index", "time", "timestamp", "Ecuid", "Apid", "Ctid", "Payload"]
            
            for row in reader:
                if len(row) >= len(self.header):
                    self.rows.append(row)
    
    def _parse_row(self, row: List) -> Dict:
        """Parse a CSV row into structured data."""
        parsed = {}
        for i, header in enumerate(self.header):
            if i < len(row):
                parsed[header.lower()] = row[i]
        return parsed
    
    def filter_by_ecuid(self, ecuid: str) -> List[Dict]:
        """Filter rows by ECUID."""
        filtered = []
        for row in self.rows:
            parsed = self._parse_row(row)
            if parsed.get("ecuid") == ecuid:
                filtered.append(parsed)
        return filtered
    
    def filter_by_apid_ctid(self, apid: str, ctid: str) -> List[Dict]:
        """Filter rows by APID and CTID."""
        filtered = []
        for row in self.rows:
            parsed = self._parse_row(row)
            row_apid = parsed.get("apid", "").strip()
            row_ctid = parsed.get("ctid", "").strip()
            
            # Support wildcards
            apid_match = apid == "*" or row_apid == apid or (apid.endswith("*") and row_apid.startswith(apid[:-1]))
            ctid_match = ctid == "*" or row_ctid == ctid or (ctid.endswith("*") and row_ctid.startswith(ctid[:-1]))
            
            if apid_match and ctid_match:
                filtered.append(parsed)
        
        return filtered
    
    def search_payload(self, rows: List[Dict], needle: str, is_regex: bool = False) -> List[Dict]:
        """Search for pattern in payload."""
        matches = []
        
        for row in rows:
            payload = row.get("payload", "").lower()
            needle_lower = needle.lower()
            
            if is_regex:
                try:
                    if re.search(needle_lower, payload):
                        matches.append(row)
                except re.error:
                    # Fallback to string search if regex fails
                    if needle_lower in payload:
                        matches.append(row)
            else:
                if needle_lower in payload:
                    matches.append(row)
        
        return matches
    
    def verify_v2x_stack(self) -> TestVerificationResult:
        """Verify V2X stack initialization with strict event counts."""
        config = DLTVerificationConfig.V2X_RULES
        
        # Filter by ECUID and CTID
        filtered = self.filter_by_ecuid(config["ecuid"])
        filtered = [r for r in filtered if r.get("ctid") == config["ctid"] and r.get("apid") == config["apid"]]
        
        evidence = []
        running_count = 0
        start_count = 0
        stop_count = 0
        
        # Count stack lifecycle events
        for row in filtered:
            payload = row.get("payload", "")
            
            if "STACK_IN_RUNNING" in payload:
                running_count += 1
                evidence.append(row)
            elif "STACK_IN_START" in payload:
                start_count += 1
                evidence.append(row)
            elif "STACK_IN_STOP" in payload:
                stop_count += 1
                evidence.append(row)
        
        # Verify requirements:
        # STACK_IN_RUNNING: exactly 2
        # STACK_IN_START: >= 4
        # STACK_IN_STOP: >= 1
        running_ok = running_count == 2
        start_ok = start_count >= 4
        stop_ok = stop_count >= 1
        
        if running_ok and start_ok and stop_ok:
            status = "Pass"
            details = f"V2X stack initialized successfully (RUNNING: {running_count}/2, START: {start_count}>=4, STOP: {stop_count}>=1)"
        elif (running_ok or running_count > 0) and (start_ok or start_count > 0) and (stop_ok or stop_count > 0):
            status = "Inconclusive"
            details = f"Partial stack initialization (RUNNING: {running_count}/2, START: {start_count}>=4, STOP: {stop_count}>=1)"
        else:
            status = "Fail"
            missing = []
            if running_count == 0:
                missing.append("STACK_IN_RUNNING")
            if start_count == 0:
                missing.append("STACK_IN_START")
            if stop_count == 0:
                missing.append("STACK_IN_STOP")
            details = f"Missing events: {', '.join(missing)}"
        
        ecuids = [r.get("ecuid", "") for r in evidence]
        
        return TestVerificationResult(
            test_name="V2X Stack",
            status=status,
            details=details,
            evidence_count=len(evidence),
            ecuids_involved=list(set(ecuids)),
            evidence=[r for r in evidence]
        )
    
    def verify_coding_provisioning(self) -> TestVerificationResult:
        """Verify coding provisioning (vehicle configuration) - all 4 parameters must be found."""
        config = DLTVerificationConfig.CODING_PROV_RULES
        
        filtered = self.filter_by_ecuid(config["ecuid"])
        filtered = [r for r in filtered if r.get("ctid") == config["ctid"] and r.get("apid") == config["apid"]]
        
        evidence = []
        found_items = {
            "V2X_ANTENNAS_CONFIG value:0": False,
            "VEHICLE_HEIGHT : 150": False,
            "VEHICLE_LENGTH : 300": False,
            "VEHICLE_WIDTH : 150": False,
        }
        
        for row in filtered:
            payload = row.get("payload", "")
            
            for key in found_items:
                if key in payload:
                    found_items[key] = True
                    evidence.append(row)
        
        # All 4 required parameters must be found
        all_found = all(found_items.values())
        
        if all_found:
            status = "Pass"
            details = "All coding provisioning parameters verified"
        elif any(found_items.values()):
            status = "Inconclusive"
            missing = [k for k, v in found_items.items() if not v]
            details = f"Partial provisioning - Missing: {', '.join(missing)}"
        else:
            status = "Fail"
            details = "No coding provisioning parameters found"
        
        ecuids = [r.get("ecuid", "") for r in evidence]
        
        return TestVerificationResult(
            test_name="Coding Provisioning",
            status=status,
            details=details,
            evidence_count=len(evidence),
            ecuids_involved=list(set(ecuids)),
            evidence=[r for r in evidence]
        )
    
    def verify_cybersecurity(self, region: str = "Universal") -> TestVerificationResult:
        """
        Verify cybersecurity - region-agnostic, just check for required patterns.
        
        Args:
            region: Ignored - kept for compatibility
        """
        filtered = self.filter_by_ecuid("IV2X")
        evidence = []
        
        # Look for all three verification states
        sig_invalid = 0
        sig_verified = 0
        replayed = 0
        
        for row in filtered:
            payload = row.get("payload", "").lower()
            
            if "invalid signature" in payload:
                sig_invalid += 1
                evidence.append(row)
            elif "verified (1)" in payload:
                sig_verified += 1
                evidence.append(row)
            elif "replayed message" in payload:
                replayed += 1
                evidence.append(row)
        
        # Check if all three patterns are found (region-agnostic)
        if sig_invalid > 0 and sig_verified > 0 and replayed > 0:
            status = "Pass"
            details = f"All security verification patterns found (Invalid: {sig_invalid}, Verified: {sig_verified}, Replayed: {replayed})"
        elif (sig_invalid > 0 and sig_verified > 0) or (sig_invalid > 0 and replayed > 0) or (sig_verified > 0 and replayed > 0):
            status = "Fail"
            missing = []
            if sig_invalid == 0:
                missing.append("Invalid signature")
            if sig_verified == 0:
                missing.append("Verified message")
            if replayed == 0:
                missing.append("Replayed message")
            details = f"Some patterns found but missing: {', '.join(missing)}"
        else:
            status = "Fail"
            details = f"Insufficient security patterns (Invalid: {sig_invalid}, Verified: {sig_verified}, Replayed: {replayed})"
        
        ecuids = [r.get("ecuid", "") for r in evidence]
        
        return TestVerificationResult(
            test_name="Cybersecurity",
            status=status,
            details=details,
            evidence_count=len(evidence),
            ecuids_involved=list(set(ecuids)),
            evidence=[r for r in evidence]
        )
    
    def verify_dtc(self) -> TestVerificationResult:
        """Verify DTC (Diagnostic Trouble Codes) - BOTH active and inactive must be found for each code."""
        config = DLTVerificationConfig.DTC_RULES
        
        filtered = self.filter_by_ecuid(config["ecuid"])
        evidence = []
        dtc_states = {}  # key: code (lowercase), value: set of states found
        
        # Map hex codes to rule names from config
        code_to_name = {}
        for rule in config["rules"]:
            needle = rule["needle"]
            # Extract hex code from needle (e.g., "0xb7f2d0")
            match = re.search(r'0x[0-9a-f]+', needle.lower())
            if match:
                code = match.group()
                code_to_name[code] = rule["name"]
        
        for row in filtered:
            payload = row.get("payload", "").lower()
            
            # Look for DTC patterns - case insensitive
            dtc_pattern = r"dtc info : (active|inactive) (0x[0-9a-f]+)"
            matches = re.findall(dtc_pattern, payload)
            
            for match in matches:
                state, code = match
                
                if code not in dtc_states:
                    dtc_states[code] = set()
                
                dtc_states[code].add(state)
                evidence.append(row)
        
        # Check if any code has BOTH active and inactive states
        codes_with_both = {code: states for code, states in dtc_states.items() if len(states) == 2}
        codes_with_one = {code: states for code, states in dtc_states.items() if len(states) == 1}
        
        if codes_with_both:
            status = "Pass"
            details = f"DTC verification passed - {len(codes_with_both)} codes with BOTH states found"
        elif dtc_states:
            status = "Fail"
            details = "DTC verification failed - Following codes missing required state(s):\n"
            for code in sorted(code_to_name.keys()):
                if code in codes_with_one:
                    states = dtc_states[code]
                    missing = "inactive" if "active" in states else "active"
                    rule_name = code_to_name[code]
                    details += f"  • {rule_name} ({code}): has {list(states)[0]}, missing {missing}\n"
                elif code not in dtc_states:
                    rule_name = code_to_name[code]
                    details += f"  • {rule_name} ({code}): NOT FOUND\n"
        else:
            status = "Fail"
            details = "No DTC information found in logs"
        
        ecuids = [r.get("ecuid", "") for r in evidence]
        
        return TestVerificationResult(
            test_name="DTC",
            status=status,
            details=details,
            evidence_count=len(evidence),
            ecuids_involved=list(set(ecuids)),
            evidence=[r for r in evidence]
        )
    
    
    def verify_all(self, regions: List[str] = None) -> Dict[str, TestVerificationResult]:
        """
        Run all verifications.
        
        Args:
            regions: Ignored - kept for compatibility, verification is region-agnostic
        
        Returns:
            Dictionary of verification results
        """
        results = {}
        
        # V2X Stack
        results["V2X Stack"] = self.verify_v2x_stack()
        
        # Coding Provisioning
        results["Coding Provisioning"] = self.verify_coding_provisioning()
        
        # Cybersecurity (region-agnostic)
        results["Cybersecurity"] = self.verify_cybersecurity()
        
        # DTC
        results["DTC"] = self.verify_dtc()
        
        return results
    
    def generate_report(
        self,
        version: str,
        results: Dict[str, TestVerificationResult],
        include_evidence: bool = True
    ) -> Dict:
        """
        Generate comprehensive verification report.
        
        Args:
            version: Device version string
            results: Dictionary of verification results
            include_evidence: Include detailed evidence in report
        
        Returns:
            Report dictionary (JSON-serializable)
        """
        # Summary statistics
        total = len(results)
        passed = sum(1 for r in results.values() if r.status == "Pass")
        failed = sum(1 for r in results.values() if r.status == "Fail")
        inconclusive = sum(1 for r in results.values() if r.status == "Inconclusive")
        
        # Build report
        report = {
            "timestamp": datetime.now().isoformat(),
            "version": version,
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "inconclusive": inconclusive,
                "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
            },
            "results": {}
        }
        
        for test_name, result in results.items():
            test_report = {
                "status": result.status,
                "details": result.details,
                "evidence_count": result.evidence_count,
                "ecuids_involved": result.ecuids_involved,
            }
            
            if include_evidence and result.evidence:
                # Include first 5 evidence items
                test_report["evidence_samples"] = result.evidence[:5]
            
            report["results"][test_name] = test_report
        
        return report
    
    def generate_readable_report(self, results: Dict[str, TestVerificationResult]) -> str:
        """
        Generate a human-readable verification report.
        
        Args:
            results: Dictionary of verification results
        
        Returns:
            Formatted string report
        """
        # Summary statistics
        total = len(results)
        passed = sum(1 for r in results.values() if r.status == "Pass")
        failed = sum(1 for r in results.values() if r.status == "Fail")
        inconclusive = sum(1 for r in results.values() if r.status == "Inconclusive")
        
        report_lines = []
        report_lines.append("\n" + "=" * 70)
        report_lines.append("DLT VERIFICATION REPORT")
        report_lines.append("=" * 70)
        report_lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Summary section
        report_lines.append("SUMMARY")
        report_lines.append("-" * 70)
        report_lines.append(f"Total Tests: {total}")
        report_lines.append(f"Passed:      {passed} [OK]")
        report_lines.append(f"Failed:      {failed} [ERROR]")
        report_lines.append(f"Inconclusive: {inconclusive} [?]")
        pass_rate = (passed / total * 100) if total > 0 else 0
        report_lines.append(f"Pass Rate:   {pass_rate:.1f}%")
        report_lines.append("")
        
        # Detailed results section
        report_lines.append("DETAILED RESULTS")
        report_lines.append("-" * 70)
        
        for test_name, result in results.items():
            status_symbol = "[+]" if result.status == "Pass" else ("[!]" if result.status == "Fail" else "[?]")
            status_line = f"{test_name:<40} {status_symbol} {result.status}"
            report_lines.append(status_line)
            
            if result.status != "Pass":
                # Show details for failed/inconclusive tests
                details_lines = result.details.split("\n")
                for detail in details_lines:
                    if detail.strip():
                        report_lines.append(f"  -> {detail.strip()}")
            else:
                # For passed tests, just show confirmation
                report_lines.append(f"  -> All checks passed")
            
            report_lines.append("")
        
        report_lines.append("=" * 70)
        
        return "\n".join(report_lines)


def verify_dlt_file(dlt_or_csv_file: str) -> Dict[str, TestVerificationResult]:
    """
    Quick verification function.
    
    Args:
        dlt_or_csv_file: Path to DLT or CSV file
    
    Returns:
        Dictionary of verification results
    """
    verifier = DLTVerifier(dlt_or_csv_file)
    results = verifier.verify_all()
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dlt_verifier.py <dlt_or_csv_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"[ERROR] File not found: {input_file}")
        sys.exit(1)
    
    print(f"[INFO] Verifying: {input_file}")
    
    try:
        verifier = DLTVerifier(input_file)
        results = verifier.verify_all()
        
        # Print human-readable report
        readable_report = verifier.generate_readable_report(results)
        print(readable_report)
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        sys.exit(1)
