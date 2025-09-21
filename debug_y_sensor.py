#!/usr/bin/env python3
"""
Debug Y-axis sensor readings to identify delay issues
Shows raw voltages without any filtering or validation
"""

import sys
import time
import yaml
from pathlib import Path

# Attempt to import hardware libraries
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    HARDWARE_AVAILABLE = True
    print("✅ Hardware libraries loaded successfully")
except ImportError:
    print("⚠️  Hardware libraries not available - simulation mode")
    HARDWARE_AVAILABLE = False


class RawSensorDebugger:
    """Raw sensor debugging without any filtering"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        if HARDWARE_AVAILABLE:
            # Initialize ADS1115
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS.ADS1115(i2c, address=self.config['hardware']['ads1115']['address'])
                self.ads.gain = self.config['hardware']['ads1115']['gain']
                
                # Setup analog inputs
                self.x_analog = AnalogIn(self.ads, ADS.P0)  # X-axis on A0
                self.y_analog = AnalogIn(self.ads, ADS.P2)  # Y-axis on A2
                
                print("✅ ADS1115 initialized successfully")
                print(f"📊 X-axis: Channel 0 (A0)")
                print(f"📊 Y-axis: Channel 2 (A2)")
                
            except Exception as e:
                print(f"❌ Error initializing ADS1115: {e}")
                sys.exit(1)
        else:
            print("❌ Hardware not available - cannot debug sensors")
            sys.exit(1)
    
    def read_raw_voltages(self):
        """Read raw voltages without any processing"""
        try:
            x_voltage = self.x_analog.voltage
            y_voltage = self.y_analog.voltage
            return x_voltage, y_voltage
        except Exception as e:
            print(f"❌ Error reading voltages: {e}")
            return None, None
    
    def run_debug_loop(self):
        """Run continuous debug loop"""
        print("\n" + "="*80)
        print("🔍 RAW SENSOR DEBUG - Y-AXIS DELAY INVESTIGATION")
        print("="*80)
        print("This shows RAW voltages with NO filtering or validation")
        print("Move Y-axis and watch for immediate voltage changes")
        print("Press Ctrl+C to stop")
        print("="*80)
        
        last_y_voltage = None
        change_detected = False
        no_change_count = 0
        
        try:
            while True:
                x_voltage, y_voltage = self.read_raw_voltages()
                
                if x_voltage is not None and y_voltage is not None:
                    # Track Y-axis changes
                    if last_y_voltage is not None:
                        y_change = abs(y_voltage - last_y_voltage)
                        if y_change > 0.01:  # 10mV change threshold
                            if not change_detected:
                                print(f"\n🔥 Y CHANGE DETECTED! {last_y_voltage:.4f}V → {y_voltage:.4f}V (Δ{y_change:.4f}V)")
                                change_detected = True
                                no_change_count = 0
                        else:
                            if change_detected:
                                no_change_count += 1
                                if no_change_count > 10:  # Reset after 2 seconds of stability
                                    change_detected = False
                                    no_change_count = 0
                    
                    # Display current readings
                    y_status = "🔥 CHANGING" if change_detected else "■ STABLE"
                    print(f"\r📊 X={x_voltage:6.4f}V | Y={y_voltage:6.4f}V {y_status}     ", end="", flush=True)
                    
                    last_y_voltage = y_voltage
                
                time.sleep(0.1)  # 10Hz update rate
                
        except KeyboardInterrupt:
            print("\n\n✅ Debug session ended")


def main():
    print("🚀 Y-Axis Sensor Debug Tool")
    print("This tool shows raw sensor readings to debug delay issues")
    
    debugger = RawSensorDebugger()
    debugger.run_debug_loop()


if __name__ == "__main__":
    main()
