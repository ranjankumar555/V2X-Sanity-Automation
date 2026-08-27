# V2X Test Execution Automation Framework

A Python-based automation framework designed to automate the execution, monitoring, validation, logging, and reporting of V2X test cases on Linux-based automotive ECUs.

The framework was developed to replace repetitive manual test activities with a reusable and extensible automation architecture.

It provides automated ECU communication, environment preparation, test execution, DLT log collection, result verification, and test report generation.

---

## 📌 Project Overview

V2X testing on automotive ECUs typically involves several repetitive activities:

- Connecting to the ECU
- Preparing the test environment
- Transferring required files
- Checking ECU software versions
- Determining the ECU execution mode
- Starting required services
- Executing V2X commands
- Monitoring console output
- Capturing DLT logs
- Performing post-test verification
- Generating test reports

Performing these activities manually for every test case is time-consuming and error-prone.

This framework automates the complete test execution workflow and provides a common infrastructure that can be reused across different test modules.

### Key Result

The automation reduced a typical manual test execution workflow from approximately **3 hours to less than 90 minutes**.

---

# 🎯 Objectives

The main objectives of the framework are:

- Reduce manual test execution effort
- Standardize ECU test execution
- Provide reusable test infrastructure
- Automate ECU environment preparation
- Support multiple ECU execution modes
- Automate log collection and analysis
- Improve test execution consistency
- Simplify development of new test cases
- Provide automated Pass/Fail reporting
- Support CI-oriented execution

---

# 🏗️ High-Level Architecture

```text
                         +----------------------+
                         |      Test Runner     |
                         |    test_runner.py    |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |       TestBase       |
                         | Test Lifecycle Mgmt  |
                         +----------+-----------+
                                    |
              +---------------------+---------------------+
              |                     |                     |
              v                     v                     v
       +-------------+       +-------------+       +-------------+
       |  ADBShell   |       | FileManager |       |  ADBLogger  |
       +------+------+       +------+------+       +------+------+
              |                     |                     |
              +---------------------+---------------------+
                                    |
                                    v
                         +----------------------+
                         |    Linux ECU / DUT   |
                         |                      |
                         | V2X Stack            |
                         | Services             |
                         | Applications         |
                         | Configuration        |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |      DLT Logs        |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Verification &       |
                         | Result Processing    |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Excel Test Report    |
                         +----------------------+
````

---

# ✨ Key Features

* Python-based modular automation framework
* Linux ECU automation
* Persistent ADB shell execution
* Automatic shell reconnection
* ECU reboot recovery
* ADB file and folder transfer
* Batch command execution
* Command execution timeout protection
* Sentinel-based command completion detection
* Real-time command output processing
* Master/SOP execution-mode detection
* Automatic SOP environment preparation
* ECU binary permission and mount configuration
* DLT log capture
* Console log collection
* Automated DLT-to-CSV conversion
* Automated test verification
* Excel test reporting
* Multiple V2X test modules
* Cybersecurity test automation
* Diagnostics test automation
* Certificate-related testing
* Geofencing testing
* Map-matching testing
* Object-forwarding testing
* Coding/provisioning testing
* Basic sanity testing
* Jenkins/CI integration support
* Reusable test-base architecture

---

# 🔌 ECU Communication

The framework communicates with Linux-based automotive ECUs through ADB.

The communication layer provides:

```text
                    Python Automation
                           |
                           v
                       ADBShell
                           |
                  +--------+--------+
                  |                 |
                stdin             stdout
                  |                 |
                  v                 v
             adb shell        Reader Thread
                  |                 |
                  v                 v
              Linux ECU       Output Queue
```

The communication layer is abstracted from individual test cases so that test developers can focus on test logic rather than low-level process management.

---

# ⚡ Persistent ADB Shell

One of the core components of the framework is the `ADBShell` class.

Instead of starting a new `adb shell` process for every command, the framework creates a **persistent shell process** and keeps it alive during test execution.

## Conventional Approach

```text
Command 1
   |
   +--> adb shell
   +--> Execute
   +--> Process terminates

