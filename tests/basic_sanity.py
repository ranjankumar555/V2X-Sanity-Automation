"""Basic sanity test runner for Coding Provisioning -> Diagnostics -> DTC -> Cybersecurity -> V2X.

Goals:
- Single stack activation/deactivation for the full sequence
- Single DLT capture window (user starts capture once before run)
- Push prerequisites and set file permissions at the very beginning
- Emit timeline markers between each test section
"""

from pathlib import Path
from typing import List, Tuple
import datetime
import os
import sys
import time

try:
    from tests.test_base import TestBase
except ImportError:  # pragma: no cover - fallback for direct script execution
    from test_base import TestBase
from dlt.testbase_integration import DLTVerificationMixin
from dlt.dlt_verifiy import verify_dlt_file
from framework.helper import Helper
from test_certificate_download import TestCertificateDownload

class BasicSanityTest(DLTVerificationMixin, TestBase):
    """Run the requested five tests in one continuous sequence (basic sanity test).
    
    Includes automatic DLT verification after test completion.
    """

    # Cybersecurity file paths
    EU_CERT_PATH = r"..\Cybersecurity\Snake oil EU\signer_1_EU\."
    EU_CN_FILE_PATH = r"..\Cybersecurity\pushfile_data_v2xmgr_etc\."
    REMOTE_ETC_PATH = "/data/v2xmgr/etc/"

    # Coding provisioning file paths
    EU_PROV_XML = r"..\Cybersecurity\Snake Oil EU\EU_Prov_File\prov.xml"
    CN_PROV_XML = r"..\Cybersecurity\Snake Oil CN\CN_Prov_File\prov.xml"

    def __init__(self, test_name: str, log_file: str, adb_cmd: str = "adb1", use_adb: bool = True, **kwargs):
        super().__init__(test_name=test_name, log_file=log_file, adb_cmd=adb_cmd, use_adb=use_adb, **kwargs)
        self.timeline_file = str(Path(log_file).parent / "basic_sanity_timeline.log")
        self.timing_file = str(Path(log_file).parent / "basic_sanity_timing.log")
        
        # Initialize execution timing tracking
        self.section_start_times = {}  # {section_name: timestamp}
        self.section_durations = {}    # {section_name: duration_seconds}
        
        # Initialize certificate download handler for devcoding prerequisites
        # Use same log file as main test to consolidate all output
        self.devcoding_imei = TestCertificateDownload(
            test_name="Certificate Download (Basic Sanity)",
            log_file=log_file
        )
        # Override with main test's logger to ensure all output goes to same file
        self.devcoding_imei.logger = self.logger
        
        # Initialize Helper instance with the necessary attributes for instance methods
        self.helper = Helper(self.logger)
        self.helper.shell = self.shell
        self.helper.config = self.config
        self.helper._wrap_command = self._wrap_command

    def get_commands(self):
        """Not used in unified mode; sections are executed directly."""
        return []

    def _timeline_marker(self, label: str) -> None:
        """Write timeline marker to both test log and dedicated timeline log."""
        host_ts = datetime.datetime.now().isoformat(timespec="seconds")
        device_ts = self.shell.run("date '+%Y-%m-%d %H:%M:%S %Z'", timeout=5).strip()
        marker = f"[TIMELINE] {label} | host={host_ts} | device={device_ts}"

        self.logger.print_default("\n" + "-" * 80)
        self.logger.print_default(marker)
        
        # Track execution time
        self._track_execution_time(label)
        
        self.logger.print_default("-" * 80)

        os.makedirs(os.path.dirname(self.timeline_file) or ".", exist_ok=True)
        with open(self.timeline_file, "a", encoding="utf-8") as f:
            f.write(marker + "\n")

    def _track_execution_time(self, label: str) -> None:
        """Track execution time for each test section."""
        current_time = time.time()
        
        if label.startswith("START_"):
            # Record start time
            section_name = label.replace("START_", "")
            self.section_start_times[section_name] = current_time
            
        elif label.startswith("END_"):
            # Calculate and log execution time
            section_name = label.replace("END_", "")
            if section_name in self.section_start_times:
                duration = current_time - self.section_start_times[section_name]
                self.section_durations[section_name] = duration
                
                # Log the duration
                duration_str = self._format_duration(duration)
                self.logger.print_default(f"[TIMING] {section_name}: {duration_str}")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in a readable format (HH:MM:SS)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _log_execution_summary(self) -> None:
        """Log a summary of execution times for all sections."""
        self.logger.print_default("\n" + "=" * 80)
        self.logger.print_default("EXECUTION TIME SUMMARY")
        self.logger.print_default("=" * 80)
        
        # Calculate overhead (time between START_SEQUENCE and END_SEQUENCE minus sum of 5 tests)
        sequence_duration = self.section_durations.get("SEQUENCE", 0)
        test_sections = ["CODING_PROVISIONING", "DIAGNOSTICS", "DTC", "CYBERSECURITY", "V2X"]
        tests_total = sum(self.section_durations.get(section, 0) for section in test_sections)
        overhead_duration = sequence_duration - tests_total
        
        # Display 5 individual tests
        total_duration = 0
        for section_name in test_sections:
            if section_name in self.section_durations:
                duration = self.section_durations[section_name]
                duration_str = self._format_duration(duration)
                self.logger.print_default(f"  {section_name:25s}: {duration_str}")
                total_duration += duration
        
        # Display overhead
        overhead_str = self._format_duration(overhead_duration)
        self.logger.print_default(f"  {'OVERHEAD':25s}: {overhead_str}")
        total_duration += overhead_duration
        
        self.logger.print_default("-" * 80)
        total_str = self._format_duration(total_duration)
        self.logger.print_default(f"  {'TOTAL':25s}: {total_str}")
        self.logger.print_default("=" * 80 + "\n")
        
        # Also write to timing file
        self._write_timing_summary()

    def _write_timing_summary(self) -> None:
        """Write execution timing summary to a dedicated timing log file."""
        os.makedirs(os.path.dirname(self.timing_file) or ".", exist_ok=True)
        
        with open(self.timing_file, "w", encoding="utf-8") as f:
            f.write("EXECUTION TIME SUMMARY\n")
            f.write("=" * 80 + "\n")
            
            # Calculate overhead (time between START_SEQUENCE and END_SEQUENCE minus sum of 5 tests)
            sequence_duration = self.section_durations.get("SEQUENCE", 0)
            test_sections = ["CODING_PROVISIONING", "DIAGNOSTICS", "DTC", "CYBERSECURITY", "V2X"]
            tests_total = sum(self.section_durations.get(section, 0) for section in test_sections)
            overhead_duration = sequence_duration - tests_total
            
            # Write 5 individual tests
            total_duration = 0
            for section_name in test_sections:
                if section_name in self.section_durations:
                    duration = self.section_durations[section_name]
                    duration_str = self._format_duration(duration)
                    f.write(f"  {section_name:25s}: {duration_str}\n")
                    total_duration += duration
            
            # Write overhead
            overhead_str = self._format_duration(overhead_duration)
            f.write(f"  {'OVERHEAD':25s}: {overhead_str}\n")
            total_duration += overhead_duration
            
            f.write("-" * 80 + "\n")
            total_str = self._format_duration(total_duration)
            f.write(f"  {'TOTAL':25s}: {total_str}\n")
            f.write("=" * 80 + "\n")

    def _cleanup_logs(self) -> None:
        """Clear all log files and timeline to ensure fresh start for each run."""
        log_dir = Path(self.config.log_file).parent
        
        # Clear main test log by truncating instead of deleting (avoids file locking issues on Windows)
        if os.path.exists(self.config.log_file):
            try:
                with open(self.config.log_file, "w", encoding="utf-8") as f:
                    f.truncate(0)  # Truncate to empty file
                print(f"[CLEANUP] Cleared: {self.config.log_file}")
            except Exception as e:
                print(f"[CLEANUP] Could not clear log file: {e}. Continuing anyway...")
        
        # Clear timeline log by truncating
        if os.path.exists(self.timeline_file):
            try:
                with open(self.timeline_file, "w", encoding="utf-8") as f:
                    f.truncate(0)
                print(f"[CLEANUP] Cleared: {self.timeline_file}")
            except Exception as e:
                print(f"[CLEANUP] Could not clear timeline: {e}")
        
        # Clear timing log by truncating
        if os.path.exists(self.timing_file):
            try:
                with open(self.timing_file, "w", encoding="utf-8") as f:
                    f.truncate(0)
                print(f"[CLEANUP] Cleared: {self.timing_file}")
            except Exception as e:
                print(f"[CLEANUP] Could not clear timing log: {e}")
        
        # Reset timing tracking dictionaries
        self.section_start_times = {}
        self.section_durations = {}
        
        # Ensure log directory exists for fresh start
        os.makedirs(log_dir, exist_ok=True)
        print(f"[CLEANUP] Log directory ready: {log_dir}")

    def _run_wrapped_commands(self, commands: List[Tuple[str, int]]) -> None:
        """Run mostly-sldd commands with SOP wrapping support."""
        batch = []
        for cmd, delay in commands:
            wrapped = self._wrap_command(cmd)
            batch.append((wrapped, delay))
        self.shell.run_batch(batch, default_delay=0)

    
    def _push_prerequisites_once(self) -> None:
        """Push all prerequisite files and apply permissions before any test section."""
        self.logger.print_green("[Initial Setup]=== Initial setup started ===")
        
        # Step 0: Create and setup versioned directory
        try:
            from dlt.version_parser import VersionParser
            
            if self.config.version_output:
                parser = VersionParser(self.config.version_output.strip())
                version_dir = parser.get_directory_path("D:\\SANITY")
                version_dir.mkdir(parents=True, exist_ok=True)
                self.logger.print_green(f"[Initial Setup] Versioned directory created: {version_dir}")
                
                # Store for later use
                self.versioned_dir = version_dir
            else:
                self.logger.print_red("[Initial Setup] Device version not available for directory setup")
                self.versioned_dir = None
        except Exception as e:
            self.logger.print_red(f"[Initial Setup] Error creating versioned directory: {e}")
            self.versioned_dir = None
        
        # self.logger.print_default("Set IMEI")
        # self.shell.run(self._wrap_command("sldd telephony factorysetimei 354028100010134"))
        if Helper.is_binary_sop(self.config.version_output):
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger)
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger, path="/data/")

        # Coding provisioning prerequisite (prov.xml) for Master mode.
        if not Helper.is_binary_sop(self.config.version_output):
            self.shell.run("smack_admin")
            self.shell.run("echo -> /sys/fs/smackfs/onlycap")
            self.shell.run("exit")

            region_eu = Helper.is_region_eu(self.files, self.logger)
            prov_source = self.EU_PROV_XML if region_eu else self.CN_PROV_XML
            if os.path.exists(prov_source):
                self.files.push(prov_source, "/data/config-service/")
            else:
                self.logger.print_red(f"[Initial Setup]prov.xml not found: {prov_source}")

        # Cybersecurity prerequisites.
        self.shell.run("mkdir -p /data/v2xmgr/etc/MBD")

        if os.path.isdir(self.EU_CN_FILE_PATH):
            self.files.push_folder(self.EU_CN_FILE_PATH, self.REMOTE_ETC_PATH)
        else:
            self.logger.print_red(f"[Initial Setup]Cybersecurity folder not found: {self.EU_CN_FILE_PATH}")

        if os.path.isdir(self.EU_CERT_PATH):
            self.files.push_folder(self.EU_CERT_PATH, "/data/v2xmgr/etc/MBD/")
        else:
            self.logger.print_red(f"[Initial Setup]EU cert folder not found: {self.EU_CERT_PATH}")

        self.shell.run("chmod 777 /data/v2xmgr/etc/MBD/*")
        self.shell.run("if [ -f /data/v2xmgr/etc/rio_inject.txt ]; then mv /data/v2xmgr/etc/rio_inject.txt /data/v2xmgr/etc/rio_inject; fi")
        self.shell.run("chmod 777 /data/v2xmgr/etc/rio_inject /data/v2xmgr/etc/*.bin")
        self.shell.run("ls -l /data/v2xmgr/etc/")

        self.logger.print_green("[Initial Setup]Cybersecurity and coding_provisioning files pushed and permissions set successfully.")

        self.logger.print_green("[Initial Setup]=== Initial setup completed ===")

    def _run_coding_provisioning(self) -> None:
        self.logger.print_green("\n[CODING PROVISIONING]=== Running Coding Provisioning test ===")
        commands = [
            ("sldd cfg reload 2 0 /data/config-service/prov.xml", 2),
            ("sldd cfg reload 0 0 /data/config-service/coding.txt", 2),
            ("sldd cfg reload 0 0 /data/config-service/coding.txt", 2),
            ("sldd cfg reload 0 0 /data/config-service/coding.txt", 2),
        ]
        self._run_wrapped_commands(commands)
        self.logger.print_green("\n[CODING PROVISIONING]=== Coding Provisioning test Completed ===")

    def _run_diagnostics(self) -> None:
        self.logger.print_green("\n[DIAGNOSTICS]=== Running Diagnostics test ===")
        commands = [
            ("sldd v2xmgr readDiag RDBI_V2X_SECURITY", 2),
            ("sldd v2xmgr readDiag RDBI_V2X_RADIO", 2),
            ("sldd v2xmgr readDiag RDBI_V2X_STACK_CONFIGURATION", 2),
            ("sldd v2xmgr readDiag RDBI_V2X_HSM", 2),
            ("sldd v2xmgr readDiag RDBI_V2X_COMPENSATOR_LNA", 2),
            ("sldd Diag readDid 43a0", 2),
            ("sldd Diag writeDid 43A0 00", 2),
            ("sldd Diag readDid 43A0", 2),
            ("sldd Diag writeDid 43A0 01", 2),
            ("sldd Diag readDid 43A0", 2),
        ]
        self._run_wrapped_commands(commands)
        # last command of this test need reboot. To ensure clean state for the following cybersecurity and V2X sections, we reboot here instead of waiting for the end of the full sequence.
        self.logger.print_green("\n[DIAGNOSTICS]=== Diagnostics test Completed ===")
        self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 0"))
        self.logger.print_default("[REBOOT] Reboot initiated, waiting 30 seconds for device reconnection...")
        self.shell.run("reboot")
        time.sleep(30)
        
    def _run_dtc(self) -> None:
        self.logger.print_green("\n[DTC]=== Running DTC test ===")
        test_cases = [
            "PKI_ERROR_AUTH_REQ_FAILED",
            "PKI_ERROR_CERT_LIST_UPDATE_FAILED",
            "PKI_ERROR_V2X_STACK_CONNECTION_ERROR",
            "PKI_ERROR_PKI_SERVER_CONNECTION_ERROR",
            "PKI_ERROR_FS_ACCESS_ERROR",
            "PKI_ERROR_ENROLLMENT_FAILED",
            "PKI_ERROR_AUTH_DOWNLOAD_FAILED",
            "PKI_ERROR_REENROLLMENT_FAILED",
            "STACK_ERROR_ECDSA_ACCESS_ERROR",
            "STACK_ERROR_FS_ACCESS_ERROR",
            "STACK_ERROR_HSM_ACCESS_ERROR",
            "STACK_ERROR_MISSING_AUTH_CERT",
            "STACK_ERROR_MISSING_CERT_LIST",
        ]
        count = 1
        for code in test_cases:
            self.logger.print_blue(f"[DTC]Test {count}: {code}")
            self.shell.run(self._wrap_command(f"sldd v2xmgr setDTC {code} 1"))
            time.sleep(1)
            self.shell.run(self._wrap_command(f"sldd v2xmgr setDTC {code} 0"))
            time.sleep(1)
            count += 1
        
        self.logger.print_blue(f"[DTC]Test {count}: systemctl stop its")
        self.shell.run("systemctl stop its")
        time.sleep(10)
        self.shell.run("systemctl start its")
        time.sleep(5)
        count += 1

        self.logger.print_blue(f"[DTC]Test {count}: STACK_ERROR_MISSING_NAV_INFO")
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_NAV_INFO 1"))
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_NAV_INFO 0"))
        time.sleep(1)
        count += 1
        self.logger.print_blue(f"[DTC]Test {count}: STACK_ERROR_MISSING_MAP_INFO")
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_MAP_INFO 1"))
        time.sleep(1)
        self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_MISSING_MAP_INFO 0"))
        time.sleep(1)

        count += 1
        self.logger.print_blue(f"[DTC]Test {count}: STACK_ERROR_RADIO_ACCESS_ERROR")
        for _ in range(4):
            time.sleep(5)
            self.shell.run(self._wrap_command("sldd v2xmgr setDTC STACK_ERROR_RADIO_ACCESS_ERROR 1"))
            time.sleep(10)


        # reboot after DTC test cases to ensure clean state for cybersecurity and V2X sections
        self.logger.print_default("[REBOOT] Reboot initiated, waiting 30 seconds for device reconnection...")
        self.shell.run("reboot")
        time.sleep(30)

        # since stack is off after reboot, we need to turn it on again for the remaining sections
        # Here after reboot, shell should reconnect automatically.
        if Helper.is_binary_sop(self.config.version_output):
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger)
        self.helper.activate_stack()

        self.logger.print_blue(f"[DTC]Test {count}: Diag writeDid 43A0 00")
        self.shell.run(self._wrap_command("sldd Diag writeDid 43A0 00"))
        time.sleep(10)
        self.shell.run(self._wrap_command("sldd Diag writeDid 43A0 01"))
        time.sleep(5)
        # reboot after DTC test cases to ensure clean state for cybersecurity and V2X sections
        self.logger.print_green("\n[DTC]===DTC test Completed ===")
        self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 0"))
        self.logger.print_default("[REBOOT] Reboot initiated, waiting 30 seconds for device reconnection...")
        self.shell.run("reboot")
        time.sleep(30)

    def _run_cybersecurity(self) -> None:
        self.logger.print_green("\n[CYBERSECURITY]=== Running Cybersecurity test ===")
        commands_eu = [
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/invalid_signature_cam.bin",
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/valid_cam.bin",
            "/data/v2xmgr/etc/rio_inject 1 127.0.0.1 /data/v2xmgr/etc/valid_cam.bin",
        ]
        commands_cn = [
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/invalid_signature_cn_bsm.bin",
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/valid_cn_bsm.bin",
            "/data/v2xmgr/etc/rio_inject 4 127.0.0.1 /data/v2xmgr/etc/valid_cn_bsm.bin",
        ]

        # stack is off in DTC section, so no potential risk to change its.json.
        Helper.modify_its_cybersecurity(self.shell, self.files, self.logger)
        is_eu = Helper.is_region_eu(self.files, self.logger)
        if is_eu:
            self.logger.print_green("======= Starting EU Cybersecurity test =======")
            self.helper.activate_stack()
            for cmd in commands_eu:
                self.shell.run(cmd)
                time.sleep(2)
            
            # off the stack before changing region and it.json
            self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 0"))
            time.sleep(15)
            self.shell.run(self._wrap_command("sldd v2xmgr changeregion cn"))
            self.logger.print_green("======= Starting CN Cybersecurity test =======")
            time.sleep(10)
            Helper.modify_its_cybersecurity(self.shell, self.files, self.logger)
            self.helper.activate_stack()

            for cmd in commands_cn:
                self.shell.run(cmd)
                time.sleep(2)
        else:
            self.logger.print_green("======= Starting CN Cybersecurity test =======")
            self.helper.activate_stack()
            for cmd in commands_cn:
                self.shell.run(cmd)
                time.sleep(2)

             # off the stack before changing region and it.json
            self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 0"))
            time.sleep(15)
            self.shell.run(self._wrap_command("sldd v2xmgr changeregion eu"))
            self.logger.print_green("======= Starting EU Cybersecurity test =======")
            # modify its.json as EU region
            time.sleep(10)
            Helper.modify_its_cybersecurity(self.shell, self.files, self.logger)
            
            self.helper.activate_stack()
            for cmd in commands_eu:
                self.shell.run(cmd)
                time.sleep(2)

            self.logger.print_green("\n[CYBERSECURITY]=== Cybersecurity test Completed ===")

    def _run_v2x(self) -> None:
        self.logger.print_green("\n[V2X]=== Running V2X test ===")
        commands = [
            ("sldd power requestset 2004 7", 2),
            ("sldd power requestset 2004 2", 2),
            ("sldd power requestset 2004 5", 2),
            ("pgrep -f its", 2),
            ("ps -fC its", 2),
            ("ps -fC its", 2),
            ("killall its", 20),
            ("sldd power requestset 2002 1", 2),
        ]

        batch = []
        for cmd, delay in commands:
            if cmd.startswith("sldd "):
                batch.append((self._wrap_command(cmd), delay))
            else:
                batch.append((cmd, delay))
        self.shell.run_batch(batch, default_delay=0)
        self.logger.print_green("\n[V2X]=== V2X test Completed ===")

    def setup_custom(self) -> None:
        """Execute the complete basic sanity sequence during setup phase."""
        self._cleanup_logs()

        self._push_prerequisites_once()
        
        # Ensure devcoding_imei has mode detected (for SOP vs Master handling)
        self.devcoding_imei._determine_mode()
        self.devcoding_imei._setup_sop_mode()
        # self.devcoding_imei._setup_cert_prerequisites()
        # self.helper.ask("Hard reboot the device to reflect initial setup")
        Helper.start_dlt_viewer()
        self.helper.activate_stack()
        self._timeline_marker("START_SEQUENCE")

        self._timeline_marker("START_CODING_PROVISIONING")
        self._run_coding_provisioning()
        self._timeline_marker("END_CODING_PROVISIONING")

        self._timeline_marker("START_DIAGNOSTICS")
        self._run_diagnostics()
        self._timeline_marker("END_DIAGNOSTICS")

        # SOP permission will be reset after reboot in Diagnostics section, so we need to set permissions again before DTC test cases.
        if Helper.is_binary_sop(self.config.version_output):
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger)
        self.helper.activate_stack()
        self._timeline_marker("START_DTC")
        self._run_dtc()
        self._timeline_marker("END_DTC")
        # since stack is off after reboot, we need to turn it on again for the remaining sections
        
        # Here after reboot, shell should reconnect automatically.
        # SOP permission will be reset after reboot in Diagnostics section, so we need to set permissions again before DTC test cases.
        if Helper.is_binary_sop(self.config.version_output):
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger)
            Helper.setup_sop_prerequisites(self.shell, self.files, self.logger, path="/data/")

        self._timeline_marker("START_CYBERSECURITY")
        self._run_cybersecurity()
        self._timeline_marker("END_CYBERSECURITY")

        self._timeline_marker("START_V2X")
        self._run_v2x()
        self._timeline_marker("END_V2X")
        
        # Ask user to stop DLT capture - handle the response
        response = Helper.ask("Basic sanity sequence completed. Stop DLT capture now. ")
        if not response:
            self.logger.print_default("User cancelled DLT capture confirmation.")
        
        self._timeline_marker("END_SEQUENCE")
        self.logger.print_default("Set IMEI")
        self.shell.run(self._wrap_command("sldd telephony factorysetimei 354028100010134"))
    def teardown_custom(self) -> None:
        """Perform one final shutdown step after all sections are done."""
        self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 0"))
        self.logger.print_default(f"Timeline written to: {self.timeline_file}")
        self.logger.print_default(f"Timing summary written to: {self.timing_file}")
        
        # Log execution summary
        self._log_execution_summary()
        
        # Find and process DLT file for verification and Excel report generation
        try:
            # Look for most recent DLT file in versioned directory
            dlt_file = self._find_latest_dlt_file()
            
            if dlt_file:
                self.logger.print_default(f"\n[INFO] Found DLT file: {dlt_file}")
                self.logger.print_default(f"[INFO] Verifying test...\n")
                
                # Call verify_dlt_file directly - processes DLT and generates Excel report
                verify_dlt_file(dlt_file)

            else:
                self.logger.print_default("[INFO] No DLT file found. Skipping verification.")
        except Exception as e:
            self.logger.print_red(f"[ERROR] Error during verification: {e}")
    
    def _find_latest_dlt_file(self) -> str:
        """
        Find the most recent DLT file in the versioned directory.
        
        Returns:
            Path to the DLT file or None if not found
        """
        try:
            if not hasattr(self, 'versioned_dir') or not self.versioned_dir:
                self.logger.print_default("[INFO] Versioned directory not available")
                return None
            
            # Search for DLT files in versioned directory
            dlt_files = sorted(self.versioned_dir.glob("*.dlt"), key=os.path.getmtime, reverse=True)
            
            if dlt_files:
                return str(dlt_files[0])
            else:
                self.logger.print_default(f"[INFO] No DLT files found in: {self.versioned_dir}")
                return None
        except Exception as e:
            self.logger.print_red(f"[ERROR] Error finding DLT file: {e}")
            return None


def main():
    """Run basic sanity test sequence."""
    log_file = r"../logs/basic_sanity.log"
    test = BasicSanityTest(test_name="Basic Sanity Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
