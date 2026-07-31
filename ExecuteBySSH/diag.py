
# #!/usr/bin/env python3
# import sys
# import time
# import argparse
# from datetime import datetime
# import shlex

# try:
#     import paramiko
# except ImportError:
#     print("ERROR: This script requires the 'paramiko' package. Install it with: pip install paramiko", file=sys.stderr)
#     sys.exit(1)

# def log(msg: str):
#     ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     print(f"[{ts}] {msg}")

# def connect_ssh(host: str, user: str, key_file: str = None, password: str = None,
#                 accept_host_key: bool = False) -> paramiko.SSHClient:
#     client = paramiko.SSHClient()
#     if accept_host_key:
#         client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     else:
#         client.set_missing_host_key_policy(paramiko.RejectPolicy())

#     # Prefer key authentication, fallback to password if provided
#     log(f"Connecting to {user}@{host} ...")
#     client.connect(
#         hostname=host,
#         username=user,
#         key_filename=key_file,
#         password=password,
#         allow_agent=True,
#         look_for_keys=True,
#         timeout=20,
#     )
#     log("SSH connected.")
#     return client


# def run_cmd_exec(client, command: str, timeout: int = 60):
#     """Run a command via exec_command on an existing SSH connection (bash -lc wrapper)."""
#     # Safely quote the command for bash -lc
#     quoted = shlex.quote(command)
#     full_cmd = f"bash -lc {quoted}"

#     log(f"EXEC: {command}")
#     stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)

#     out = stdout.read().decode(errors='ignore').strip()
#     err = stderr.read().decode(errors='ignore').strip()

#     rc = stdout.channel.recv_exit_status()
#     if out:
#         print(out)
#     if err:
#         print(err, file=sys.stderr)
#     log(f"Exit code: {rc}\n")
#     return rc, out, err


# def open_interactive_shell(client: paramiko.SSHClient):
#     """Open a single interactive shell (bash -li) and return the channel."""
#     chan = client.invoke_shell(width=200, height=50)
#     # Start bash login shell to get environment
#     # Send a command to identify start
#     chan.send("bash -li\n")
#     time.sleep(0.8)
#     # Drain any initial output
#     _drain_channel(chan, 0.2)
#     return chan

# def _drain_channel(chan: paramiko.Channel, idle_window: float = 0.1) -> str:
#     """Read available data from channel until it idles for idle_window seconds."""
#     buf = []
#     last = time.time()
#     while True:
#         if chan.recv_ready():
#             data = chan.recv(4096)
#             if not data:
#                 break
#             buf.append(data.decode(errors='ignore'))
#             last = time.time()
#         else:
#             if time.time() - last > idle_window:
#                 break
#             time.sleep(0.05)
#     return ''.join(buf)


# def run_cmd_shell(chan, command: str, timeout: int = 60):
#     """
#     Run a command inside the *single* interactive shell and capture output + exit code.

#     We send: bash -lc '<quoted_command>'; echo __RC__$?
#     Then we parse the __RC__ marker to get the numeric exit code.
#     """
#     quoted = shlex.quote(command)
#     marked = f"bash -lc {quoted}; echo __RC__$?\n"

#     log(f"SHELL: {command}")
#     chan.send(marked)

#     start = time.time()
#     output = ''
#     rc = None

#     while True:
#         chunk = _drain_channel(chan, idle_window=0.15)
#         if chunk:
#             output += chunk
#             # detect the exit-code marker
#             if "__RC__" in output:
#                 lines = output.strip().splitlines()
#                 # scan from end for the marker line
#                 for i in range(len(lines) - 1, -1, -1):
#                     if lines[i].startswith("__RC__"):
#                         try:
#                             rc = int(lines[i].split('__RC__')[-1])
#                         except Exception:
#                             rc = None
#                         # remove marker line from printed output
#                         output = '\n'.join(l for idx, l in enumerate(lines) if idx != i)
#                         break

#         if rc is not None:
#             break
#         if time.time() - start > timeout:
#             log(f"Timeout after {timeout}s for command: {command}")
#             rc = 124
#             break
#         time.sleep(0.05)

#     out = output.strip()
#     if out:
#         print(out)
#     log(f"Exit code: {rc}\n")
#     return rc, out, ''

# # ------------------------- Steps definition -------------------------
# def steps_definition():
#     """Return the ordered steps translated from the batch script."""
#     return [
#         { 'echo': 'Starting V2X Diagnostic Script...' },
#         { 'delay': 5 },
#         { 'cmd': 'cat /etc/version' },

#         { 'echo': 'Step 1: Reading DID 43A0' },
#         { 'cmd': 'sldd Diag readDid 43a0' },
#         { 'delay': 1 },

#         { 'echo': 'Step 2: Writing value 00 to DID 43A0' },
#         { 'cmd': 'sldd Diag writeDid 43A0 00' },
#         { 'delay': 3 },

