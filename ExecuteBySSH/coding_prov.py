# coding_provisioning.py

import os
import platform
import paramiko
from datetime import datetime

# -------------------------------------------------
# Provisioning files
# -------------------------------------------------
prov_CN = r"D:\Cybersecurity\Snake Oil CN\CN_Prov_File\prov.xml"
prov_EU = r"D:\Cybersecurity\Snake Oil EU\EU_Prov_File\prov.xml"

# -------------------------------------------------
# Print current date (portable)
# -------------------------------------------------
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# -------------------------------------------------
# SSH connection settings (hard-coded as requested)
# -------------------------------------------------
HOST = "160.48.249.97"     # media_converter
# HOST = "169.254.1.97"   # TestBench
USER = "root"
KEY_FILE = r"C:\Users\ranjan08.kumar\.ssh\nad_root_key_new"
ACCEPT_HOST_KEY = True


class SSHSession:
    """Persistent SSH + SFTP session"""

    def __init__(self):
        self.client = None
        self.sftp = None

    def connect(self):
        if self.client:
            return

        self.client = paramiko.SSHClient()
        if ACCEPT_HOST_KEY:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            self.client.load_system_host_keys()

        self.client.connect(
            hostname=HOST,
            username=USER,
            key_filename=KEY_FILE,
            look_for_keys=False,
            allow_agent=False,
            timeout=30,
            banner_timeout=200
        )

        self.sftp = self.client.open_sftp()

    def run(self, command):
        """Run a remote command and return stdout + stderr"""
        self.connect()

        stdin, stdout, stderr = self.client.exec_command(command)
        out = stdout.read().decode(errors="ignore").strip()
        err = stderr.read().decode(errors="ignore").strip()

        return out + ("\n" + err if err else "")

    def push_file(self, local_path, remote_path):
        """Push a file via SFTP"""
        self.connect()
        self.sftp.put(local_path, remote_path)
        print(f"Transferred {local_path} → {remote_path}")

    def close(self):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        self.sftp = None
        self.client = None


# -------------------------------------------------
# Main logic
# -------------------------------------------------
ssh = SSHSession()

try:
    # Print NAD version
    print("NAD version:")
    print(ssh.run("cat /etc/version"))

    print("To CN '1' | EU '2'")
    region = input("Enter: ").strip()

    if region not in ("1", "2"):
        print("Invalid selection. Please enter 1 for CN or 2 for EU.")
        raise SystemExit(1)

    # -------------------------------------------------
    # Common steps
    # -------------------------------------------------
    print("Configuring smackfs...")
    ssh.run("bash -c 'echo - | tee /sys/fs/smackfs/onlycap'")

    print("Remounting /data as read-write...")
    ssh.run("mount -o remount,rw /data")

    # -------------------------------------------------
    # Region-specific provisioning
    # -------------------------------------------------
    if region == "1":
        print("Pushing CN provisioning file...")
        ssh.push_file(prov_CN, "/data/config-service/prov.xml")

    elif region == "2":
        print("Pushing EU provisioning file...")
        ssh.push_file(prov_EU, "/data/config-service/prov.xml")

    # -------------------------------------------------
    # Reload configuration (kept twice as in original)
    # -------------------------------------------------
    print("Reloading configuration with sldd...")
    ssh.run("sldd cfg reload 2 0 /data/config-service/prov.xml")
    ssh.run("sldd cfg reload 2 0 /data/config-service/prov.xml")

    # -------------------------------------------------
    # Display configuration
    # -------------------------------------------------
    print("its.json config:")
    print(ssh.run("cat /etc/its.json"))

finally:
    ssh.close()