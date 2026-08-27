# V2X Test Execution Automation Framework

A Python-based automation framework designed to **execute, monitor, validate, and report V2X test cases on Linux-based automotive ECUs**.

The framework automates the complete test execution workflow — from ECU connection and environment preparation to test execution, DLT log collection, verification, and final test reporting.

---

## 📌 Overview

Testing V2X functionality on automotive ECUs typically involves several manual activities:

* Connecting to multiple ECU terminals
* Preparing the test environment
* Pushing required binaries/configuration files
* Identifying the ECU software version
* Determining Master/SOP execution mode
* Starting required services
* Executing V2X commands
* Capturing console and DLT logs
* Converting logs for analysis
* Verifying expected results
* Preparing the final test report

This framework was developed to **automate and standardize these activities**, reducing manual effort and improving test execution consistency.

### Key Objective

> Automate the complete V2X test lifecycle while providing a reusable architecture for adding new test cases with minimal code duplication.

---

# 🚀 Key Features

* Automated ECU connection and communication
* ADB-based communication with Linux 64-bit ECUs
* SSH-based ECU communication
* UART/serial terminal support
* Persistent shell command execution
* Batch command execution with configurable delays
* Automatic Master/SOP software-version detection
* Automatic SOP environment preparation
* Automated file and folder transfer
* ECU binary permission and mount configuration
* Automatic DLT log capture
* Console log capture
* Multi-ECU test execution
* V2X test automation
* Cybersecurity test automation
* Diagnostics test automation
* Certificate download testing
* Geofencing testing
* Map-matching testing
* Object-forwarding testing
* Coding/provisioning testing
* Basic sanity test execution
* Post-test verification
* Automated DLT-to-CSV conversion
* Automated Excel test reporting
* Pass/Fail result generation
* Centralized test logging
* Reusable test-base architecture

---

# 🏗️ High-Level Architecture

```text
                    +----------------------+
                    |     Test Runner      |
                    |   test_runner.py     |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |      TestBase        |
                    | Test Lifecycle Mgmt  |
                    +----------+-----------+
                               |
             +-----------------+------------------+
             |                 |                  |
             v                 v                  v
      +-------------+   +-------------+    +-------------+
      |  ADBShell   |   | FileManager |    |  ADBLogger  |
      +------+------+   +------+------+    +------+------+
             |                 |                  |
             v                 v                  v
      +------------------------------------------------+
      |              Linux Automotive ECU             |
      |                                                |
      |  V2X Stack | Services | Binaries | Logs       |
      +----------------------+-------------------------+
                             |
                             v
                    +------------------+
                    |    DLT Logs      |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Verification /   |
                    | Result Analysis  |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Excel Test Report|
                    +------------------+
```

---

# 📂 Framework Components

## 1. Test Runner

The test runner provides a single entry point for executing different test groups.

Example:

```bash
python test_runner.py --list
```

Run a specific test:

```bash
python test_runner.py --test v2x
```

Other supported test groups include:

```text
v2x
dtc
diagnostics
cybersecurity
certificate_download
geofencing
map_matching
objforward
coding_prov
basic_sanity
```

The runner maintains a centralized test registry mapping each test name to its corresponding test implementation and log file.

---

# 2. TestBase

`TestBase` provides the common lifecycle and infrastructure required by all automated tests.

Instead of implementing ECU communication, logging, mode detection, and cleanup separately in every test case, individual tests inherit from the common base class.

```python
class MyTest(TestBase):

    def get_commands(self):
        return [
            "sldd cmd1",
            ("sldd cmd2", 3),
        ]
```

This provides a consistent test lifecycle:

```text
Determine ECU Mode
       ↓
Prepare Environment
       ↓
Custom Test Setup
       ↓
Execute Test
       ↓
Custom Cleanup
       ↓
Post-Test Verification
       ↓
SOP Cleanup
       ↓
Generate Result
```

---

# 3. Master / SOP Automatic Detection