#         { 'echo': 'Step 3: Reading DID 43A0' },
#         { 'cmd': 'sldd Diag readDid 43A0' },
#         { 'delay': 1 },

#         { 'echo': 'Step 4: Writing value 01 to DID 43A0' },
#         { 'cmd': 'sldd Diag writeDid 43A0 01' },
#         { 'delay': 3 },

#         { 'echo': 'Step 5: Reading DID 43A0' },
#         { 'cmd': 'sldd Diag readDid 43A0' },
#         { 'delay': 1 },

#         { 'echo': 'Step 6: Reading V2X Security Diagnostics' },
#         { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_SECURITY' },
#         { 'delay': 1 },

#         { 'echo': 'Step 7: Reading V2X Radio Diagnostics' },
#         { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_RADIO' },
#         { 'delay': 1 },

#         { 'echo': 'Step 8: Reading V2X Stack Configuration' },
#         { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_STACK_CONFIGURATION' },
#         { 'delay': 1 },

#         { 'echo': 'Step 9: Reading V2X HSM Diagnostics (1st read)' },
#         { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_HSM' },
#         { 'delay': 1 },

#         { 'echo': 'Step 10: Reading V2X HSM Diagnostics (2nd read)' },
#         { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_HSM' },
#         { 'delay': 1 },

#         { 'echo': 'Step 11: Reading V2X Compensator LNA' },
#         { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_COMPENSATOR_LNA' },
#         { 'delay': 1 },

#         { 'echo': 'All diagnostics completed.' },
#     ]

# # ------------------------- Runner -------------------------


# def main():
#     # ---- Assign your settings here ----
#     host = "160.48.249.97"  # target IP/host
#     user = "root"           # SSH user
#     key_file = r"C:\Users\ranjan08.kumar\.ssh\nad_root_key_new"  # private key path
#     accept_host_key = True  # auto-accept host key
#     timeout = 60            # per-command timeout (seconds)

#     # ---- Connect once ----
#     client = connect_ssh(
#         host=host,
#         user=user,
#         key_file=key_file,
#         password=None,
#         accept_host_key=accept_host_key,
#     )

#     steps = steps_definition()  # your existing steps list

#     try:
#         log('Opening a single interactive shell session...')
#         chan = open_interactive_shell(client)

#         for step in steps:
#             # echo-only steps
#             if 'echo' in step:
#                 print(step['echo'])
#                 continue

#             # delay-only steps
#             if 'delay' in step:
#                 d = int(step['delay'])
#                 if d > 0:
#                     log(f"Sleeping {d}s...")
#                     time.sleep(d)
#                 continue

#             # normal command
#             cmd = step['cmd']
#             run_cmd_shell(chan, cmd, timeout=timeout)

#     finally:
#         log('Closing SSH connection...')
#         client.close()
#         log('Done!')


# if __name__ == '__main__':
#     main()





#!/usr/bin/env python3
r"""
V2X Diagnostic Script over SSH (single persistent session)

This script converts your Windows batch/ADB flow into a Python program that
runs the same commands on a Linux target via SSH, keeping ONE interactive bash
session open for all commands.

How to run (PowerShell):
  python .\diag.py

Requirements on the machine running this script:
  - Python 3.8+
  - Paramiko: pip install paramiko
"""

import sys
import time
import shlex
from datetime import datetime

try:
    import paramiko
except ImportError:
    print("ERROR: This script requires the 'paramiko' package. Install it with: pip install paramiko", file=sys.stderr)
    sys.exit(1)

# ------------------------- Logging -------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}")

# ------------------------- SSH helpers -------------------------

def connect_ssh(host: str, user: str, key_file: str = None, password: str = None,
                accept_host_key: bool = True) -> paramiko.SSHClient:
    """Open a single SSH client connection."""
    client = paramiko.SSHClient()
    if accept_host_key:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    log(f"Connecting to {user}@{host} ...")
    client.connect(
        hostname=host,
        username=user,
        key_filename=key_file,
        password=password,
        allow_agent=True,
        look_for_keys=True,
        timeout=20,
    )
    log("SSH connected.")
    return client


def open_interactive_shell(client: paramiko.SSHClient) -> paramiko.Channel:
    """Open a login bash shell on the SSH connection and return the channel."""
    chan = client.invoke_shell(width=200, height=50)
    # Start a login shell so PATH/env are available
    chan.send("bash -li\n")
    time.sleep(0.8)
    _drain_channel(chan, idle_window=0.25)
    return chan


def _drain_channel(chan: paramiko.Channel, idle_window: float = 0.15) -> str:
    """Read all available data until the channel idles for idle_window seconds."""
    buf = []
    last = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096)
            if not data:
                break
            buf.append(data.decode(errors='ignore'))
            last = time.time()
        else:
            if time.time() - last > idle_window:
                break
            time.sleep(0.05)
    return ''.join(buf)


