from bam import ECUSerialCom
import time
if __name__ == "__main__":

    ecu = ECUSerialCom(
        port="COM43",
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