One of the key features of the framework is automatic detection of the ECU software execution mode.

The framework reads:

```bash
cat /etc/version
```

and determines whether the ECU is operating in:

```text
MASTER
```

or

```text
SOP
```

mode.

If version information is insufficient, the framework can perform additional runtime detection.

### Master Mode

Commands are executed using the native binary:

```bash
sldd <command>
```

### SOP Mode

The framework prepares the SOP environment and uses:

```bash
/log/sldd <command>
```

It can automatically:

* Push required files
* Remount `/log/` with execution permission
* Configure binary permissions
* Adapt commands to the SOP binary path

This allows the same test implementation to operate across different ECU software variants.

---

# 4. ADBShell

`ADBShell` provides command execution on Linux-based 64-bit ECUs.

### Main capabilities

```text
run()
run_batch()
```

### Persistent Shell

`run()` executes commands through a persistent shell session, allowing a sequence of commands to be executed while maintaining the shell context.

Example:

```python
shell.run("cat /etc/version")
shell.run("cmd2")
shell.run("cmd3")
```

### Batch Execution

Multiple commands can be executed sequentially:

```python
commands = [
    "command_1",
    ("command_2", 3),
    "command_3",
]

shell.run_batch(commands)
```

The tuple format allows a custom delay to be associated with individual commands.

---

# 5. ADBFileManager

`ADBFileManager` provides automated file transfer between the host machine and ECU.

### Supported operations

```text
push()
pull()
push_folder()
```

Example:

```python
files.push(
    "local/config.json",
    "/data/v2xmgr/etc/config.json"
)
```

Folder transfer:

```python
files.push_folder(
    "local/test_data/",
    "/data/v2xmgr/etc/"
)
```

This eliminates repetitive manual file-copy operations during test setup.

---

# 6. ADBLogger

Centralized logging is provided through the `ADBLogger` component.

### Logging APIs

```text
log()
log_warn()
log_error()
```

The logger records:

* Test execution steps
* ECU command execution
* Setup information
* Warnings
* Errors
* Test completion status
* Execution logs

Example:

```python
logger.log("Starting V2X test")
logger.log_warn("Expected response not received")
logger.log_error("Test execution failed")
```

---

# 7. Helper Utilities

The framework provides reusable helper functions for common ECU operations and environment checks.

Examples include:

```text
is_certificate_present()
is_stack_on()
activate_stack()
is_icon_sf25()
is_binary_sop()
is_region_eu()
modify_its_cybersecurity()
modify_cff_mapmatching()
disable_map_matching_for_geofencing_in_cff()
modify_its_geofencing()
setup_sop_prerequisites()
```

These utilities prevent common operations from being duplicated across individual test cases.

---

# 🧪 Supported Test Areas

The framework is designed around independent test modules.

```text
                    Test Runner
                        |
        +---------------+----------------+
        |               |                |
        v               v                v
      V2X          Diagnostics      Cybersecurity
        |               |                |
        +---------------+----------------+
                        |
             +----------+----------+
             |          |          |
             v          v          v
        Geofencing  Map Matching  Object Forwarding
             |
             +----------+----------+
                        |
                        v
             Coding / Provisioning
                        |
                        v
                Basic Sanity
```

---

# 🔐 Cybersecurity Test Automation

The framework also supports V2X cybersecurity validation.

The cybersecurity test can:

1. Prepare cybersecurity-related files
2. Transfer certificates/test data to the ECU
3. Configure the ECU environment
4. Detect the current region
5. Execute region-specific tests
6. Change between supported regions
7. Restart required services where necessary
8. Inject valid and invalid V2X messages
9. Capture logs
10. Perform verification

Example test data includes valid and invalid signed V2X messages.

```text
Invalid Message
      |
      v
Message Injection
      |
      v
V2X Security Processing
      |
      v
DLT / Console Logs
      |
      v
Verification
```

The implementation supports region-specific cybersecurity execution for EU and CN configurations.

