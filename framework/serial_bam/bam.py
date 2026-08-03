import serial
import threading
import time
import logging
import os
from datetime import datetime
from queue import Queue, Empty
from pathlib import Path


# =====================================================
# Configure Logging with Colors
# =====================================================
class Colors:
    """ANSI color codes for console output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class DualLogger:
    """
    Dual logger that writes to both console and file
    """
    
    def __init__(self, log_file=None):
        # Create logs directory if not specified
        if log_file is None:
            logs_dir = Path(__file__).parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)
            log_file = logs_dir / "ecu_communication.log"
        else:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.log_file = str(log_file)
        self.logger = logging.getLogger("ECUSerialCom")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler with UTF-8 encoding
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.stream.reconfigure(encoding='utf-8')
        
        # Format
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S"
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, msg):
        self.logger.info(msg)
    
    def error(self, msg):
        self.logger.error(msg)
    
    def warning(self, msg):
        self.logger.warning(msg)
    
    def debug(self, msg):
        self.logger.debug(msg)
    
    def print_red(self, msg):
        """Print message in red color and log to file"""
        print(f"{Colors.RED}{msg}{Colors.RESET}")
        self.logger.error(msg)
    
    def print_green(self, msg):
        """Print message in green color and log to file"""
        print(f"{Colors.GREEN}{msg}{Colors.RESET}")
        self.logger.info(msg)
    
    def print_yellow(self, msg):
        """Print message in yellow color and log to file"""
        print(f"{Colors.YELLOW}{msg}{Colors.RESET}")
        self.logger.warning(msg)
    
    def print_blue(self, msg):
        """Print message in blue color and log to file"""
        print(f"{Colors.BLUE}{msg}{Colors.RESET}")
        self.logger.info(msg)


class ECUSerialCom:
    """
    Production-quality ECU communication interface over UART/Serial
    
    Features:
    - Thread-safe command/response handling
    - Continuous background log monitoring
    - Auto-reconnect on disconnection
    - Configurable timeouts
    - File logging
    - Graceful shutdown
    """

    def __init__(self, port="COM40", baudrate=1000000, log_file="ecu_communication.log", print_console_output=True):
        """
        Initialize ECU interface
        
        Args:
            port (str): Serial port (e.g., "COM43")
            baudrate (int): Baud rate (default 1000000)
            log_file (str): Log file path
            print_console_output (bool): Print command output to console (default True)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.monitor_thread = None
        self.stop_monitor = False
        self.last_command = ""
        self.print_console_output = print_console_output
        
        # Thread synchronization
        self.ser_lock = threading.Lock()
        
        # Response queue for command handling
        # Monitor thread puts data here, send_cmd reads from here
        self.response_queue = Queue()
        
        # Logger setup
        self.logger = DualLogger(log_file)
        
        self.logger.info("=" * 60)
        self.logger.info("ECU Interface Initialized")
        self.logger.info(f"Port: {self.port}, Baudrate: {self.baudrate}")
        self.logger.info(f"Console Output: {'Enabled' if self.print_console_output else 'Disabled'}")
        self.logger.info("=" * 60)

    # -------------------------------------------------
    # Connect to ECU with retry logic
    # -------------------------------------------------
    def connect(self):
        """
        Connect to ECU with automatic retry on failure
        """
        retry_count = 0
        max_retries = 5
        retry_delay = 2
        
        while not self.connected and retry_count < max_retries:
            try:
                self.logger.info(f"Connecting to {self.port}... (Attempt {retry_count + 1}/{max_retries})")
                
                with self.ser_lock:
                    self.ser = serial.Serial(
                        port=self.port,
                        baudrate=self.baudrate,
                        timeout=0.5,  # Non-blocking read
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        xonxoff=False,  # No flow control
                        rtscts=False
                    )
                    
                    # Clear any existing data in buffers
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                
                self.connected = True
                self.logger.info("[OK] ECU Connected Successfully")
                return True

            except serial.SerialException as e:
                retry_count += 1
                self.logger.warning(f"Connection failed: {e}")
                
                if retry_count < max_retries:
                    self.logger.print_yellow(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self.logger.print_red(f"Failed to connect after {max_retries} attempts")
                    raise

    # -------------------------------------------------
    # Reconnect if ECU disconnects/reboots
    # -------------------------------------------------
    def reconnect(self):
        """
        Perform reconnection after disconnection or timeout
        """
        self.logger.print_yellow("Attempting reconnection...")
        self.connected = False
        
        try:
            with self.ser_lock:
                if self.ser:
                    self.ser.close()
        except:
            pass
        
        time.sleep(1)
        self.connect()

    # -------------------------------------------------
    # Monitor log thread - continuously reads from serial
    # -------------------------------------------------
    def monitor_logs(self):
        """
        Background thread that continuously reads data from serial port
        and queues it for response handling. This separates data reading
        from command execution preventing race conditions.
        """
        consecutive_errors = 0
        max_errors = 3
        
        while not self.stop_monitor:
            try:
                with self.ser_lock:
                    if self.ser and self.ser.is_open:
                        if self.ser.in_waiting:
                            # Read available data
                            data = self.ser.read(self.ser.in_waiting).decode(
                                errors="ignore"
            )
                            
                            if data:
                                # Queue the data for processing
                                self.response_queue.put(data)
                                
                                # Print output to console if enabled
                                if self.print_console_output:
                                    for line in data.split('\n'):
                                        if line.strip():
                                            print(line)
                                
                                consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                
                time.sleep(0.05)
                
            except (serial.SerialException, OSError) as e:
                consecutive_errors += 1
                self.logger.print_red(f"Monitor read error: {e}")
                
                if consecutive_errors >= max_errors:
                    self.logger.print_red(f"Too many consecutive errors, reconnecting...")
                    self.reconnect()
                    consecutive_errors = 0
                else:
                    time.sleep(0.1)

    # -------------------------------------------------
    # Send command to ECU
    # -------------------------------------------------
    def send_cmd(self, cmd, timeout=5):
        """
        Send command to ECU and wait for response.
        
        Uses queue-based response handling to avoid race conditions
        between monitor thread and command execution.
        
        Args:
            cmd (str): Command to send
            timeout (float): Response timeout in seconds
            
        Returns:
            str: Response from ECU or None on failure
        """
        if not self.connected:
            self.connect()
        
        try:
            # Clear response queue before sending command
            while not self.response_queue.empty():
                self.response_queue.get_nowait()
            
            # Send command with newline
            full_cmd = cmd + "\n"
            
            with self.ser_lock:
                self.ser.reset_input_buffer()
                self.ser.write(full_cmd.encode())
            
            self.last_command = cmd
            
            # Collect response with timeout
            response = self._collect_response(cmd, timeout)
            
            if response:
                return response
            else:
                self.logger.print_red(f"No response received")
                return None

        except (serial.SerialException, OSError) as e:
            self.logger.print_red(f"Serial error: {e}")
            self.reconnect()
            return None

    # -------------------------------------------------
    # Collect response from queue with timeout
    # -------------------------------------------------
    def _collect_response(self, cmd, timeout=5):
        """
        Collect response data from the queue with timeout.
        Handles multiline responses and waits for completion.
        
        Args:
            cmd (str): Command that was sent
            timeout (float): Response timeout
            
        Returns:
            str: Collected response
        """
        start_time = time.time()
        response = ""
        quiet_iterations = 0
        max_quiet_iterations = 5  # Iterations with no data before considering response complete
        
        while time.time() - start_time < timeout:
            try:
                # Try to get data from queue with small timeout
                data = self.response_queue.get(timeout=0.2)
                response += data
                quiet_iterations = 0  # Reset counter when data arrives
                
            except Empty:
                quiet_iterations += 1
                
                # If we have response and haven't heard for a while, response is complete
                if response and quiet_iterations >= max_quiet_iterations:
                    return response.strip()
            
            time.sleep(0.05)
        
        # Timeout reached
        if response:
            return response.strip()
        else:
            raise TimeoutError(
                f"Timeout waiting for response for command: {cmd} (waited {timeout}s)"
            )

    # -------------------------------------------------
    # Start monitor thread
    # -------------------------------------------------
    def start_monitor(self):
        """
        Start background monitoring thread
        """
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.stop_monitor = False
            self.monitor_thread = threading.Thread(
                target=self.monitor_logs,
                daemon=True,
                name="ECU-Monitor"
            )
            self.monitor_thread.start()
            self.logger.info("Monitor thread started")

    # -------------------------------------------------
    # Stop monitor thread
    # -------------------------------------------------
    def stop_monitoring(self):
        """
        Stop background monitoring thread
        """
        self.stop_monitor = True
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            self.logger.info("Monitor thread stopped")

    # -------------------------------------------------
    # Check connection status
    # -------------------------------------------------
    def is_connected(self):
        """
        Check if ECU is connected
        
        Returns:
            bool: Connection status
        """
        with self.ser_lock:
            return self.connected and self.ser and self.ser.is_open

    # -------------------------------------------------
    # Toggle console output
    # -------------------------------------------------
    def set_console_output(self, enable):
        """
        Enable or disable console output for command responses.
        
        Args:
            enable (bool): True to enable console output, False to disable
        """
        self.print_console_output = enable
        status = "Enabled" if enable else "Disabled"
        self.logger.info(f"Console output: {status}")

    def switch_region(self, target_region):
        """
        Switch region between EU and CN.        
        Args:
            target_region (str): 'EU' or 'CN'
        """
        if target_region not in ["EU", "CN"]:
            raise ValueError(f"Invalid region: {target_region}. Must be 'EU' or 'CN'")
        
        if not self.connected:
            self.connect()
        
        base_path = "/var/data/telematics/provisioningd/provisioning-eng/"
        
        try:
            # STEP 1: Verify current region from grep output
            region_output = self.send_cmd(
                f"cd {base_path} && cat provisioning.xml | grep -i stackRegion",
                timeout=5
            )
            
            # Parse current region from XML
            xml_lower = region_output.lower()
            if '<stackregion>eu</stackregion>' in xml_lower or 'stackregion>eu<' in xml_lower:
                current_region = "EU"
            elif '<stackregion>cn</stackregion>' in xml_lower or 'stackregion>cn<' in xml_lower:
                current_region = "CN"
            else:
                current_region = None
            
            # STEP 2: Check if switch is needed
            if current_region == target_region:
                self.logger.print_green(f"Region is already {current_region}")
                return
            
            # STEP 3: Execute region switch
            old_region = current_region
            
            out = self.send_cmd(f"cd {base_path} && ls -l", timeout=5)
            self.logger.print_blue(f"ls -l {base_path}:\n{out}")
            self.send_cmd(f"cd {base_path} && mv provisioning.xml provisioning-{old_region}.xml", timeout=5)
            self.send_cmd(f"cd {base_path} && mv provisioning-{target_region}.xml provisioning.xml", timeout=5)
            self.send_cmd("sync", timeout=5)
            self.send_cmd("sync", timeout=5)
            
            self.logger.print_green(f"Region changed to {target_region}")
            
            # Initiate reboot
            self.reboot_ecu()
            
        except Exception as e:
            self.logger.print_red(f"Region switch failed: {e}")

    # -------------------------------------------------
    # Verify Region (check current provisioning)
    # -------------------------------------------------
    def is_region_eu(self):
        if not self.connected:
            self.connect()
        try:
            base_path = "/var/data/telematics/provisioningd/provisioning-eng/"
            # Step 2: Get actual stackRegion from active provisioning.xml
            region_output = self.send_cmd(
                f"cd {base_path} && cat provisioning.xml | grep -i stackRegion",
                timeout=5
            )
            # Parse current region from XML
            xml_lower = region_output.lower()
            if '<stackregion>eu</stackregion>' in xml_lower or 'stackregion>eu<' in xml_lower:
                current_region = "EU"
            elif '<stackregion>cn</stackregion>' in xml_lower or 'stackregion>cn<' in xml_lower:
                current_region = "CN"
            else:
                current_region = None
            return current_region == "EU"

        except Exception as e:
            return None

    # -------------------------------------------------
    # Reboot ECU (after region switch)
    # -------------------------------------------------
    def reboot_ecu(self, wait_time=30):
        if not self.connected:
            self.connect()
        try:
            result = self.send_cmd("reboot", timeout=2)
            return "reboot_initiated"
        except TimeoutError:
            # Timeout is expected for reboot
            return "reboot_Timeout"
        except Exception as e:
            return "reboot_failed"

    # -------------------------------------------------
    # Close serial connection gracefully
    # -------------------------------------------------
    def close(self):
        """
        Close ECU connection and cleanup
        """
        self.logger.info("Closing ECU connection...")
        self.stop_monitoring()
        
        with self.ser_lock:
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
        
        self.connected = False
        self.logger.info("[OK] ECU connection closed")
        self.logger.info("=" * 60)
    
    def switch_region_bam():

        ecu = ECUSerialCom(
            port="COM40",
            baudrate=1000000
        )
        ecu.set_console_output(False)
        try:
            # Connect to ECU
            ecu.connect()
            
            # Start continuous live logs in background
            ecu.start_monitor()
            
            # Give monitor time to start
            time.sleep(0.5)
            
            print("\n" + "=" * 70)
            print("ECU REGION SWITCHING")
            print("=" * 70)
            
            # ===== OPTION 1: Verify current region =====
            eu_region = ecu.is_region_eu()
            ecu.logger.print_green(f"\nCurrent region: {'EU' if eu_region else 'CN'}")
            # ===== OPTION 2: Switch region to EU =====
            if eu_region:
                ecu.switch_region("CN")
            else:
                ecu.switch_region("EU")
            
            ecu.logger.print_green("\nTask completed successfully")

        except KeyboardInterrupt:
            ecu.logger.print_yellow("\n[INFO] Keyboard interrupt received")

        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")

        finally:
            ecu.close()

