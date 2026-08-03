import subprocess
import threading
import queue
import time
import datetime
import sys
import os
import json
import tempfile
import json
import uuid
import re
from collections import OrderedDict
# ------------------------------
# Helper Function
# ------------------------------
class Helper:
    def __init__(self, logger=None):
        self.logger = logger

    @staticmethod
    def ask(prompt):
        """Prompt user with Y/N question and treat ENTER as 'Y'."""
        import sys
        
        # Check if stdin is available and interactive
        if not sys.stdin.isatty():
            # In non-interactive mode (batch/automated), default to True
            print(f"{prompt} [Y/N]: [AUTO-CONFIRMED: Y (non-interactive mode)]")
            return True
        
        while True:
            try:
                answer = input(prompt + " [Y/N]: ").strip().upper()

                # ENTER key or Y → YES
                if answer == "" or answer == "Y":
                    return True
                elif answer == "N":
                    print("Please complete the required step before continuing...")
                    return False
                else:
                    print("Invalid input. Please type Y or N (or press ENTER for Yes).")
            except (EOFError, KeyboardInterrupt):
                # Handle cases where stdin is closed or user interrupts
                print("\nOperation cancelled by user or stdin closed.")
                return False

    @staticmethod
    def start_dlt_viewer(bat_file=r"..\dlt\V2X_NAD_DLT.bat",
                         dlt_viewer_path=r"..\dlt\DltViewerSDK-2.21.3\dlt-viewer.exe",
                         project_file=r"..\dlt\dlt_projectfile\NAD_debug_verbose.dlp"):
        """
        Start prerequisite bat file and DLT Viewer as completely separate processes.
        """
        try:
            # Step 1: Run the prerequisite bat file in separate cmd window
            if os.path.exists(bat_file):
                subprocess.Popen(
                    bat_file,
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                time.sleep(1)
            
            # Step 2: Start DLT Viewer as separate detached process
            if os.path.exists(dlt_viewer_path):
                subprocess.Popen(
                    [dlt_viewer_path, "-p", project_file],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    start_new_session=True if os.name != 'nt' else False
                )
                print(f"✓ DLT Viewer launched as separate process")
        except Exception as e:
            print(f"✗ Error: {str(e)}")

    # Json load helper
    @staticmethod
    def load_first_json_object(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read().lstrip()

        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text)
        return obj
 
    # @staticmethod
    # def is_stack_on(shell, logger=None, max_attempts=5, delay_between=5):
    #     """
    #     Check if the ITS stack is active using 'systemctl is-active its'.
    #     If stack does not turn active after max_attempts, halts the script.
    #     Logs output to both console and file.
        
    #     Args:
    #         shell: ADB shell instance
    #         logger: Optional ADBLogger instance (can be None)
    #         max_attempts: Number of attempts to check stack status
    #         delay_between: Seconds to wait between attempts
    #     """
    #     # Handle backward compatibility: if logger is an int, it's the old signature
    #     if isinstance(logger, int):
    #         delay_between = max_attempts
    #         max_attempts = logger
    #         logger = None
        
    #     for attempt in range(1, max_attempts + 1):
    #         msg_attempt = f"[Stack Check] Attempt {attempt}..."
    #         if logger and hasattr(logger, "print_default"):
    #             logger.print_default(msg_attempt)
    #         else:
    #             print(msg_attempt)
            
    #         output = shell.run("systemctl is-active its", timeout=10).strip()
    #         msg_status = f"Stack status: {output}"
    #         if logger and hasattr(logger, "print_default"):
    #             logger.print_default(msg_status)
    #         else:
    #             print(msg_status)
            
    #         if "active" in output.lower():
    #             msg_on = "[Stack Check] Stack is ON"
    #             if logger and hasattr(logger, "print_green"):
    #                 logger.print_green(msg_on)
    #             else:
    #                 print(msg_on)
    #             return  # Stack ON, continue execution
            
    #         if attempt < max_attempts:
    #             msg_wait = f"Stack still OFF. Waiting {delay_between}s before retry..."
    #             if logger and hasattr(logger, "print_yellow"):
    #                 logger.print_yellow(msg_wait)
    #             else:
    #                 print(msg_wait)
    #             time.sleep(delay_between)

    #     # Stack did not turn ON after retries
    #     msg_error = "[ERROR] Stack not active after maximum attempts. Exiting..."
    #     if logger and hasattr(logger, "print_red"):
    #         logger.print_red(msg_error)
    #     else:
    #         print(msg_error)
    #     sys.exit(1)

    def is_certificate_present(shell, logger, cert_path=None) -> bool:
        """
        Returns True if files are present in either EU or CN certificate directories.
        """
        try:
            # Check both directories at once
            cmd = "ls -A /etc/certs/security_eu; ls -A /etc/certs/security_cn"
            output = shell.run(cmd).strip()

            logger.info(f"Certificate check output:\n{output}")

            # If output is empty → both dirs are empty
            if not output:
                return False

            # If any file exists in either directory
            return True

        except Exception as e:
            logger.error(f"Exception in certificate check: {str(e)}")
            return False
        
    @staticmethod
    def is_stack_on(shell, logger=None, min_lines=5, max_attempts=5, delay_between=8):
        """
        Automatically check if the stack is ON using 'unplugged-rt-status-gen'.
        Accepts either ``is_stack_on(shell, logger)`` or the older
        ``is_stack_on(shell, min_lines, max_attempts, delay_between)`` form.
        """
        if isinstance(logger, int):
            delay_between = max_attempts
            max_attempts = min_lines
            min_lines = logger
            logger = None

        log = logger.log if hasattr(logger, "log") else print
        log_error = logger.log_error if hasattr(logger, "log_error") else print

        for attempt in range(1, max_attempts + 1):
            log(f"[Stack Check] Attempt {attempt}...")
            output = shell.run("unplugged-rt-status-gen", timeout=10)
            line_count = len(output.strip().splitlines())
            log(f"Lines in output: {line_count}")
            if line_count > min_lines:
                log("[Stack Check] Stack is ON")
                return
            if attempt < max_attempts:
                log(f"Stack still OFF. Waiting {delay_between}s before retry...")
                time.sleep(delay_between)

        log_error("[Stack Check] Stack not ON after maximum attempts. Exiting...")
        sys.exit(1)

    def activate_stack(self) -> None:
        """Enable privacy and stack only once for the full sequence."""
        self.shell.run(self._wrap_command("sldd v2xmgr setdataprivacy 1"))
        time.sleep(8)

        if Helper.is_icon_sf25(self.config.version_output):
            self.shell.run("systemctl start its")
            time.sleep(2)
        # self.shell.run("systemctl start its") # ICON25

        Helper.is_stack_on(self.shell, self.logger)
    @staticmethod
    def is_icon_sf25(version_output: str) -> bool:
        """Return True if 'iconsf25' is found in the version output."""
        if version_output is None:
            return False
        return "iconsf25" in version_output.lower()  # lowercase to make it case-insensitive
    
    @staticmethod
    def is_binary_sop(version_output: str) -> bool:
        """Return True if 'sop' is found in the version output."""
        if version_output is None:
            return False
        return "sop" in version_output.lower()  # lowercase to make it case-insensitive

    @staticmethod
    def is_region_eu(files, logger, remote_path="/etc/its.json", local_dir=r"D:\Help\automation"):
        """
        Pulls its.json from device and determines EU / CN region.
        Returns:
            True  -> EU
            False -> CN
            None  -> Unknown
        """

        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, "its.json")

        logger.log(f"[INFO] Pulling {remote_path} → {local_path}")
        files.pull(remote_path, local_path)

        if not os.path.exists(local_path):
            logger.log_error("its.json not found after pull")
            return None

        data = load_json_with_fallback(local_path, logger, use_ordered_dict=False)

        if data is None:
            return None

        directories = data.get("security", {}).get("directories", {})

        if "eu" in directories:
            logger.log("Region detected: EU")
            return True

        if "cn" in directories:
            logger.log("Region detected: CN")
            return False

        logger.log_error("Region not found in its.json")
        return None

    def modify_its_cybersecurity(shell, file, logger, remote_path="/etc/its.json"):
        """
        Pulls its.json from the remote device, modifies it locally, and pushes it back.
        """

        # --- 1. Backup existing JSON file on target ---
        local_dir = r"D:\Help\automation"
        backup_path = remote_path + ".bak"
        logger.log(f"[INFO] Creating backup on device: {backup_path}")
        shell.run(f"cp {remote_path} {backup_path}")

        # --- 2. Pull file to local machine ---
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, "its.json")

        logger.log(f"[INFO] Pulling {remote_path} → {local_path}")
        file.pull(remote_path, local_path)

        if not os.path.exists(local_path):
            logger.log(f"❌ Pull failed — file not found at {local_path}")
            return

        # --- 3. Load JSON preserving order ---
        data = load_json_with_fallback(local_path, logger, use_ordered_dict=True)
        if data is None:
            return

        # --- 4. Modify 'security' section ---
        if "security" in data:
            sec = data["security"]
            sec["enable"] = "Yes"
            sec["checkCrl"] = "Permissive"
            sec["checkLoadedCertificates"] = False

            # Region-based directories
            if "directories" in sec:
                dirs = sec["directories"]
                if "eu" in dirs:
                    dirs["eu"] = "/data/v2xmgr/etc/MBD"
                else:
                    sec["directories"] = {
                        "cn": "/data/v2xmgr/etc/test_certs/security_cn"
                    }

            # Insert checkTimestamp after checkLoadedCertificates
            new_sec = OrderedDict()
            for key, value in sec.items():
                new_sec[key] = value
                if key == "checkLoadedCertificates":
                    new_sec["checkTimestamp"] = False
            data["security"] = new_sec

        # --- 5. Insert 'logging' after 'security' ---
        new_data = OrderedDict()
        for key, value in data.items():
            new_data[key] = value
            if key == "security":
                new_data["logging"] = OrderedDict([
                    ("logLevel", "Debug"),
                    ("debugComponents", ["SEC"])
                ])

        # --- 6. Modify 'hsm' ---
        if "hsm" in new_data:
            new_data["hsm"] = {"type": "Emulated"}

        # --- 7. Disable geofencing ---
        if "geofencing" in new_data:
            new_data["geofencing"]["enable"] = False

        # --- 8. Write modified JSON back ---
        json_str = json.dumps(new_data, indent=2, separators=(",", ": "))
        json_str = re.sub(r'\[\s*"SEC"\s*\]', '["SEC"]', json_str)

        with open(local_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        logger.log(f"[INFO] Local file modified successfully → {local_path}")

        # --- 9. Push file back to remote device ---
        file.push(local_path, remote_path, force=True)
        logger.log(f"[OK] Modified its.json pushed → {remote_path}")
        logger.log(f"[INFO] Backup retained at {backup_path}")


    def modify_cff_mapmatching(shell, file, logger, remote_path="/etc/cff.json"):
        """
        Pulls its.json, adds a logging section, and pushes it back.
        """
        local_dir = r"D:\Help\automation"
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, "its_logging.json")
        backup_path = remote_path + ".bak"

        # 1. Backup and Pull
        logger.log(f"[INFO] Creating backup: {backup_path}")
        shell.run(f"cp {remote_path} {backup_path}")
        
        logger.log(f"[INFO] Pulling {remote_path} → {local_path}")
        file.pull(remote_path, local_path)

        if not os.path.exists(local_path):
            logger.log(f"❌ Pull failed — file not found at {local_path}")
            return

        # 2. Load JSON safely
        data = load_json_with_fallback(local_path, logger, use_ordered_dict=True)
        if data is None:
            return

        # Check path existence to prevent KeyErrors
        if "mapMatching" in data and "common" in data["mapMatching"]:
            data["mapMatching"]["common"]["enable"] = True
            logger.log("[INFO] Set mapMatching.common.enable to False")
        else:
            logger.log("[WARN] Required keys 'mapMatching' -> 'common' not found in file")

        data["logging"] = {
            "logLevel": "Debug",
            "loggers": [
                {"logger": "M-BSI", "logLevel": "Debug"},
                {"logger": "F-FOR", "logLevel": "Debug"}
            ]
        }

        # 3. Write and Push
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.log(f"[INFO] Local modification complete. Pushing back...")
        file.push(local_path, remote_path, force=True)
        logger.log(f"[OK] Logging section added and pushed to {remote_path}")


    def disable_map_matching_for_geofencing_in_cff(shell, file, logger, remote_path="/etc/cff.json"):
        """
        Pulls cff.json, disables mapMatching.common.enable, and pushes it back.
        Handles malformed JSON with trailing extra data safely.
        """

        local_dir = r"D:\Help\automation"
        os.makedirs(local_dir, exist_ok=True)

        local_path = os.path.join(local_dir, "its_disable_map.json")
        backup_path = remote_path + ".bak"

        # 1. Backup and Pull
        logger.log(f"[INFO] Creating backup: {backup_path}")
        shell.run(f"cp {remote_path} {backup_path}")

        logger.log(f"[INFO] Pulling {remote_path} → {local_path}")
        file.pull(remote_path, local_path)

        if not os.path.exists(local_path):
            logger.log(f"❌ Pull failed — file not found at {local_path}")
            return

        # 2. Load JSON safely
        data = load_json_with_fallback(local_path, logger, use_ordered_dict=True)
        if data is None:
            return

        # 3. Modify: Disable Map Matching
        if "mapMatching" in data and "common" in data["mapMatching"]:
            data["mapMatching"]["common"]["enable"] = False
            logger.log("[INFO] Set mapMatching.common.enable to False")
        else:
            logger.log("[WARN] Required keys 'mapMatching -> common' not found in file")

        # 4. Write and Push
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.log("[INFO] Local modification complete. Pushing back...")
        file.push(local_path, remote_path, force=True)

        logger.log(f"[OK] MapMatching disabled and pushed to {remote_path}")

    # def modify_its_geofencing(shell, file, logger, remote_path="/etc/its.json"):
    #     """
    #     Pulls its.json from the remote device, modifies it locally, and pushes it back.
    #     """
    #     # --- 1. Backup existing JSON file on target ---
    #     local_dir = r"D:\Help\automation"
    #     backup_path = "/etc/its.json" + ".bak"
    #     logger.log(f"[INFO] Creating backup on device: {backup_path}")
    #     shell.run(f"cp {remote_path} {backup_path}")

    #     # --- 2. Pull file to local machine ---
        
    #     os.makedirs(local_dir, exist_ok=True)
    #     local_path = os.path.join(local_dir, "its.json")

    #     logger.log(f"[INFO] Pulling {remote_path} → {local_path}")
    #     file.pull(remote_path, local_path)

    #     if not os.path.exists(local_path):
    #         logger.log(f"❌ Pull failed — file not found at {local_path}")
    #         return

    #     # --- 3. Load JSON preserving order ---
    #     data = load_json_with_fallback(local_path, logger, use_ordered_dict=True)
    #     if data is None:
    #         logger.log(f"❌ Failed to parse JSON from {local_path}")
    #         return

    #     # --- 4. Modify 'security' section ---
    #     if "security" in data:
    #         sec = data["security"]
    #         sec["enable"] = "Yes"
    #         sec["checkCrl"] = "Permissive"
    #         sec["checkLoadedCertificates"] = False

    #         # Region-based directories
    #         if "directories" in sec:
    #             dirs = sec["directories"]
    #             if "eu" in dirs:
    #                 dirs["eu"] = "/data/v2xmgr/etc/test_certs/security_eu"
    #             else:
    #                 sec["directories"] = {
    #                     "cn": "/data/v2xmgr/etc/test_certs/security_cn"
    #                 }

    #         # Insert checkTimestamp after checkLoadedCertificates
    #         new_sec = OrderedDict()
    #         for key, value in sec.items():
    #             new_sec[key] = value
    #             if key == "checkLoadedCertificates":
    #                 new_sec["checkTimestamp"] = False
    #         data["security"] = new_sec

    #     # --- 5. Insert 'logging' after 'security' ---
    #     new_data = OrderedDict()
    #     for key, value in data.items():
    #         new_data[key] = value
    #         if key == "security":
    #             new_data["logging"] = OrderedDict([
    #                 ("logLevel", "Debug"),
    #                 ("debugComponents", ["GF"])
    #             ])

    #     # --- 6. Modify 'hsm' ---
    #     if "hsm" in new_data:
    #         new_data["hsm"] = {"type": "Emulated"}

    #     # --- 7. Disable geofencing ---
    #     if "geofencing" in new_data:
    #         new_data["geofencing"]["enable"] = True

    #     # --- 8. Write modified JSON back ---
    #     json_str = json.dumps(new_data, indent=2, separators=(",", ": "))
    #     json_str = re.sub(r'\[\s*"SEC"\s*\]', '["GF"]', json_str)

    #     with open(local_path, "w", encoding="utf-8") as f:
    #         f.write(json_str)

    #     logger.log(f"[INFO] Local file modified successfully → {local_path}")

    #     # --- 9. Push file back to remote device ---
    #     file.push(local_path, remote_path, force=True)
    #     logger.log(f"[OK] Modified its.json pushed → {remote_path}")
    #     logger.log(f"[INFO] Backup retained at {backup_path}")

    def modify_its_geofencing(
        self,
        remote_path="/etc/its.json",
        work_dir=None,
        local_backup_path=None):

        # ----------------------------------
        # 0) Prepare working paths
        # ----------------------------------
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)

        if work_dir is None:
            work_dir = os.path.join(parent_dir, "build", "its_json_workdir")

        if local_backup_path is None:
            local_backup_path = os.path.join(
                parent_dir,
                "build",
                "backup",
                "its.json.bak"
            )

        os.makedirs(work_dir, exist_ok=True)

        local_path = os.path.join(work_dir, "its.json")

        # Ensure backup directory exists
        backup_dir = os.path.dirname(local_backup_path)
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)

        # ----------------------------------
        # 1) Pull file to local
        # ----------------------------------
        self.logger.log(f"[its.json] Pulling {remote_path} → {local_path}")

        try:
            self.files.pull(remote_path, local_path)
        except Exception as e:
            self.logger.log_error(f"[its.json] Pull operation failed: {e}")
            return

        if not os.path.exists(local_path):
            self.logger.log_error(f"[its.json] Pull failed — file not found at {local_path}")
            return

        # ----------------------------------
        # 2) Local backup
        # ----------------------------------
        try:
            with open(local_path, "rb") as src, open(local_backup_path, "wb") as dst:
                dst.write(src.read())

            self.logger.log(f"[its.json] Local backup created → {local_backup_path}")

        except Exception as e:
            self.logger.log(
                f"[its.json] Failed to create local backup: {e}. "
                f"Proceeding without backup."
            )

        # ----------------------------------
        # 3) Load JSON
        # ----------------------------------
        data = load_json_with_fallback(
            local_path,
            self.logger,
            use_ordered_dict=True
        )

        if data is None:
            self.logger.log("❌ JSON load failed")
            return

        cert_present = self.is_certificate_present(self.shell, self.logger)
        region_is_eu = False

        # ----------------------------------
        # Pseudonimity
        # ----------------------------------
        if "pseudonimity" in data:
            data["pseudonimity"]["enable"] = "Yes"

        # ----------------------------------
        # Security
        # ----------------------------------
        if "security" in data:
            sec = data["security"]

            sec["enable"] = "Yes"
            sec["checkCrl"] = "Permissive"
            if cert_present:
                sec["checkLoadedCertificates"] = True
            else:
                sec["checkLoadedCertificates"] = False

            if "directories" in sec:
                dirs = sec["directories"]

                if "eu" in dirs:
                    region_is_eu = True

                    if cert_present:
                        dirs["eu"] = "/etc/certs/security_eu"
                    else:
                        dirs["eu"] = "/data/v2xmgr/etc/test_certs/security_eu"

                else:
                    print(f"Certificate present status:{cert_present}")
                    if cert_present:
                        sec["directories"] = {
                            "cn": "/etc/certs/security_cn"
                        }
                    else:
                        sec["directories"] = {
                            "cn": "/data/v2xmgr/etc/test_certs/security_cn"
                        }

        # ----------------------------------
        # HSM
        # ----------------------------------
        if cert_present:

            if region_is_eu:
                data["hsm"] = {
                    "type": "Hardware",
                    "hwType": "atEhsm",
                    "atEhsm": {
                        "blobFile": "/data/v2xmgr/etc/hsm-blob.dat"
                    }
                }
            else:
                data["hsm"] = {
                    "type": "Hardware",
                    "hwType": "ttMizaru"
                }

        else:

            if region_is_eu:
                data["hsm"]["type"] = "Emulated"
            else:
                if "hsm" in data:
                    data["hsm"]["type"] = "Emulated"

        # ----------------------------------
        # Logging
        # ----------------------------------
        new_data = OrderedDict()

        for key, value in data.items():
            new_data[key] = value

            if key == "security":
                new_data["logging"] = OrderedDict([
                    ("logLevel", "Debug"),
                    ("debugComponents", ["GF"])
                ])

        # ----------------------------------
        # Geofencing
        # ----------------------------------
        if "geofencing" in new_data:
            new_data["geofencing"]["enable"] = True

        # ----------------------------------
        # Save locally
        # ----------------------------------
        json_str = json.dumps(new_data, indent=2)
        json_str = re.sub(r'\[\s*"SEC"\s*\]', '["GF"]', json_str)

        with open(local_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        # ----------------------------------
        # Push back to target
        # ----------------------------------
        self.files.push(local_path, remote_path, force=True)

        self.logger.log("[INFO] its.json updated successfully")
  

    @staticmethod
    def setup_sop_prerequisites(shell, files, logger, path = "/log/"):
        """
        Set up SOP mode prerequisites:
        1. Push sldd binaries to /log/ (if paths provided)
        2. Remount /log/ with exec permissions
        3. Set execute permissions on sldd binaries
        """
        logger.log("[SOP Setup] Starting prerequisites...")

        cmd = "ls -A /log/"
        output = shell.run(cmd).strip()

        # Check if both files are present
        if "sldd" not in output or "sldd_v2xmgr" not in output:

            sldd_dir = input("Enter sldd path: ").strip()
            sldd_path = f"{sldd_dir}\\sldd"
            sldd_v2xmgr_path = f"{sldd_dir}\\sldd_v2xmgr"
            logger.log("[SOP Setup] Pushing sldd and sldd_v2xmgr → /log/")
            files.push(sldd_path, "/log/")
            files.push(sldd_v2xmgr_path, "/log/")
            # Set execute permissions
            time.sleep(1)
            logger.log("[SOP Setup] Setting permissions (chmod 777)...")
            shell.run("chmod 777 /log/sldd /log/sldd_v2xmgr", timeout=10)
        else:
            logger.log("[SOP Setup] sldd and sldd_v2xmgr already present in /log/, skipping push.")
                
        # Remount /log/ with exec permission
        logger.log(f"[SOP Setup] Remounting {path} with exec permission...")
        shell.run(f"mount -o remount,exec {path}", timeout=10)
        
        logger.log("[SOP Setup] Prerequisites complete!")


    def sop_mount_remount(shell, logger, path="/log/"):
        """
        Perform SOP-specific mount and remount operations:
        - Remount /log/sldd with exec permissions
        """
        shell.run(f"mount -o remount,exec {path}", timeout=10)
        logger.log("[SOP Mount] Done Mount remount permission...")
