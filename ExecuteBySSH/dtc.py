
#!/usr/bin/env python3
"""
Run the V2X PKI test cases on a Linux target over SSH from a Windows laptop.
This script converts the provided Windows batch/ADB flow into SSH-based execution.

Usage example (PowerShell):
  python v.\dtc.py     --host 160.48.249.97     --user root     --key C:\Users\ranjan08.kumar\.ssh\nad_root_key_new     --accept-host-key
"""

from pathlib import Path
import subprocess
import sys
import time
import shlex
import argparse
import shutil
from datetime import datetime

# ------------------------- SSH helpers -------------------------

def log(msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}")


def ensure_ssh_available():
    ssh_path = shutil.which('ssh')
    if not ssh_path:
        raise RuntimeError(
            "OpenSSH client 'ssh' not found on PATH. On Windows, enable 'OpenSSH Client' via Optional Features or install Git for Windows (includes ssh)."
        )
    return ssh_path


def normalize_key_path(key: str) -> str:
    p = Path(key).expanduser()
    return str(p.resolve())


def ssh_run(host: str, user: str, key: str, command: str, timeout: int = 60,
            accept_host_key: bool = False, use_bash_login_shell: bool = True):
    """Run a single command on remote host via ssh. Returns (rc, stdout, stderr)."""
    ssh_bin = ensure_ssh_available()
    key_path = normalize_key_path(key)

    ssh_opts = [
        ssh_bin,
        '-i', key_path,
        '-o', 'BatchMode=yes',
    ]
    if accept_host_key:
        ssh_opts += ['-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL']

    target = f"{user}@{host}"

    if use_bash_login_shell:
        quoted_cmd = shlex.quote(command)
        remote_cmd = f"bash -lc {quoted_cmd}"
    else:
        remote_cmd = command

    full_cmd = ssh_opts + [target, remote_cmd]

    log(f"SSH exec: {command}")
    try:
        proc = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)
        log(f"Exit code: {proc.returncode}")
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        log(f"Timeout after {timeout}s for command: {command}")
        return 124, '', f"Timeout after {timeout}s"

# ------------------------- Test runner -------------------------

def sleep_s(seconds: int):
    if seconds <= 0:
        return
    log(f"Sleeping {seconds}s...")
    time.sleep(seconds)


def do_step(host, user, key, description: str, actions, accept_host_key: bool, default_timeout: int = 60):
    """
    Run a step with a description and a list of actions.
    actions: list of dicts with keys:
      - cmd: command string to run on remote
      - delay: seconds to sleep AFTER this command
      - timeout: optional timeout for this command
      - echo: optional message to print locally (no remote execution)
    """
    log(description)
    for act in actions:
        if 'echo' in act and act.get('echo'):
            print(act['echo'])
            sleep_s(act.get('delay', 0))
            continue
        cmd = act['cmd']
        timeout = int(act.get('timeout', default_timeout))
        rc, _, err = ssh_run(host, user, key, cmd, timeout=timeout, accept_host_key=accept_host_key)
        if rc != 0:
            log(f"WARN: Command failed (rc={rc}): {cmd}stderr: {err}")
        sleep_s(int(act.get('delay', 0)))


def build_actions_for_error(flag: str, delay_between: int = 5):
    """Helper to build actions that set a DTC flag 1 then 0 with delays."""
    return [
        { 'delay': delay_between },  # initial delay before first command
        { 'cmd': f"sldd v2xmgr setDTC {flag} 1", 'delay': delay_between },
        { 'cmd': f"sldd v2xmgr setDTC {flag} 0", 'delay': delay_between },
    ]

# ------------------------- Main flow -------------------------

