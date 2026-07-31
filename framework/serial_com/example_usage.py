#!/usr/bin/env python3
"""
ECU Serial Communication - Example Usage Scripts

This file demonstrates various ways to use the ECUInterface class
for communicating with ECUs over UART/Serial.

Usage: python example_usage.py
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from serial_com.bam import ECUInterface


def example_1_basic_communication():
    """
    Example 1: Basic command execution and response
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Communication")
    print("=" * 70)
    
    ecu = ECUInterface(port="COM43", baudrate=1000000)
    
    try:
        ecu.connect()
        ecu.start_monitor()
        time.sleep(0.5)
        
        # Send a command
        response = ecu.send_cmd("uname -a", timeout=5)
        if response:
            print(f"✓ Command executed successfully")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ecu.close()


def example_2_multiple_commands():
    """
    Example 2: Execute multiple commands sequentially
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Multiple Commands")
    print("=" * 70)
    
    ecu = ECUInterface(port="COM43", baudrate=1000000)
    
    try:
        ecu.connect()
        ecu.start_monitor()
        time.sleep(0.5)
        
        commands = [
            "cat /etc/os-release",
            "uname -a",
            "ps aux",
            "df -h"
        ]
        
        for cmd in commands:
            response = ecu.send_cmd(cmd, timeout=10)
            time.sleep(0.5)
            
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ecu.close()


def example_3_v2x_specific():
    """
    Example 3: V2X-specific commands (automotive testing)
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: V2X-Specific Commands")
    print("=" * 70)
    
    ecu = ECUInterface(port="COM43", baudrate=1000000)
    
    try:
        ecu.connect()
        ecu.start_monitor()
        time.sleep(0.5)
        
        # V2X specific commands
        v2x_commands = [
            "cat /etc/its.json",           # Get V2X configuration
            "systemctl status",            # Check services
            "dmesg | tail -20",            # Kernel messages
        ]
        
        for cmd in v2x_commands:
            print(f"\n[*] Executing: {cmd}")
            response = ecu.send_cmd(cmd, timeout=10)
            time.sleep(0.5)
            
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ecu.close()


def example_4_continuous_monitoring():
    """
    Example 4: Start monitoring and keep script alive
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Continuous Monitoring")
    print("=" * 70)
    print("Monitoring logs... Press Ctrl+C to exit\n")
    
    ecu = ECUInterface(port="COM43", baudrate=1000000)
    
    try:
        ecu.connect()
        ecu.start_monitor()
        
        # Keep running for monitoring
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[*] Stopping monitoring...")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ecu.close()


def example_5_error_handling():
    """
    Example 5: Proper error handling and retry logic
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Error Handling & Retry")
    print("=" * 70)
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            ecu = ECUInterface(port="COM43", baudrate=1000000)
            ecu.connect()
            ecu.start_monitor()
            time.sleep(0.5)
            
            response = ecu.send_cmd("uname -a", timeout=5)
            print(f"✓ Success on attempt {attempt + 1}")
            break
            
        except TimeoutError as e:
            print(f"✗ Attempt {attempt + 1}: Timeout - {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                
        except Exception as e:
            print(f"✗ Attempt {attempt + 1}: Error - {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
        finally:
            try:
                ecu.close()
            except:
                pass


def example_6_large_response():
    """
    Example 6: Handling commands with large multiline responses
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Large Multiline Responses")
    print("=" * 70)
    
    ecu = ECUInterface(port="COM43", baudrate=1000000)
    
    try:
        ecu.connect()
        ecu.start_monitor()
        time.sleep(0.5)
        
        # Commands with large output
        large_commands = [
            ("dmesg | tail -50", 15),        # Kernel messages with longer timeout
            ("cat /proc/meminfo", 10),       # Memory info
            ("ls -la /", 10),                # Directory listing
        ]
        
        for cmd, timeout in large_commands:
            print(f"\n[*] Executing: {cmd} (timeout: {timeout}s)")
            response = ecu.send_cmd(cmd, timeout=timeout)
            
            if response:
                lines = response.split('\n')
                print(f"    Got {len(lines)} lines")
            
            time.sleep(1)
            
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ecu.close()


def example_7_connection_status():
    """
    Example 7: Check connection status and reconnect
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Connection Status")
    print("=" * 70)
    
    ecu = ECUInterface(port="COM43", baudrate=1000000)
    
    try:
        ecu.connect()
        
        print(f"Connected: {ecu.is_connected()}")
        
        # Do something
        ecu.start_monitor()
        time.sleep(1)
        
        # Check again
        print(f"Still connected: {ecu.is_connected()}")
        
        # Force reconnect
        print("Forcing reconnect...")
        ecu.reconnect()
        print(f"Reconnected: {ecu.is_connected()}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ecu.close()


# =====================================================================
# Menu
# =====================================================================

def main():
    """
    Interactive menu for examples
    """
    examples = {
        '1': ('Basic Communication', example_1_basic_communication),
        '2': ('Multiple Commands', example_2_multiple_commands),
        '3': ('V2X-Specific Commands', example_3_v2x_specific),
        '4': ('Continuous Monitoring', example_4_continuous_monitoring),
        '5': ('Error Handling & Retry', example_5_error_handling),
        '6': ('Large Multiline Responses', example_6_large_response),
        '7': ('Connection Status', example_7_connection_status),
        'A': ('Run All Examples', None),
        'Q': ('Quit', None),
    }
    
    while True:
        print("\n" + "=" * 70)
        print("ECU Serial Communication - Examples")
        print("=" * 70)
        
        for key, (desc, _) in examples.items():
            print(f"  {key}: {desc}")
        
        choice = input("\nSelect example (1-7, A for all, Q to quit): ").strip().upper()
        
        if choice == 'Q':
            print("Exiting...")
            break
        elif choice == 'A':
            for key in '1234567':
                try:
                    examples[key][1]()
                except Exception as e:
                    print(f"Error in {examples[key][0]}: {e}")
                time.sleep(1)
        elif choice in examples and examples[choice][1]:
            try:
                examples[choice][1]()
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("Invalid choice!")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ECU Serial Communication Interface - Example Usage")
    print("=" * 70)
    
    # Verify pyserial is installed
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed!")
        print("Install with: pip install -r requirements.txt")
        sys.exit(1)
    
    # Run menu or direct example
    import sys
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num == '1':
            example_1_basic_communication()
        elif example_num == '2':
            example_2_multiple_commands()
        elif example_num == '3':
            example_3_v2x_specific()
        elif example_num == '4':
            example_4_continuous_monitoring()
        elif example_num == '5':
            example_5_error_handling()
        elif example_num == '6':
            example_6_large_response()
        elif example_num == '7':
            example_7_connection_status()
        else:
            print(f"Unknown example: {example_num}")
    else:
        main()