def run_cmd_shell(chan: paramiko.Channel, command: str, timeout: int = 60):
    """
    Run a command inside the single interactive shell and capture output & exit code.
    We send: bash -lc '<quoted_command>'; echo __RC__$?
    Then parse the __RC__ marker for the numeric exit code.
    Returns (rc, stdout, stderr='').
    """
    quoted = shlex.quote(command)
    marked = f"bash -lc {quoted}; echo __RC__$?\n"

    log(f"SHELL: {command}")
    chan.send(marked)

    start = time.time()
    output = ''
    rc = None

    while True:
        chunk = _drain_channel(chan, idle_window=0.20)
        if chunk:
            output += chunk
            if "__RC__" in output:
                # Extract the last RC marker line and remove it from output
                lines = output.strip().splitlines()
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].startswith("__RC__"):
                        try:
                            rc = int(lines[i].split('__RC__')[-1])
                        except Exception:
                            rc = None
                        output = '\n'.join(l for idx, l in enumerate(lines) if idx != i)
                        break
        if rc is not None:
            break
        if time.time() - start > timeout:
            log(f"Timeout after {timeout}s for command: {command}")
            rc = 124
            break
        time.sleep(0.05)

    out = output.strip()
    if out:
        print(out)
    log(f"Exit code: {rc}\n")
    return rc, out, ''

# ------------------------- Steps definition -------------------------

def steps_definition():
    """Return the ordered steps translated from your batch script."""
    return [
        { 'echo': 'Starting V2X Diagnostic Script...' },
        { 'delay': 5 },
        { 'cmd': 'cat /etc/version' },

        { 'echo': 'Step 1: Reading DID 43A0' },
        { 'cmd': 'sldd Diag readDid 43a0' },
        { 'delay': 1 },

        { 'echo': 'Step 2: Writing value 00 to DID 43A0' },
        { 'cmd': 'sldd Diag writeDid 43A0 00' },
        { 'delay': 3 },

        { 'echo': 'Step 3: Reading DID 43A0' },
        { 'cmd': 'sldd Diag readDid 43A0' },
        { 'delay': 1 },

        { 'echo': 'Step 4: Writing value 01 to DID 43A0' },
        { 'cmd': 'sldd Diag writeDid 43A0 01' },
        { 'delay': 3 },

        { 'echo': 'Step 5: Reading DID 43A0' },
        { 'cmd': 'sldd Diag readDid 43A0' },
        { 'delay': 1 },

        { 'echo': 'Step 6: Reading V2X Security Diagnostics' },
        { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_SECURITY' },
        { 'delay': 1 },

        { 'echo': 'Step 7: Reading V2X Radio Diagnostics' },
        { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_RADIO' },
        { 'delay': 1 },

        { 'echo': 'Step 8: Reading V2X Stack Configuration' },
        { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_STACK_CONFIGURATION' },
        { 'delay': 1 },

        { 'echo': 'Step 9: Reading V2X HSM Diagnostics (1st read)' },
        { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_HSM' },
        { 'delay': 1 },

        { 'echo': 'Step 10: Reading V2X HSM Diagnostics (2nd read)' },
        { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_HSM' },
        { 'delay': 1 },

        { 'echo': 'Step 11: Reading V2X Compensator LNA' },
        { 'cmd': 'sldd v2xmgr readDiag RDBI_V2X_COMPENSATOR_LNA' },
        { 'delay': 1 },

        { 'echo': 'All diagnostics completed.' },
    ]

# ------------------------- Main (single session, no args) -------------------------

def main():
    # ---- Assign your settings here ----
    host = "160.48.249.97"  # target IP/host
    user = "root"           # SSH user
    key_file = r"C:\\Users\\ranjan08.kumar\\.ssh\\nad_root_key_new"  # private key path (Windows)
    accept_host_key = True   # auto-accept host key
    timeout = 60             # per-command timeout (seconds)

    # ---- Connect once ----
    client = connect_ssh(
        host=host,
        user=user,
        key_file=key_file,
        password=None,
        accept_host_key=accept_host_key,
    )

    steps = steps_definition()

    try:
        log('Opening a single interactive shell session...')
        chan = open_interactive_shell(client)

        for step in steps:
            # echo-only steps
            if 'echo' in step:
                print(step['echo'])
                continue

            # delay-only steps
            if 'delay' in step:
                d = int(step['delay'])
                if d > 0:
                    log(f"Sleeping {d}s...")
                    time.sleep(d)
                continue

            # normal command
            cmd = step['cmd']
            run_cmd_shell(chan, cmd, timeout=timeout)

    finally:
        log('Closing SSH connection...')
        client.close()
        log('Done!')


if __name__ == '__main__':
    main()