---

# 🔄 Test Execution Workflow

The complete automated workflow can be represented as:

```text
+----------------------+
| Start Test Runner    |
+----------+-----------+
           |
           v
+----------------------+
| Select Test Case     |
+----------+-----------+
           |
           v
+----------------------+
| Connect to ECU       |
+----------+-----------+
           |
           v
+----------------------+
| Read Software Version|
+----------+-----------+
           |
           v
+----------------------+
| Master or SOP ?      |
+-----+------------+---+
      |            |
   MASTER         SOP
      |            |
      |     +------v------+
      |     | Push Files  |
      |     | Mount /log  |
      |     | Set Perms   |
      |     +------+------+
      |            |
      +------+-----+
             |
             v
+----------------------+
| Test-Specific Setup  |
+----------+-----------+
           |
           v
+----------------------+
| Start DLT Capture    |
+----------+-----------+
           |
           v
+----------------------+
| Execute Test Group   |
+----------+-----------+
           |
           v
+----------------------+
| Capture Console Logs |
+----------+-----------+
           |
           v
+----------------------+
| Post-Test Verification|
+----------+-----------+
           |
           v
+----------------------+
| DLT → CSV Conversion |
+----------+-----------+
           |
           v
+----------------------+
| Generate Excel Report|
+----------+-----------+
           |
           v
+----------------------+
| Pass / Fail Result   |
+----------------------+
```

---

# 🖥️ Multi-ECU Execution

The framework supports test execution involving multiple devices.

The environment can communicate with ECUs through different interfaces:

```text
                 Test Automation Host
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
        ADB            SSH            UART
          |              |              |
          v              v              v
       ECU #1         ECU #2        Terminal /
                                      Device
```

This enables scenarios where one device is controlled through ADB while another device is accessed through SSH.

---

# 📋 Logging and Verification

During execution, the framework captures both:

### Console Logs

Commands and execution output are stored in test-specific log files.

Example:

```text
logs/
├── v2x_test.log
├── diagnostics_test.log
├── cybersecurity_test.log
├── geofencing.log
└── basic_sanity.log
```

### DLT Logs

DLT logs are collected for detailed ECU-side analysis.

The workflow is:

```text
Test Execution
      ↓
DLT Capture
      ↓
DLT Log File
      ↓
CSV Conversion
      ↓
Result Verification
```

---

# 📊 Automated Test Reporting

After test execution and verification, the framework generates a consolidated Excel report.

The report can be used to communicate:

```text
Test Case
Test Group
Execution Status
Expected Result
Actual Result
Pass / Fail
```

Example:

| Test Case         | Expected Result      | Actual Result        | Status |
| ----------------- | -------------------- | -------------------- | ------ |
| V2X Communication | Message transmitted  | Message received     | PASS   |
| Invalid Signature | Message rejected     | Message rejected     | PASS   |
| Certificate Test  | Certificate accepted | Certificate accepted | PASS   |
| Geofencing        | Event triggered      | Event triggered      | PASS   |

This provides the team with a clear summary of the overall test execution.

---

# 🛠️ Technology Stack

## Programming

```text
Python
```

## Automotive / Embedded

```text
V2X
DSRC
C-V2X
Linux-based ECU
ECU diagnostics
DLT
GNSS
```

## Communication

```text
ADB
SSH
UART / Serial
TCP/IP
```

## Testing / Debugging

```text
CANoe
Tera Term
MobaXterm
DLT Viewer
```

## Automation / CI

```text
Jenkins
```

## Reporting

```text
CSV
Excel
```

---

# ▶️ Usage

## List Available Tests

```bash
python test_runner.py --list
```

## Execute V2X Test

```bash
python test_runner.py --test v2x
```

## Execute Diagnostics Test

```bash
python test_runner.py --test diagnostics
```

## Execute Cybersecurity Test

```bash
python test_runner.py --test cybersecurity
```

## Execute Basic Sanity Test

