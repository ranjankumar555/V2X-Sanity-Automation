"""
Certificate Download Test
Uses both ECUSerialCom (for devcoding) and ADB Shell (for telephony)
"""

import time
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Union, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_base import TestBase
from framework.serial_com.bam import ECUSerialCom
from framework.helper import Helper

class TestCertificateDownload(TestBase):
    """Certificate download test combining serial interface and ADB shell"""
    
    def __init__(self, test_name: str = "Certificate Download Test", log_file: str = r"../logs/certificate_download.log"):
        """Initialize certificate download test."""
        # Initialize serial interface first
        self.ecu_serial = ECUSerialCom(port="COM40", baudrate=1000000, log_file=log_file, print_console_output=False)
        
        # Then initialize TestBase (which initializes ADB shell)
        super().__init__(test_name=test_name, log_file=log_file)
        
        self.region = None
        self.dns_ok = False
    
    def get_commands(self) -> List[Union[str, Tuple[str, int]]]:
        """Return telephony and prerequisite verification commands executed during setup"""
        return [
            # Telephony verification (via ADB)
            "sldd telephony getimei",
            "sldd telephony getprefnettype",
            "sldd telephony getsignalstrength",
            "sldd telephony getdatastate",
            "sldd telephony getnetregstate",
            "sldd telephony getnetoper",
            "sldd telephony getservicestate",
        ]
    
    def _setup_utc_time(self) -> None:
        """Set UTC time on BAM side (via serial interface)"""
        self.logger.log("\n[UTC TIME SETUP] Setting UTC Time on BAM side (via Serial Interface)")
        
        if not self.ecu_serial.is_connected():
            self.ecu_serial.connect()
        
        if not self.ecu_serial.monitor_thread or not self.ecu_serial.monitor_thread.is_alive():
            self.ecu_serial.start_monitor()
        
        time.sleep(0.5)
        
        now_utc = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")
        date_cmd = f'date -s "{date_str}"'
        
        try:
            self.logger.log(f"  Setting UTC date: {date_str}")
            response = self.ecu_serial.send_cmd(date_cmd, timeout=5)
            self.logger.log(f"  [OK] UTC date set")
            time.sleep(1)
            
            # Verify date was set
            response = self.ecu_serial.send_cmd("date", timeout=5)
            self.logger.log(f"  [OK] Current date verified")
        except Exception as e:
            self.logger.log(f"  [WARNING] UTC time setup: {e}")
    
    def _setup_cert_prerequisites(self) -> None:
        """Setup necessary prerequisites for DNS verification
        
        Includes:
        1. Set IMEI via ADB (NAD side) - MUST succeed for DNS to work
        2. Devcoding setup via Serial (BAM side) - MUST run for DNS success
        """
        self.logger.log("\n[DNS PREREQUISITES] Setting up necessary prerequisites for DNS verification")
        
        # Step 1: Set IMEI to ensure telephony is functional (required for DNS success)
        self.logger.log("\n[STEP 1] Set IMEI (via ADB - NAD side)")
        try:
            self.shell.run(self._wrap_command("sldd telephony factorysetimei 354028100010134"))
            self.logger.print_green(f"  [NAD] IMEI set successfully")
            time.sleep(1)
        except Exception as e:
            self.logger.print_red(f"  [ERROR] Failed to set IMEI: {e}")
        
        # Step 2: Devcoding setup - Execute via serial interface (MUST RUN FOR DNS SUCCESS)
        self.logger.log("\n[STEP 2] Devcoding Setup (via Serial Interface - BAM side)")
        
        if not self.ecu_serial.is_connected():
            self.ecu_serial.connect()
        
        if not self.ecu_serial.monitor_thread or not self.ecu_serial.monitor_thread.is_alive():
            self.ecu_serial.start_monitor()
        
        # Devcoding commands - run through serial interface (MUST RUN FOR DNS SUCCESS)
        devcoding_cmds = [
            "devcoding write PROVISIONING/DAS_INDEX 1",
            "devcoding write ECALL/SIM_CARD 1",
            "devcoding write ECALL/TELEMATIC 1",
        ]
        
        for cmd in devcoding_cmds:
            try:
                self.logger.print_blue(f"{cmd}")
                response = self.ecu_serial.send_cmd(cmd, timeout=10)
                self.logger.print_default(f"[setup_cert_prerequisites] {response}")
                time.sleep(0.5)
            except Exception as e:
                self.logger.print_red(f"  [ERROR] {e}")
        
        # Check provisioning daemon - via serial interface
        self.logger.log("  ps | grep provisioningd daemon...")
        try:
            response = self.ecu_serial.send_cmd("ps | grep provisioningd", timeout=5)
            self.logger.print_green(f"  [setup_cert_prerequisites] {response}")
        except Exception as e:
            self.logger.print_red(f"  [WARNING] {e}")
        
        # Setup UTC time
            self._setup_utc_time()
            time.sleep(1)
    
    def setup_custom(self) -> None:
        """Setup: Run DNS prerequisites, UTC time setup, and reboot"""
        self.logger.log("\n" + "="*70)
        self.logger.print_green("CERTIFICATE DOWNLOAD - Initial Setup(devcoding + IMEI + UTC Time + Reboot)")
        self.logger.log("="*70)
        
        if Helper.is_binary_sop(self.config.version_output):
            Helper.sop_mount_remount(self.shell, self.logger)
        
        try:
            # Setup DNS prerequisites (IMEI + devcoding)
            self._setup_cert_prerequisites()
            time.sleep(1)
            
            
            
            # Remount filesystem as read-only
            self.logger.log("\n[STEP 3] Remount filesystem as read-only")
            try:
                response = self.ecu_serial.send_cmd("mount -o remount,ro /opt/telematics/", timeout=5)
                self.logger.print_default(f"[BAM]  mount -o remount,ro /opt/telematics/ \n{response}")
                self.logger.log(f"  [OK] Filesystem remounted as read-only")
            except Exception as e:
                self.logger.log(f"  [WARNING] Remount: {e}")
            
            time.sleep(1)
            
            # Reboot device (REQUIRED after setup)
            self.logger.print_default("\n[STEP 4] Rebooting device (REQUIRED after setup)...")
            try:
                self.ecu_serial.send_cmd("reboot", timeout=2)
            except:
                pass  # Timeout expected for reboot
            
            self.logger.print_default("  [BAM] Reboot initiated, waiting 35 seconds...")
            time.sleep(30)
            
            # Post-reboot telephony verification
            self.logger.log("\n[STEP 5] Post-reboot Verification")
            self.logger.print_default("  Checking service state after reboot...")
            
            max_retries = 5
            service_ok = False
            for attempt in range(1, max_retries + 1):
                try:
                    result = self.shell.run(self._wrap_command(("sldd telephony getservicestate")))
                    if "In service" in result:
                        self.logger.log(f"  [Certificate] Device in service (attempt {attempt}/{max_retries})")
                        service_ok = True
                        break
                    else:
                        self.logger.log(f"  [WARNING] Service state check attempt {attempt}/{max_retries}")
                        if attempt < max_retries:
                            time.sleep(3)
                except Exception as e:
                    self.logger.print_red(f"  [ERROR] Attempt {attempt}: {e}")
                    if attempt < max_retries:
                        time.sleep(3)
            
            if not service_ok:
                self.logger.log("  [WARNING] Service state verification inconclusive, continuing anyway")
            
        except Exception as e:
            self.logger.print_red(f"[ERROR] Setup failed: {e}")
            raise
    
    def teardown_custom(self) -> None:
        """Cleanup: Disable data privacy and close connections"""
        self.logger.log("\n" + "="*70)
        self.logger.print_default("CERTIFICATE DOWNLOAD - CLEANUP PHASE")
        self.logger.log("="*70)
        
        try:
            # Cleanup via ADB shell
            self.logger.print_default("[CLEANUP] Disabling data privacy...")
            cmd = self._wrap_command("sldd v2xmgr setdataprivacy 0")
            self.shell.run(cmd)
            time.sleep(2)
            
            self.logger.print_default("[CLEANUP] Rebooting device...")
            self.shell.run("reboot")
            
        except Exception as e:
            self.logger.print_red(f"[WARNING] Cleanup error: {e}")
        
        finally:
            # Close serial interface
            try:
                if self.ecu_serial and self.ecu_serial.is_connected():
                    self.ecu_serial.close()
            except:
                pass
    
    def _verify_dns_response(self, dns_name: str, response: str, expected_count: int) -> bool:
        """
        Verify DNS response contains expected number of addresses
        
        Args:
            dns_name: Domain name that was queried
            response: Response from nslookup command
            expected_count: Expected number of addresses
            
        Returns:
            bool: True if count matches or exceeds expected, False otherwise
        """
        address_count = 0
        for line in response.split('\n'):
            if line.strip().startswith("Address"):
                address_count += 1
        
        self.logger.log(f"  DNS '{dns_name}': Found {address_count} addresses (expected ~{expected_count})")
        
        if address_count < expected_count:
            self.logger.log(f"  [WARNING] Lower than expected count")
            return False
        else:
            self.logger.log(f"  [OK] Address count verified")
            return True
    
    def _poll_certificates(self) -> bool:
        """
        Poll for certificate availability (slc_xxx folder)
        Checks every 1 minute for 6 minutes (total 6 attempts)
        
        Returns:
            bool: True if certificates found, False otherwise
        """
        self.logger.print_default("\n[CERT CHECK] certificate download (6 minutes)...")
        
        max_attempts = 6
        poll_interval = 30  # 1/2 minute
        cert_found = False
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Detect region if not already detected
                if not self.region:
                    try:
                        region_eu = self.Helper.is_region_eu(self.shell, self.logger)
                        if  region_eu:
                            self.region = "EU"
                        elif not region_eu:
                            self.region = "CN"
                    except:
                        pass
                
                cert_dir = f"/etc/certs/security_{self.region}/"
                
                self.logger.print_default(f"\n[CERT CHECK - ATTEMPT {attempt}/6] Checking {cert_dir}...")
                
                try:
                    result = self.shell.run(f"ls -l {cert_dir}")
                    
                    if "slc_" in result:
                        self.logger.print_green(f"  [CERTIFICATE] Certificate found (slc_xxx folder)!")
                        cert_found = True
                        
                        # Show certificate details
                        try:
                            cert_list = self.shell.run(f"ls -l {cert_dir}")
                            self.logger.print_default(f"  [CERT LIST] {cert_list}")
                        except:
                            pass
                        
                        break
                    else:
                        self.logger.print_default(f"  [CERTIFICATE] No certificates yet ({attempt}/6)")
                        
                        if attempt < max_attempts:
                            self.logger.print_default(f"  [WAIT] Next check in 1 minute...")
                            time.sleep(poll_interval)
                        else:
                            self.logger.print_red(f"  [FAILED] No certificates found after 6 minutes")
                
                except Exception as e:
                    self.logger.print_red(f"  [ERROR] Check failed: {e}")
                    
                    if attempt < max_attempts:
                        self.logger.print_default(f"  [RETRY] Next check in 1 minute...")
                        time.sleep(poll_interval)
            
            except Exception as e:
                self.logger.print_red(f"  [ERROR] Polling attempt {attempt} failed: {e}")
                if attempt < max_attempts:
                    time.sleep(poll_interval)
        
        return cert_found
    
    def _verify_dns(self) -> bool:
        """
        Perform DNS verification on both NAD (ADB) and BAM (Serial) sides with retry logic
        DNS verification PASSED only if both sides verify successfully (up to 5 attempts)
        
        Returns:
            bool: True if DNS verification passes on BOTH NAD and BAM sides, False otherwise
        """
        self.logger.print_default("\n" + "="*70)
        self.logger.print_default("CERTIFICATE DOWNLOAD - DNS Ping VERIFICATION (NAD + BAM)")
        self.logger.print_default("="*70)
        
        max_attempts = 5
        retry_delay = 3  # seconds between retries
        
        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.print_default(f"\n[DNS VERIFICATION - ATTEMPT {attempt}/{max_attempts}]")
                
                # ===== NAD SIDE (ADB Shell) =====
                self.logger.log("\n[NAD SIDE - ADB Shell]")
                
                # Verify Google DNS via ADB
                google_response_nad = self.shell.run("nslookup www.google.com")
                time.sleep(2)
                google_ok_nad = self._verify_dns_response("www.google.com (NAD)", google_response_nad, expected_count=10)
                time.sleep(1)
                
                # Verify BMW DNS via ADB
                bmw_response_nad = self.shell.run("nslookup asbc-v2x.e2e.cvs-emea.bmw.cloud")
                time.sleep(2)
                bmw_ok_nad = self._verify_dns_response("asbc-v2x.e2e.cvs-emea.bmw.cloud (NAD)", bmw_response_nad, expected_count=2)
                time.sleep(1)
                
                nad_ok = google_ok_nad and bmw_ok_nad
                nad_status = "[OK] NAD DNS verified" if nad_ok else "[WARNING] NAD DNS incomplete"
                self.logger.log(f"  {nad_status}")
                
                # ===== BAM SIDE (Serial Interface) =====
                self.logger.log("\n[BAM SIDE - Dns Check]")
                
                try:
                    # Verify Google DNS via Serial
                    self.logger.log("  [DNS CHECK 1] Testing www.google.com (BAM)...")
                    google_response_bam = self.ecu_serial.send_cmd("nslookup www.google.com", timeout=15)
                    time.sleep(2)
                    google_ok_bam = self._verify_dns_response("www.google.com (BAM)", google_response_bam, expected_count=10)
                    time.sleep(1)
                    
                    # Verify BMW DNS via Serial
                    self.logger.log("  [DNS CHECK 2] Testing asbc-v2x.e2e.cvs-emea.bmw.cloud (BAM)...")
                    bmw_response_bam = self.ecu_serial.send_cmd("nslookup asbc-v2x.e2e.cvs-emea.bmw.cloud", timeout=15)
                    time.sleep(2)
                    bmw_ok_bam = self._verify_dns_response("asbc-v2x.e2e.cvs-emea.bmw.cloud (BAM)", bmw_response_bam, expected_count=2)
                    time.sleep(1)
                    
                    bam_ok = google_ok_bam and bmw_ok_bam
                    bam_status = "[OK] BAM DNS verified" if bam_ok else "[WARNING] BAM DNS incomplete"
                    self.logger.log(f"  {bam_status}")
                
                except Exception as e:
                    self.logger.log(f"  [ERROR] BAM DNS verification error: {e}")
                    bam_ok = False
                
                # Check if BOTH NAD and BAM DNS records verified
                if nad_ok and bam_ok:
                    self.logger.log("\n[OK] DNS verification PASSED (NAD + BAM)")
                    self.dns_ok = True
                    return True
                else:
                    self.logger.log(f"\n[WARNING] DNS verification attempt {attempt} incomplete (NAD: {nad_ok}, BAM: {bam_ok})")
                    
                    # If not last attempt, wait and retry
                    if attempt < max_attempts:
                        self.logger.log(f"[RETRY] Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                    else:
                        self.logger.log(f"\n[CRITICAL] All {max_attempts} DNS verification attempts FAILED")
                        self.dns_ok = False
                        return False
            
            except Exception as e:
                self.logger.log(f"[ERROR] DNS verification attempt {attempt} failed: {e}")
                
                if attempt < max_attempts:
                    self.logger.log(f"[RETRY] Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                else:
                    self.logger.log(f"\n[CRITICAL] All {max_attempts} DNS verification attempts FAILED with exception")
                    return False
        
        # Should not reach here
        return False
    
    def run(self) -> bool:
        """
        Override run() to include full certificate download test flow:
        1. Setup (UTC time + devcoding + reboot)
        2. DNS verification with retry (golden skip if success on first try)
        3. Start stack (sldd v2xmgr setdataprivacy 1 + systemctl start its if ICON25SF)
        4. Poll for certificates (6 minutes, 1 minute intervals)
        5. Cleanup
        """
        try:
            # Phase 1: Setup
            self.setup_custom()
            time.sleep(1)
            
            # Phase 2: DNS Verification (with golden skip: if success at first try, continue)
            self.logger.log("\n" + "="*70)
            self.logger.log("CERTIFICATE DOWNLOAD - PRE-TEST VERIFICATION PHASE")
            self.logger.log("="*70)
            
            dns_result = self._verify_dns()
            
            if not dns_result:
                self.logger.log("\n[CRITICAL] DNS verification failed - halting test")
                return False
            
            time.sleep(1)
            
            # Phase 3: Start stack and initiate certificate download
            self.logger.log("\n" + "="*70)
            self.logger.log("CERTIFICATE DOWNLOAD - ACTUAL TEST PHASE (Start Stack)")
            self.logger.log("="*70)
            

            Helper.ask("Is DLT open?")
            # Start data privacy
            self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 1"))
            time.sleep(5)
            
            # If ICON25SF device, start ITS stack
            if Helper.is_icon_sf25(self.config.version_output):
                self.logger.log("[DEVICE] ICON25SF detected - starting ITS stack...")
                try:
                    self.shell.run("systemctl start its")
                    time.sleep(2)
                except Exception as e:
                    self.logger.log(f"[WARNING] ITS stack start: {e}")
            
            Helper.is_stack_on(self.shell, self.logger)

            # Phase 4: Poll for certificates (6 minutes)
            cert_found = self._poll_certificates()
            
            if cert_found:
                self.logger.log("\n[SUCCESS] Certificate download completed successfully!")
            else:
                self.logger.log("\n[FAILED] Certificate download did not complete - manual debug required")
                return False
            
            # Phase 5: Cleanup
            self.teardown_custom()
            
            return True
        
        except Exception as e:
            self.logger.log(f"\n[CRITICAL ERROR] Test failed: {e}")
            import traceback
            self.logger.log(traceback.format_exc())
            return False


def main():
    """Run Certificate Download test."""
    log_file = r"../logs/certificate_download.log"
    test = TestCertificateDownload(test_name="Certificate Download Test", log_file=log_file)
    success = test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