def main():
    parser = argparse.ArgumentParser(description='Run V2X PKI test cases over SSH.')
    parser.add_argument('--host', required=True, help='Target host/IP (e.g., 160.48.249.97)')
    parser.add_argument('--user', default='root', help='SSH user (default: root)')
    parser.add_argument('--key', required=True, help='Path to private key')
    parser.add_argument('--accept-host-key', action='store_true', help='Auto-accept host key (no prompts)')
    parser.add_argument('--timeout', type=int, default=60, help='Default timeout per command (seconds)')
    parser.add_argument('--repeat-count', type=int, default=4, help='Repeat count for TC18 loop (default: 4)')
    parser.add_argument('--no-bash-login', action='store_true', help='Do not wrap commands in "bash -lc"')

    args = parser.parse_args()

    host = args.host
    user = args.user
    key = args.key
    accept = args.accept_host_key
    default_timeout = args.timeout
    use_bash = not args.no_bash_login

    log('Starting V2X PKI test cases...')

    # NAD version
    do_step(host, user, key, 'NAD version:', [
        { 'delay': 2 },
        { 'cmd': 'cat /etc/version', 'delay': 0 },
    ], accept, default_timeout)

    # TC1: Authorization request failed
    do_step(host, user, key, 'TC1: V2X PKI Client: Authorization request failed',
            build_actions_for_error('PKI_ERROR_AUTH_REQ_FAILED'), accept, default_timeout)

    # TC2: Update certificate list failed
    do_step(host, user, key, 'TC2: V2X PKI Client: Update certificate list failed',
            build_actions_for_error('PKI_ERROR_CERT_LIST_UPDATE_FAILED'), accept, default_timeout)

    # TC3: Unable to connect to V2X SW stack
    do_step(host, user, key, 'TC3: V2X PKI Client: Unable to connect to V2X SW stack',
            build_actions_for_error('PKI_ERROR_V2X_STACK_CONNECTION_ERROR'), accept, default_timeout)

    # TC4: Unable to connect to V2X PKI server
    do_step(host, user, key, 'TC4: V2X PKI Client: Unable to connect to V2X PKI server',
            build_actions_for_error('PKI_ERROR_PKI_SERVER_CONNECTION_ERROR'), accept, default_timeout)

    # TC5: File system access error
    do_step(host, user, key, 'TC5: V2X PKI Client: File system access error',
            build_actions_for_error('PKI_ERROR_FS_ACCESS_ERROR'), accept, default_timeout)

    # TC6: Enrollment failed
    do_step(host, user, key, 'TC6: V2X PKI Client: Enrollment failed',
            build_actions_for_error('PKI_ERROR_ENROLLMENT_FAILED'), accept, default_timeout)

    # TC7: Authorization download failed
    do_step(host, user, key, 'TC7: V2X PKI Client: Authorization download failed',
            build_actions_for_error('PKI_ERROR_AUTH_DOWNLOAD_FAILED'), accept, default_timeout)

    # TC8: Enrollment renewal failed
    do_step(host, user, key, 'TC8: V2X PKI Client - Enrollment renewal failed',
            build_actions_for_error('PKI_ERROR_REENROLLMENT_FAILED'), accept, default_timeout)

    # TC9: ECDSA accelerator access error
    do_step(host, user, key, 'TC9: V2X SW Stack: ECDSA accelerator access error',
            build_actions_for_error('STACK_ERROR_ECDSA_ACCESS_ERROR'), accept, default_timeout)

    # TC10: File system access error
    do_step(host, user, key, 'TC10: V2X SW Stack: File system access error',
            build_actions_for_error('STACK_ERROR_FS_ACCESS_ERROR'), accept, default_timeout)

    # TC11: HSM access error (last delay in script was 8 sec)
    do_step(host, user, key, 'TC11: V2X SW Stack: HSM access error', [
        { 'delay': 5 },
        { 'cmd': 'sldd v2xmgr setDTC STACK_ERROR_HSM_ACCESS_ERROR 1', 'delay': 5 },
        { 'cmd': 'sldd v2xmgr setDTC STACK_ERROR_HSM_ACCESS_ERROR 0', 'delay': 8 },
    ], accept, default_timeout)

    # TC12: Missing V2X authorization certificate
    do_step(host, user, key, 'TC12: V2X SW Stack: Missing V2X authorization certificate',
            build_actions_for_error('STACK_ERROR_MISSING_AUTH_CERT'), accept, default_timeout)

    # TC13: Missing V2X certificate list
    do_step(host, user, key, 'TC13: V2X SW Stack: Missing V2X certificate list',
            build_actions_for_error('STACK_ERROR_MISSING_CERT_LIST'), accept, default_timeout)

    # TC14: V2X deactivated by diagnosis
    do_step(host, user, key, 'TC14: V2X deactivated by diagnosis', [
        { 'delay': 5 },
        { 'cmd': 'sldd Diag writeDid 43A0 00', 'delay': 10 },
        { 'cmd': 'sldd Diag writeDid 43A0 01', 'delay': 5 },
    ], accept, default_timeout)

    # TC15: V2X function unavailable (stop/start its)
    do_step(host, user, key, 'TC15: V2X function unavailable', [
        { 'delay': 5 },
        { 'cmd': 'systemctl stop its', 'delay': 10 },
        { 'cmd': 'systemctl start its', 'delay': 5 },
    ], accept, default_timeout)

    # TC16: Missing navigation information
    do_step(host, user, key, 'TC16: V2X SW Stack: Missing navigation information',
            build_actions_for_error('STACK_ERROR_MISSING_NAV_INFO'), accept, default_timeout)

    # TC17: Missing map information
    do_step(host, user, key, 'TC17: V2X SW Stack: Missing map information',
            build_actions_for_error('STACK_ERROR_MISSING_MAP_INFO'), accept, default_timeout)

    # TC18: V2X radio access error + reboot sequence
    log('TC18: V2X SW Stack: V2X radio access error')
    log('Device is going to reboot in this Test Case')
    current = 0
    count = int(args.repeat_count)
    while current < count:
        print(f"Count is {current}")
        sleep_s(10)
        ssh_run(host, user, key, 'sldd v2xmgr setdataprivacy 1', timeout=default_timeout, accept_host_key=accept)
        ssh_run(host, user, key, 'systemctl start its', timeout=default_timeout, accept_host_key=accept)
        sleep_s(10)
        ssh_run(host, user, key, 'sldd v2xmgr setDTC STACK_ERROR_RADIO_ACCESS_ERROR 1', timeout=default_timeout, accept_host_key=accept)
        sleep_s(10)
        current += 1
    sleep_s(1)
    # Reboot at the end. This will likely drop SSH; ignore its exit code.
    log('Rebooting device...')
    try:
        ssh_run(host, user, key, 'reboot', timeout=15, accept_host_key=accept)
    except Exception as e:
        log(f"Reboot command triggered; SSH may drop: {e}")
    sleep_s(1)

    log('Done!')


if __name__ == '__main__':
    main()
