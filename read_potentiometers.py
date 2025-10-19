#!/usr/bin/env python3
"""
Live Potentiometer Reader - Continuously read and display potentiometer values
Shows real-time voltage and position readings from both X and Y axes
"""

import time
import sys
import signal
import yaml
from typing import Optional

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
except ImportError as e:
    print(f"Hardware libraries not available: {e}")
    print("Running in simulation mode...")
    board = None
    busio = None
    ADS = None
    AnalogIn = None


class LivePotentiometerReader:
    """Live potentiometer reader with real-time display"""
    
    def __init__(self):
        self.running = False
        self.ads = None
        self.x_channel = None
        self.y_channel = None
        
        # Load configuration from config.yaml
        self.load_config()
        self.init_hardware()
    
    def load_config(self):
        """Load voltage ranges from config.yaml"""
        try:
            with open('config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            x_cal = config['hardware']['calibration']['x_axis']
            y_cal = config['hardware']['calibration']['y_axis']
            
            self.x_config = {
                'channel': config['hardware']['potentiometer']['x_axis_channel'],
                'min_voltage': x_cal['min_voltage'],
                'max_voltage': x_cal['max_voltage'],
                'label': 'X-AXIS'
            }
            
            self.y_config = {
                'channel': config['hardware']['potentiometer']['y_axis_channel'],
                'min_voltage': y_cal['min_voltage'],
                'max_voltage': y_cal['max_voltage'],
                'label': 'Y-AXIS'
            }
            
            print(f"✅ Config loaded - X: {self.x_config['min_voltage']:.3f}V-{self.x_config['max_voltage']:.3f}V, Y: {self.y_config['min_voltage']:.3f}V-{self.y_config['max_voltage']:.3f}V")
            
        except Exception as e:
            print(f"❌ Error loading config.yaml: {e}")
            print("Using fallback values...")
            # Fallback to current values if config loading fails
            self.x_config = {
                'channel': 0,
                'min_voltage': 1.670,
                'max_voltage': 2.884,
                'label': 'X-AXIS'
            }
            
            self.y_config = {
                'channel': 2, 
                'min_voltage': 0.821,
                'max_voltage': 3.017,
                'label': 'Y-AXIS'
            }
    
    def init_hardware(self):
        """Initialize ADS1115 and analog channels"""
        if not (board and busio and ADS and AnalogIn):
            print("⚠️  Hardware libraries not available - simulation mode")
            return
        
        try:
            # Initialize I2C and ADS1115
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c, address=0x48)
            self.ads.gain = 1  # ±4.096V range
            self.ads.data_rate = 128  # Samples per second (faster now that cross-talk is eliminated)
            
            # Initialize analog input channels
            self.x_channel = AnalogIn(self.ads, getattr(ADS, f'P{self.x_config["channel"]}'))  # X-axis from config
            self.y_channel = AnalogIn(self.ads, getattr(ADS, f'P{self.y_config["channel"]}'))  # Y-axis from config
            
            print("✅ ADS1115 initialized successfully")
            print(f"   X-axis: Channel {self.x_config['channel']} (A{self.x_config['channel']})")
            print(f"   Y-axis: Channel {self.y_config['channel']} (A{self.y_config['channel']})")
            
        except Exception as e:
            print(f"❌ Failed to initialize ADS1115: {e}")
            self.ads = None
    
    def read_voltage(self, channel_config: dict) -> Optional[float]:
        """Read voltage from specified channel"""
        if not self.ads:
            # Simulation mode
            import random
            return random.uniform(channel_config['min_voltage'], channel_config['max_voltage'])
        
        try:
            if channel_config['channel'] == 0:
                voltage = self.x_channel.voltage
            elif channel_config['channel'] == 2:
                voltage = self.y_channel.voltage
            else:
                return None
            
            return voltage
            
        except Exception as e:
            print(f"\n❌ Error reading {channel_config['label']}: {e}")
            return None
    
    def voltage_to_position(self, voltage: float, channel_config: dict) -> float:
        """Convert voltage to position percentage"""
        if voltage is None:
            return 0.0
        
        # Clamp voltage to valid range
        voltage = max(channel_config['min_voltage'], min(channel_config['max_voltage'], voltage))
        
        # Convert to percentage
        voltage_range = channel_config['max_voltage'] - channel_config['min_voltage']
        percent = ((voltage - channel_config['min_voltage']) / voltage_range) * 100.0
        
        return max(0.0, min(100.0, percent))
    
    def display_readings(self):
        """Display current readings in a formatted way"""
        x_voltage = self.read_voltage(self.x_config)
        y_voltage = self.read_voltage(self.y_config)
        
        # Handle None values
        if x_voltage is None:
            x_voltage = 0.0
        if y_voltage is None:
            y_voltage = 0.0
        
        x_position = self.voltage_to_position(x_voltage, self.x_config)
        y_position = self.voltage_to_position(y_voltage, self.y_config)
        
        # Clear line and display readings
        print(f"\r🔍 LIVE: X={x_position:6.1f}% ({x_voltage:5.3f}V) | Y={y_position:6.1f}% ({y_voltage:5.3f}V) | Press Ctrl+C to stop", end="", flush=True)
        
        return x_voltage, y_voltage, x_position, y_position
    
    def run_live_display(self, update_interval: float = 0.2):
        """Run live display loop"""
        print("🚀 Live Potentiometer Reader")
        print("=" * 50)
        print("Displays real-time voltage and position readings")
        print("Move the TV arm manually to see values change")
        print()
        
        if not self.ads:
            print("Running in simulation mode with random values")
        
        print("📊 Live Readings:")
        print()
        
        self.running = True
        
        try:
            while self.running:
                self.display_readings()
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped by user")
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
        finally:
            self.running = False
            print("🧹 Reader stopped")
    
    def run_single_reading(self):
        """Take a single reading and display"""
        print("📖 Single Potentiometer Reading:")
        print("-" * 40)
        
        x_voltage, y_voltage, x_position, y_position = self.display_readings()
        
        print(f"\nX-AXIS: {x_position:.1f}% ({x_voltage:.3f}V)")
        print(f"Y-AXIS: {y_position:.1f}% ({y_voltage:.3f}V)")
        
        # Show distance from preset positions
        wall_x, wall_y = 96.9, 23.1
        ext_x, ext_y = 62.3, 88.7
        
        wall_dist = abs(x_position - wall_x) + abs(y_position - wall_y)
        ext_dist = abs(x_position - ext_x) + abs(y_position - ext_y)
        
        print(f"\nDistance from WALL (96.9%, 23.1%): {wall_dist:.1f}%")
        print(f"Distance from EXTENDED (62.3%, 88.7%): {ext_dist:.1f}%")
        
        if wall_dist < ext_dist:
            print("🏠 Closer to WALL position")
        else:
            print("📏 Closer to EXTENDED position")


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n⏹️  Stopping...")
    sys.exit(0)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Live Potentiometer Reader')
    parser.add_argument('--live', action='store_true', 
                       help='Run live continuous display (default)')
    parser.add_argument('--single', action='store_true',
                       help='Take a single reading and exit')
    parser.add_argument('--interval', type=float, default=0.2,
                       help='Update interval for live mode (seconds)')
    
    args = parser.parse_args()
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    reader = LivePotentiometerReader()
    
    if args.single:
        reader.run_single_reading()
    else:
        reader.run_live_display(args.interval)


if __name__ == "__main__":
    main()