Command 2
   |
   +--> adb shell
   +--> Execute
   +--> Process terminates

Command 3
   |
   +--> adb shell
   +--> Execute
   +--> Process terminates
```

Repeated process creation introduces unnecessary overhead.

## Framework Approach

```text
                 Python Framework
                        |
                        v
                +---------------+
                | Persistent    |
                | adb shell     |
                +-------+-------+
                        |
                        v
                    Linux ECU
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
      Command 1     Command 2     Command 3
```

The same shell session is reused for the complete test execution.

---

# 🧠 ADBShell Design

The `ADBShell` class is responsible for:

* Starting the ADB shell
* Maintaining the shell process
* Sending commands through stdin
* Reading stdout asynchronously
* Detecting command completion
* Returning command output
* Handling command timeouts
* Detecting shell termination
* Automatically reconnecting after connection loss
* Supporting batch command execution
* Closing the shell gracefully

The primary interface is intentionally simple:

```python
shell.run(command)
shell.run_batch(commands)
shell.close()
```

---

# 🔄 Persistent Shell Initialization

When `ADBShell` is initialized, the framework first waits for the ECU:

```bash
adb wait-for-device root
```

It then creates the persistent shell using `subprocess.Popen()`:

```python
self.proc = subprocess.Popen(
    [self.adb_cmd, "shell"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)
```

The process remains alive while commands are sent through its `stdin`.

---

# 🧵 Asynchronous Output Reader

A background reader thread continuously reads the shell's stdout.

Conceptually:

```text
                  adb shell
                     |
                     | stdout
                     v
              +--------------+
              | Reader Thread |
              +------+-------+
                     |
                     v
              +--------------+
              | Queue.Queue   |
              +------+-------+
                     |
                     v
                  run()
```

The reader thread places every received line into a thread-safe queue.

This separates ECU output collection from command execution.

Example:

```python
def _enqueue_output(self):
    for line in self.proc.stdout:
        self.q.put(line)
```

The main `run()` method consumes data from this queue.

---

# ▶️ `run()` Function

The `run()` function is the primary command-execution API.

```python
run(command, timeout=10, use_sentinel=True)
```

Example:

```python
output = shell.run(
    "cmd to execure"
)
```

The function performs the following operations:

```text
run(command)
     |
     v
Check shell status
     |
     +---- Shell dead?
     |         |
     |         v
     |      Reconnect
     |
     v
Generate unique sentinel
     |
     v
Append sentinel to command
     |
     v
Send command to persistent shell
     |
     v
Read output from queue
     |
     v
Check for completion sentinel
     |
     v
Clean internal marker
     |
     v
Log output
     |
     v
Return command output
```

---

# 🚦 Sentinel-Based Command Completion

A major challenge with persistent shells is determining exactly when a command has finished.

Simply waiting for output is not sufficient because:

* Commands can produce multiple lines
* Some commands may produce no output
* Output may arrive asynchronously
* Shell prompts are not always reliable
* A fixed sleep introduces unnecessary delays

To solve this, the framework uses a unique **sentinel marker**.

For example, the original command:

```bash
command
```

is internally transformed into:

```bash
command to execute ; echo __CMD_DONE_<unique-id>__
```

The shell produces:

```text
command output...
command output...
command output...
__CMD_DONE_<unique-id>__
```

When the framework detects the sentinel, it knows that the command has completed.

---

# 🔐 Unique Sentinel Generation

A UUID is used to create a unique completion marker:

```python
sentinel = f"__CMD_DONE_{uuid.uuid4().hex}__"
```

For example:

```text
__CMD_DONE_91c72d8a1c5c4c3e8f...__
```

A different marker is generated for every command.

This minimizes the possibility of normal ECU output being mistaken for a completion signal.

---

# ⚡ Why Sentinel Mode?

The sentinel mechanism provides deterministic and fast command-completion detection.

Instead of:

```text
Execute
   |
   v
Wait fixed amount of time
   |
   v
Assume command completed
```

the framework uses:

```text
Execute
   |
   v
Read output
   |
   v
Detect explicit completion marker
   |
   v
Command completed
```

This avoids unnecessary waiting for commands that finish quickly while still providing a completion mechanism for commands that take longer.

---

# 🧹 Sentinel Output Cleanup

The sentinel is an internal automation mechanism and should not be visible in the actual test output.

The framework therefore removes the marker before logging/returning the final command output.

For example:

### Raw output

```text
sh-3.2# chmod 777 /data/v2xmgr/etc/ ; echo __CMD_DONE_xyz__
```

### Cleaned output

```text
sh-3.2# chmod 777 /data/v2xmgr/etc/
```

If the line contains only:

```text
__CMD_DONE_xyz__
```

the framework discards it.

This keeps the returned output clean for subsequent verification and reporting.

---

# ⏱️ Command Timeout

The `run()` function implements a hard timeout to prevent the complete automation framework from hanging indefinitely.

Default:

```python
timeout=10
```

Custom timeout:

```python
shell.run(
    "long_running_command",
    timeout=30
)
```

Timeout protection helps handle:

* Hung commands
* ECU communication problems
* Missing completion markers
* Unexpected target behavior
* Service failures

---

# 🔁 Prompt-Based Fallback

Sentinel mode is enabled by default.

The framework also provides a fallback mechanism based on shell-prompt detection:

```python
shell.run(
    "some_command",
    use_sentinel=False
)
```

The implementation checks for shell prompts ending in:

```text
#
$
```

Conceptually:

```text
                 run()
                   |
          +--------+--------+
          |                 |
          v                 v
     Sentinel Mode      Prompt Mode
          |                 |
          v                 v
 Explicit completion    Shell prompt
      marker              detected
          |                 |
          +--------+--------+
                   |
                   v
             Command Done
```

---

# 🔄 Automatic Reconnection

Embedded ECU testing often includes operations that reboot the target.

A reboot can terminate the active ADB shell.

The framework automatically detects this condition and recreates the shell connection.

```text
                  Test Running
                       |
                       v
                   ECU Reboot
                       |
                       v
                ADB Shell Lost
                       |
                       v
            Framework Detects Failure
                       |
                       v
             Reconnection Attempt
                       |
                       v
                New adb shell
                       |
                       v
              Continue Execution
```

Before executing a command, `run()` checks whether the shell process is still alive.

If it has terminated, `_reconnect_if_needed()` attempts to establish a new shell.

---

# 🔁 Reconnection Retry Mechanism

The reconnect behavior is configurable:

```python
ADBShell(
    adb_cmd="adb",
    reconnect_attempts=3,
    reconnect_delay=5
)
```

The default strategy is:

```text
Shell Lost
    |
    v
Attempt 1
    |
    +---- Success ---> Continue
    |
    +---- Failure
             |
             v
          Wait 5s
             |
             v
          Attempt 2
             |
             +---- Success ---> Continue
             |
             +---- Failure
                      |
                      v
                   Wait 5s
                      |
                      v
                   Attempt 3
                      |
                      +---- Success ---> Continue
                      |
                      +---- Failure
                               |
                               v
                           Raise Error
```

This is especially useful for tests involving:

* ECU reboot
* Application restart
* Service restart
* Software restart
* ADB disconnection
* ECU recovery procedures

---

# 🧪 Reboot-Aware Test Execution

A test can execute commands before and after an ECU reboot without requiring the test developer to manually recreate the shell.

Example:

```python
commands = [
    "prepare_test_environment",
    "configure_v2x",
    "reboot",
    "verify_system_after_reboot",
    "execute_v2x_test",
]
```

The framework handles the shell lifecycle automatically.

```text
Configure
   |
   v
Reboot ECU
   |
   v
Shell terminates
   |
   v
Automatic reconnect
   |
   v
Continue test
```

This significantly improves robustness for long-running ECU test sequences.

---

# 📦 Batch Command Execution

The framework provides `run_batch()` for executing multiple commands sequentially.

```python
commands = [
    "command_1",
    ("command_2", 3),
    "command_3",
]

shell.run_batch(commands)
```

The tuple format allows an individual delay to be specified.

```text
command_1
    |
    v
command_2
    |
    v
Wait 3 seconds
    |
    v
command_3
```

This is useful when ECU services require time to:

* Start
* Stop
* Restart
* Initialize
* Apply configuration
* Process V2X operations

---

# 📁 File Management

The framework provides an `ADBFileManager` abstraction for file transfer between the host and ECU.

Supported operations include:

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

This eliminates repetitive manual file-copy operations during test preparation.

---

# 📝 Logging

The framework provides centralized logging through `ADBLogger`.

Example APIs:

```python
logger.log("Starting V2X test")

logger.log_warn(
    "Expected response was not received"
)

logger.log_error(
    "Test execution failed"
)
```

Logging is used for:

* Test execution steps
* ECU commands
* Command output
* Setup operations
* Warnings
* Errors
* Test completion
* Debugging information

---

# 🧪 Test Lifecycle

The framework provides a common `TestBase` abstraction so that individual tests follow a consistent execution lifecycle.

```text
                Test Start
                    |
                    v
          Determine ECU Mode
                    |
                    v
          Prepare Environment
                    |
                    v
           Test-Specific Setup
                    |
                    v
             Start Logging
                    |
                    v
            Execute Commands
                    |
                    v
           Capture Test Logs
                    |
                    v
         Post-Test Verification
                    |
                    v
          Generate Test Result
                    |
                    v
            Cleanup Environment
                    |
                    v
                Test End
```

Individual test implementations can override test-specific setup, execution, and cleanup logic while reusing the common infrastructure.

---

# 🖥️ Master / SOP Mode Handling

The framework automatically determines the ECU software execution mode.

The software version is checked using the ECU environment.

Based on the detected configuration, the framework supports different execution paths for:

```text
MASTER
SOP
```

For example, Master execution may use:

```bash
sldd <command>
```

while SOP execution may use:

```bash
/log/sldd <command>
```

The framework can automatically prepare the SOP environment by:

* Transferring required files
* Configuring execution permissions
* Remounting required locations
* Preparing binaries
* Adapting command paths

This allows the same test logic to operate across different ECU software configurations.

---

# 🧩 Helper Utilities

Common ECU operations are implemented as reusable helper functions rather than being duplicated inside every test.

Examples include functions for:

```text
Certificate presence checks
V2X stack status checks
Stack activation
ECU/product identification
Binary type detection
Region detection
Cybersecurity configuration
Map-matching configuration
Geofencing configuration
SOP prerequisite setup
```

This improves:

* Code reuse
* Maintainability
* Test development speed
* Consistency
* Readability

---

# 🧪 Supported Test Areas

The framework is structured around independent test modules.

Examples include:

```text
V2X
Diagnostics
DTC
Cybersecurity
Certificate Download
Geofencing
Map Matching
Object Forwarding
Coding / Provisioning
Basic Sanity
```

The test runner maintains a centralized registry that maps test names to their corresponding implementations.

Conceptually:

```text
                     Test Runner
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
       V2X         Diagnostics      Cybersecurity
        |                |                |
        +----------------+----------------+
                         |
              +----------+----------+
              |          |          |
              v          v          v
        Geofencing  Map Matching  Object Forwarding
              |
              v
       Coding / Provisioning
              |
              v
         Basic Sanity
```

---

# 🚗 V2X Testing

The framework supports automation of V2X-related test scenarios involving V2X message transmission, reception, configuration, and validation.

Typical V2X message types include:

```text
CAM
DENM
BSM
```

Depending on the target configuration, testing can involve:

```text
DSRC
C-V2X
```

The automation framework provides the infrastructure required to execute the corresponding ECU commands and collect evidence from the target system.

---

# 🔐 V2X Cybersecurity Testing

The framework also supports V2X cybersecurity-related test automation.

The cybersecurity test workflow can include:

```text
Prepare security test environment
             |
             v
Transfer required test files
             |
             v
Configure ECU
             |
             v
Prepare certificates / test data
             |
             v
Execute security scenario
             |
             v
Capture DLT / console logs
             |
             v
Verify expected behavior
             |
             v
Generate test result
```

The framework can support region-specific configurations where required by the test environment.

---

# 📡 DLT Logging

DLT logs are collected during test execution for ECU-side analysis.

The overall workflow is:

```text
Test Execution
      |
      v
DLT Capture
      |
      v
DLT Log File
      |
      v
DLT Processing
      |
      v
CSV / Structured Data
      |
      v
Verification
```

This provides test evidence for validating ECU behavior.

---

# 📊 Automated Reporting

After test execution and verification, the framework generates a consolidated test report.

A typical report can contain:

| Test Case           | Expected Result              | Actual Result        | Status |
| ------------------- | ---------------------------- | -------------------- | ------ |
| V2X Communication   | Message transmitted/received | Message received     | PASS   |
| Security Validation | Invalid message rejected     | Message rejected     | PASS   |
| Certificate Test    | Certificate accepted         | Certificate accepted | PASS   |
| Geofencing          | Event generated              | Event generated      | PASS   |

Automated reporting eliminates the need to manually consolidate test results after execution.

---

# 🔄 End-to-End Automation Flow

The complete framework can be summarized as:

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
| Detect ECU Version   |
+----------+-----------+
           |
           v
+----------------------+
| Master / SOP ?       |
+-----+------------+---+
      |            |
   MASTER          SOP
      |            |
      |      +-----v------+
      |      | Prepare    |
      |      | SOP Env.   |
      |      +-----+------+
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
| Execute Test         |
+----------+-----------+
           |
           v
+----------------------+
| Collect Logs         |
+----------+-----------+
           |
           v
+----------------------+
| Post-Test Verification|
+----------+-----------+
           |
           v
+----------------------+
| DLT → CSV Processing |
+----------+-----------+
           |
           v
+----------------------+
| Generate Report      |
+----------+-----------+
           |
           v
+----------------------+
| Pass / Fail Result   |
+----------------------+
```

---

# 🧱 Framework Design

The framework follows a modular architecture.

```text
                         TestBase
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
       V2X Test       Diagnostics Test   Security Test
          |                 |                 |
          +-----------------+-----------------+
                            |
                     Common Framework
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
      ADBShell         FileManager         Logger
          |
          v
     Linux ECU
```

The separation between test logic and infrastructure provides:

* Reusability
* Maintainability
* Reduced code duplication
* Consistent execution
* Easier debugging
* Faster development of new tests

---

# ➕ Adding a New Test

New tests can inherit from the common `TestBase`.

Example:

```python
from test_base import TestBase


class MyV2XTest(TestBase):

    def get_commands(self):
        return [
            "command to execute1",
            ("command to execute2", 3),
            "command to execute3",
        ]

    def setup_custom(self):
        # Test-specific setup
        pass

    def teardown_custom(self):
        # Test-specific cleanup
        pass
```

The test can then be registered with the test runner.

Conceptually:

```python
TEST_REGISTRY = {
    "my_test": {
        "class": MyV2XTest,
        "display": "My V2X Test",
        "log": "../logs/my_v2x_test.log"
    }
}
```

The test can then be executed through the common runner.

---

# 🛠️ Technology Stack

## Programming

```text
Python
Object-Oriented Programming
Multithreading
Subprocess / Process Management
```

## Embedded / Automotive

```text
V2X
Linux-based Automotive ECU
ECU Diagnostics
DLT
GNSS
DSRC
C-V2X
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

# 🔍 Engineering Concepts Demonstrated

This project demonstrates practical experience with:

### Python

* Object-oriented design
* Classes and inheritance
* Exception handling
* Multithreading
* Queues
* UUID generation
* Regular expressions
* File handling
* Subprocess management

### Linux

* Linux shell interaction
* Process management
* stdin/stdout communication
* File permissions
* Mount configuration
* Service management
* SSH-based debugging
* Embedded Linux environments

### Embedded Systems

* Automotive ECU interaction
* ECU reboot handling
* Firmware/software configuration
* Binary deployment
* Test environment preparation
* Runtime debugging

### Automation

* Test orchestration
* Reusable test infrastructure
* Automated log collection
* Automated verification
* Test reporting
* CI integration

---

# 📈 Before vs After Automation

## Manual Workflow

```text
Manual ECU Connection
        ↓
Manual File Transfer
        ↓
Manual Environment Setup
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

## Automated Workflow

```text
                Test Runner
                    ↓
        Automated ECU Connection
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

### Result

```text
Manual execution:
~3 hours

Automated execution:
<90 minutes
```

This represents a significant reduction in repetitive test execution effort.

---

# 🧪 Example Command Execution

A test developer does not need to manage the underlying ADB process directly.

Instead:

```python
output = shell.run(
    "command to execute"
)
```

The framework internally handles:

```text
Shell Health Check
        ↓
Automatic Reconnect if Required
        ↓
Sentinel Generation
        ↓
Command Transmission
        ↓
Asynchronous Output Reading
        ↓
Completion Detection
        ↓
Output Cleanup
        ↓
Logging
        ↓
Return Output
```

This abstraction keeps individual test cases simple and focused on test behavior.

---

# 🧹 Resource Cleanup

The framework provides a `close()` method for gracefully terminating the persistent shell.

Conceptually:

```python
shell.close()
```

The method:

* Sends the shell exit command
* Terminates the process
* Handles cleanup exceptions
* Records shell shutdown in the logger

This prevents unnecessary processes from remaining after test execution.

---

# 🔒 Security and Confidentiality

This repository is intended to demonstrate the automation architecture and engineering concepts.

If the framework is based on proprietary automotive software, the following should **not** be committed to a public repository:

* Private keys
* Production certificates
* ECU credentials
* Internal IP addresses
* Proprietary binaries
* Internal source code
* Company-specific configuration files
* Customer information
* Internal infrastructure details
* Proprietary V2X test data

For public demonstrations, replace proprietary components with mock or synthetic data.

---

# 📌 Project Highlights

The project demonstrates the design and development of an end-to-end automotive test automation framework with:

```text
             Python Automation
                    |
       +------------+------------+
       |            |            |
       v            v            v
   ECU Control   File Mgmt     Logging
       |            |            |
       +------------+------------+
                    |
                    v
             Test Execution
                    |
                    v
             DLT Collection
                    |
                    v
              Verification
                    |
                    v
              Test Reporting
```

The most significant engineering component is the persistent ADB shell abstraction, which combines:

* Persistent subprocess management
* Asynchronous stdout processing
* Thread-safe queues
* Sentinel-based command completion
* Timeout protection
* Prompt-based fallback
* Automatic shell reconnection
* ECU reboot recovery

This provides a reliable communication foundation for the higher-level V2X test automation framework.

---

# 🚀 Future Improvements

Potential future enhancements include:

* Parallel multi-ECU test execution
* Pytest integration
* JUnit XML reporting
* HTML test reports
* Test result dashboards
* More comprehensive CI/CD integration
* Automatic test retry policies
* Enhanced log correlation
* Centralized test configuration
* YAML/JSON-based test definitions
* REST/API-based test triggering
* Containerized execution environment
* Automated test result publishing

---

# 📄 License

Add the appropriate license here if this repository contains code that you are permitted to distribute.

Example:

```text
MIT License
```

If the framework contains proprietary code, do not publish the source without authorization.

---

# 👨‍💻 Project Summary

**V2X Test Execution Automation Framework** is a Python-based embedded automotive test automation framework designed to automate V2X ECU testing from environment preparation through final reporting.

The framework combines:

```text
ECU Communication
        +
Persistent Shell Execution
        +
Environment Automation
        +
V2X Test Execution
        +
DLT Logging
        +
Result Verification
        +
Automated Reporting
```

The result is a reusable automation infrastructure that reduces manual effort, improves test consistency, and allows engineers to focus on test scenarios rather than repetitive ECU setup and execution activities.

```


# How to Use ?
- Run the `setup.bat` it will setup necessary libraries, dependencies and install python if not already installed.