```bash
python test_runner.py --test basic_sanity
```

The framework automatically determines whether the connected ECU requires Master or SOP execution.

---

# ➕ Adding a New Test Case

New test cases can be created by inheriting from `TestBase`.

Example:

```python
from test_base import TestBase


class MyV2XTest(TestBase):

    def get_commands(self):
        return [
            "sldd v2xmgr setdataprivacy 1",
            ("sldd power requestset 2004 7", 3),
            "sldd v2xmgr setdataprivacy 0",
        ]

    def setup_custom(self):
        # Test-specific setup
        pass

    def teardown_custom(self):
        # Test-specific cleanup
        pass
```

Register the test in the test runner:

```python
TEST_REGISTRY = {
    "my_test": {
        "class": MyV2XTest,
        "display": "My V2X Test",
        "log": "../logs/my_v2x_test.log"
    }
}
```

Run:

```bash
python test_runner.py --test my_test
```

---

# 🧩 Extensibility

The framework follows a reusable and modular architecture.

New functionality can be added without modifying the core execution infrastructure.

For example:

```text
                 TestBase
                    |
       +------------+------------+
       |            |            |
       v            v            v
    V2XTest      DTC Test     SecurityTest
       |            |            |
       +------------+------------+
                    |
                    v
              Common Framework
                    |
       +------------+-------------+
       |            |             |
       v            v             v
    ADBShell    FileManager    Logger
```

This separation provides:

* Code reuse
* Easier maintenance
* Consistent test execution
* Faster development of new test cases
* Centralized error handling
* Consistent logging
* Reduced code duplication

---

# 📈 Automation Benefits

The framework was developed to reduce the amount of manual effort required during repetitive V2X testing.

### Before Automation

```text
Manual ECU Connection
        ↓
Manual File Transfer
        ↓
Manual Configuration
        ↓
Manual Version Check
        ↓
Manual Command Execution
        ↓
Manual Log Collection
        ↓
Manual Verification
        ↓
Manual Report Creation
```

### After Automation

```text
              Test Runner
                   ↓
        Automated Environment Setup
                   ↓
          Automated Test Execution
                   ↓
          Automated Log Collection
                   ↓
          Automated Verification
                   ↓
          Automated Test Reporting
```

The automation reduced a typical manual execution workflow from approximately **3 hours to less than 90 minutes**.

---

# 🎯 Engineering Highlights

This project demonstrates experience in:

* Test automation framework design
* Python software development
* Object-oriented programming
* Linux-based embedded systems
* Automotive ECU interaction
* ADB and SSH communication
* UART/serial communication
* Persistent shell execution
* File transfer automation
* V2X protocol testing
* V2X cybersecurity testing
* ECU software-version detection
* Master/SOP abstraction
* DLT log analysis
* Automated verification
* Test reporting
* CI-oriented automation using Jenkins

---

# 🔒 Security & Confidentiality

This project may interact with proprietary automotive ECU software and V2X infrastructure.

When publishing this framework externally:

* Remove proprietary binaries
* Remove certificates and private keys
* Remove internal IP addresses
* Remove company-specific paths
* Remove credentials
* Remove proprietary configuration files
* Replace internal command names where required
* Use synthetic test data for demonstrations

Only the framework architecture and non-confidential examples should be shared publicly.

---

# 📌 Project Summary

**V2X Test Execution Automation Framework** is a reusable Python-based automation solution for executing and validating automotive V2X test cases on Linux-based ECUs.

The framework combines:

```text
ECU Communication
        +
Environment Automation
        +
Test Execution
        +
DLT Logging
        +
Verification
        +
Automated Reporting
```

to create an end-to-end automated V2X testing workflow.

The architecture is designed to make new test cases easy to add while keeping common ECU communication, logging, file management, environment detection, and execution logic centralized.


# How to Use ?
- Run the `setup.bat` it will setup necessary libraries, dependencies and install python if not already installed.

