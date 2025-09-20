#!/usr/bin/env python3
"""
TV Arm Controller - Main hardware control module
Handles DC motors with TB6612FNG driver and potentiometer position feedback
"""

import time
import threading
import logging
import signal
import sys
from typing import Tuple, Optional, Any

try:
    import RPi.GPIO as GPIO
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
except ImportError as e:
    print(f"Hardware libraries not available: {e}")
    print("Running in simulation mode...")
    GPIO = None
    board = None
    busio = None
    ADS = None
    AnalogIn = None


class DCMotorController:
    """Controls DC motor using TB6612FNG motor driver"""
    
    def __init__(self, ain1_pin: int, ain2_pin: int, pwm_pin: int, stby_pin: int = None, 
                 frequency: int = 1000, min_position: float = 0.0, max_position: float = 100.0):
        self.ain1_pin = ain1_pin
        self.ain2_pin = ain2_pin  
        self.pwm_pin = pwm_pin
        self.stby_pin = stby_pin
        self.frequency = frequency
        self.min_position = min_position
        self.max_position = max_position
        self.current_position = 50.0  # Start at center
        self.target_position = 50.0
        self.pwm = None
        self.moving = False
        
        if GPIO:
            GPIO.setup(self.ain1_pin, GPIO.OUT)
            GPIO.setup(self.ain2_pin, GPIO.OUT)
            GPIO.setup(self.pwm_pin, GPIO.OUT)
            if self.stby_pin:
                GPIO.setup(self.stby_pin, GPIO.OUT)
                GPIO.output(self.stby_pin, GPIO.HIGH)  # Enable motor driver
            
            self.pwm = GPIO.PWM(self.pwm_pin, self.frequency)
            self.pwm.start(0)
            self.stop_motor()
    
    def set_direction_forward(self):
        """Set motor direction to forward"""
        if GPIO:
            GPIO.output(self.ain1_pin, GPIO.HIGH)
            GPIO.output(self.ain2_pin, GPIO.LOW)
    
    def set_direction_reverse(self):
        """Set motor direction to reverse"""
        if GPIO:
            GPIO.output(self.ain1_pin, GPIO.LOW)
            GPIO.output(self.ain2_pin, GPIO.HIGH)
    
    def stop_motor(self):
        """Stop motor (coast)"""
        if GPIO:
            GPIO.output(self.ain1_pin, GPIO.LOW)
            GPIO.output(self.ain2_pin, GPIO.LOW)
        if self.pwm:
            self.pwm.ChangeDutyCycle(0)
        self.moving = False
    
    def brake_motor(self):
        """Brake motor (short brake)"""
        if GPIO:
            GPIO.output(self.ain1_pin, GPIO.HIGH)
            GPIO.output(self.ain2_pin, GPIO.HIGH)
        if self.pwm:
            self.pwm.ChangeDutyCycle(100)
    
    def set_speed(self, speed: float):
        """Set motor speed (0-100%)"""
        speed = max(0.0, min(100.0, abs(speed)))
        if self.pwm:
            self.pwm.ChangeDutyCycle(speed)
    
    def move_to_position(self, target_percent: float, speed: float = 50.0):
        """Move motor towards target position"""
        target_percent = max(self.min_position, min(self.max_position, target_percent))
        self.target_position = target_percent
        
        # For now, just set direction based on target vs current
        # In a real system, you'd use position feedback to control movement
        if target_percent > self.current_position:
            self.set_direction_forward()
            self.set_speed(speed)
            self.moving = True
            logging.debug(f"DC Motor moving forward to {target_percent:.1f}% at {speed:.1f}% speed")
        elif target_percent < self.current_position:
            self.set_direction_reverse()
            self.set_speed(speed)
            self.moving = True
            logging.debug(f"DC Motor moving reverse to {target_percent:.1f}% at {speed:.1f}% speed")
        else:
            self.stop_motor()
            logging.debug(f"DC Motor already at target position {target_percent:.1f}%")
        
        # Update current position (in real system, this would come from position feedback)
        self.current_position = target_percent
        return True
    
    def set_position_percent(self, percent: float) -> bool:
        """Set motor position as percentage (0-100%)"""
        return self.move_to_position(percent)
    
    def get_current_position(self) -> float:
        """Get current motor position"""
        return self.current_position
    
    def is_moving(self) -> bool:
        """Check if motor is currently moving"""
        return self.moving
    
    def stop(self):
        """Stop motor and cleanup"""
        self.stop_motor()
        if self.pwm:
            self.pwm.stop()


# ServoController kept for backward compatibility (deprecated)
class ServoController:
    """Controls servo motor using PWM (DEPRECATED - use DCMotorController for DC motors)
    
    This class is kept for backward compatibility only. New implementations
    should use DCMotorController for DC motor control with TB6612FNG driver.
    """
    
    def __init__(self, pin: int, frequency: int = 50, min_pulse: float = 1.0, 
                 max_pulse: float = 2.0, min_angle: int = 0, max_angle: int = 180):
        self.pin = pin
        self.frequency = frequency
        self.min_pulse = min_pulse
        self.max_pulse = max_pulse
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.current_angle = 90  # Start at center
        self.pwm = None
        
        if GPIO:
            GPIO.setup(self.pin, GPIO.OUT)
            self.pwm = GPIO.PWM(self.pin, self.frequency)
            self.pwm.start(0)
            self.set_angle(90)  # Center position
    
    def pulse_width_to_duty_cycle(self, pulse_width_ms: float) -> float:
        """Convert pulse width in milliseconds to duty cycle percentage"""
        period_ms = 1000.0 / self.frequency  # 20ms for 50Hz
        return (pulse_width_ms / period_ms) * 100.0
    
    def angle_to_pulse_width(self, angle: int) -> float:
        """Convert angle to pulse width in milliseconds"""
        angle = max(self.min_angle, min(self.max_angle, angle))
        angle_range = self.max_angle - self.min_angle
        pulse_range = self.max_pulse - self.min_pulse
        return self.min_pulse + (angle - self.min_angle) * (pulse_range / angle_range)
    
    def set_angle(self, angle: int) -> bool:
        """Set servo to specific angle"""
        try:
            if not self.pwm:
                logging.warning(f"PWM not initialized for pin {self.pin}")
                return False
                
            angle = max(self.min_angle, min(self.max_angle, angle))
            pulse_width = self.angle_to_pulse_width(angle)
            duty_cycle = self.pulse_width_to_duty_cycle(pulse_width)
            
            self.pwm.ChangeDutyCycle(duty_cycle)
            self.current_angle = angle
            
            logging.debug(f"Servo pin {self.pin}: angle={angle}°, pulse={pulse_width:.2f}ms, duty={duty_cycle:.2f}%")
            return True
            
        except Exception as e:
            logging.error(f"Error setting servo angle: {e}")
            return False
    
    def set_position_percent(self, percent: float) -> bool:
        """Set servo position as percentage (0-100%)"""
        angle = int(self.min_angle + (percent / 100.0) * (self.max_angle - self.min_angle))
        return self.set_angle(angle)
    
    def get_current_angle(self) -> int:
        """Get current servo angle"""
        return self.current_angle
    
    def stop(self):
        """Stop PWM and cleanup"""
        if self.pwm:
            self.pwm.stop()


class PositionSensor:
    """Reads position from potentiometer via ADS1115 with filtering for erratic readings"""
    
    def __init__(self, ads: Any, channel: int, min_voltage: float = 0.1, 
                 max_voltage: float = 3.2, max_drift_percent: float = 10.0, 
                 enable_filtering: bool = True):
        self.ads = ads
        self.channel = channel
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.max_drift_percent = max_drift_percent
        self.enable_filtering = enable_filtering
        
        # Filtering variables
        self.last_valid_position = None
        self.last_valid_voltage = None
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.max_retries = 5
        
        if ADS and AnalogIn and ads is not None:
            self.analog_in = AnalogIn(ads, getattr(ADS, f'P{channel}'))
        else:
            self.analog_in = None
        
        # Log filtering status
        filter_status = "enabled" if self.enable_filtering else "disabled"
        logging.info(f"Position sensor channel {self.channel}: filtering {filter_status}")
    
    def read_voltage(self) -> float:
        """Read raw voltage from potentiometer with retry logic"""
        if not self.analog_in:
            # Simulation mode - return random value with occasional drift simulation
            import random
            if self.last_valid_voltage is None:
                voltage = random.uniform(self.min_voltage, self.max_voltage)
            else:
                # Simulate occasional drift for testing
                if random.random() < 0.05:  # 5% chance of drift
                    voltage = random.uniform(self.min_voltage, self.max_voltage)
                else:
                    # Normal small variation
                    voltage = self.last_valid_voltage + random.uniform(-0.1, 0.1)
                    voltage = max(self.min_voltage, min(self.max_voltage, voltage))
            return voltage
        
        # If filtering is disabled, just return raw reading with logging
        if not self.enable_filtering:
            try:
                voltage = self.analog_in.voltage
                logging.info(f"Raw voltage reading for channel {self.channel}: {voltage:.3f}V (filtering disabled)")
                return voltage
            except Exception as e:
                logging.error(f"Error reading voltage from channel {self.channel}: {e}")
                return (self.min_voltage + self.max_voltage) / 2
        
        # Try reading voltage with retries
        for attempt in range(self.max_retries):
            try:
                voltage = self.analog_in.voltage
                
                # For the first reading, accept any reasonable voltage to establish baseline
                if self.last_valid_voltage is None and self.min_voltage * 0.2 <= voltage <= self.max_voltage * 2.0:
                    logging.info(f"Initial voltage reading for channel {self.channel}: {voltage:.3f}V")
                    self.last_valid_voltage = voltage
                    self.consecutive_errors = 0
                    return voltage
                
                # Validate the reading
                if self._is_voltage_valid(voltage):
                    self.last_valid_voltage = voltage
                    self.consecutive_errors = 0
                    return voltage
                else:
                    logging.warning(f"Invalid voltage reading on channel {self.channel}: {voltage:.3f}V (attempt {attempt + 1})")
                    if attempt < self.max_retries - 1:
                        time.sleep(0.01)  # Small delay before retry
                    
            except Exception as e:
                logging.error(f"Error reading voltage from channel {self.channel} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.01)  # Small delay before retry
        
        # All retries failed - use last valid voltage if available
        self.consecutive_errors += 1
        if self.last_valid_voltage is not None and self.consecutive_errors <= self.max_consecutive_errors:
            logging.warning(f"Using last valid voltage for channel {self.channel}: {self.last_valid_voltage:.3f}V")
            return self.last_valid_voltage
        
        # Return a safe default value
        logging.error(f"All voltage readings failed for channel {self.channel}, using safe default")
        return (self.min_voltage + self.max_voltage) / 2
    
    def _is_voltage_valid(self, voltage: float) -> bool:
        """Check if voltage reading is valid (not a drift/error)"""
        # Check if voltage is within expected range (with very generous bounds)
        min_allowed = self.min_voltage * 0.5
        max_allowed = self.max_voltage * 1.5
        
        if voltage < min_allowed or voltage > max_allowed:
            logging.debug(f"Voltage {voltage:.3f}V outside range [{min_allowed:.3f}V - {max_allowed:.3f}V]")
            return False
        
        # If we have a previous reading, check for sudden drift
        if self.last_valid_voltage is not None:
            voltage_diff = abs(voltage - self.last_valid_voltage)
            voltage_range = self.max_voltage - self.min_voltage
            drift_percent = (voltage_diff / voltage_range) * 100
            
            if drift_percent > self.max_drift_percent:
                logging.debug(f"Voltage drift too large: {drift_percent:.1f}% > {self.max_drift_percent:.1f}%")
                return False
        
        return True
    
    def read_position_percent(self) -> float:
        """Read position as percentage (0-100%) with filtering"""
        voltage = self.read_voltage()
        
        # Clamp voltage to valid range
        voltage = max(self.min_voltage, min(self.max_voltage, voltage))
        
        # Convert to percentage
        voltage_range = self.max_voltage - self.min_voltage
        percent = ((voltage - self.min_voltage) / voltage_range) * 100.0
        position = max(0.0, min(100.0, percent))
        
        # Additional position-level filtering (only if filtering is enabled)
        if self.enable_filtering and self.last_valid_position is not None:
            position_diff = abs(position - self.last_valid_position)
            if position_diff > self.max_drift_percent:
                logging.warning(f"Large position change detected on channel {self.channel}: {position_diff:.1f}% (using last valid)")
                # Use last valid position if drift is too large
                return self.last_valid_position
        
        self.last_valid_position = position
        return position
    
    def get_sensor_stats(self) -> dict:
        """Get sensor statistics for debugging"""
        return {
            'channel': self.channel,
            'last_valid_voltage': self.last_valid_voltage,
            'last_valid_position': self.last_valid_position,
            'consecutive_errors': self.consecutive_errors,
            'max_drift_percent': self.max_drift_percent
        }


class TVArmController:
    """Main TV Arm Controller class"""
    
    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self.position_thread = None
        
        # Initialize GPIO
        if GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        
        # Initialize ADS1115
        self.ads = None
        if board and busio and ADS:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS.ADS1115(i2c, address=config['hardware']['ads1115']['address'])
                self.ads.gain = config['hardware']['ads1115']['gain']
                self.ads.data_rate = config['hardware']['ads1115']['data_rate']
                logging.info("ADS1115 initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize ADS1115: {e}")
        
        # Initialize DC motors with TB6612FNG driver
        motor_config = config['hardware']['dc_motor']
        
        # X-axis motor (Motor A)
        self.x_motor = DCMotorController(
            ain1_pin=config['hardware']['motor_x_ain1_pin'],
            ain2_pin=config['hardware']['motor_x_ain2_pin'],
            pwm_pin=config['hardware']['motor_x_pwm_pin'],
            stby_pin=config['hardware'].get('motor_stby_pin'),
            frequency=motor_config['frequency'],
            min_position=motor_config['min_position'],
            max_position=motor_config['max_position']
        )
        
        # Y-axis motor (Motor B)
        self.y_motor = DCMotorController(
            ain1_pin=config['hardware']['motor_y_ain1_pin'],
            ain2_pin=config['hardware']['motor_y_ain2_pin'],
            pwm_pin=config['hardware']['motor_y_pwm_pin'],
            stby_pin=config['hardware'].get('motor_stby_pin'),  # Shared standby pin
            frequency=motor_config['frequency'],
            min_position=motor_config['min_position'],
            max_position=motor_config['max_position']
        )
        
        # Initialize position sensors
        x_cal = config['hardware']['calibration']['x_axis']
        y_cal = config['hardware']['calibration']['y_axis']
        
        self.x_sensor = PositionSensor(
            self.ads, 
            config['hardware']['potentiometer']['x_axis_channel'],
            x_cal['min_voltage'], 
            x_cal['max_voltage'],
            x_cal.get('max_drift_percent', 10.0),
            x_cal.get('enable_filtering', True)
        )
        
        self.y_sensor = PositionSensor(
            self.ads,
            config['hardware']['potentiometer']['y_axis_channel'], 
            y_cal['min_voltage'],
            y_cal['max_voltage'],
            y_cal.get('max_drift_percent', 10.0),
            y_cal.get('enable_filtering', True)
        )
        
        # Current positions
        self.current_x_position = 50.0
        self.current_y_position = 50.0
        self.target_x_position = 50.0
        self.target_y_position = 50.0
        
        # Position update callback
        self.position_callback = None
        
        logging.info("TV Arm Controller initialized")
    
    def set_position_callback(self, callback):
        """Set callback function for position updates"""
        self.position_callback = callback
    
    def set_x_position(self, percent: float) -> bool:
        """Set X-axis position (0-100%)"""
        percent = max(0.0, min(100.0, percent))
        self.target_x_position = percent
        success = self.x_motor.set_position_percent(percent)
        logging.info(f"Set X position to {percent:.1f}%")
        return success
    
    def set_y_position(self, percent: float) -> bool:
        """Set Y-axis position (0-100%)"""
        percent = max(0.0, min(100.0, percent))
        self.target_y_position = percent
        success = self.y_motor.set_position_percent(percent)
        logging.info(f"Set Y position to {percent:.1f}%")
        return success
    
    def set_position(self, x_percent: float, y_percent: float) -> bool:
        """Set both X and Y positions"""
        x_success = self.set_x_position(x_percent)
        y_success = self.set_y_position(y_percent)
        return x_success and y_success
    
    def get_current_position(self) -> Tuple[float, float]:
        """Get current position from potentiometers"""
        x_pos = self.x_sensor.read_position_percent()
        y_pos = self.y_sensor.read_position_percent()
        return x_pos, y_pos
    
    def get_target_position(self) -> Tuple[float, float]:
        """Get target position"""
        return self.target_x_position, self.target_y_position
    
    def calibrate_position_sensors(self) -> dict:
        """Calibrate position sensors - move DC motors and read voltages"""
        logging.info("Starting position sensor calibration...")
        calibration_data = {
            'x_axis': {'min_voltage': None, 'max_voltage': None},
            'y_axis': {'min_voltage': None, 'max_voltage': None}
        }
        
        try:
            # Calibrate X-axis
            logging.info("Calibrating X-axis...")
            self.x_motor.set_position_percent(0)  # Move to minimum
            time.sleep(3)  # Give more time for DC motor movement
            min_x_voltage = self.x_sensor.read_voltage()
            
            self.x_motor.set_position_percent(100)  # Move to maximum
            time.sleep(3)  # Give more time for DC motor movement
            max_x_voltage = self.x_sensor.read_voltage()
            
            calibration_data['x_axis']['min_voltage'] = min_x_voltage
            calibration_data['x_axis']['max_voltage'] = max_x_voltage
            
            # Calibrate Y-axis
            logging.info("Calibrating Y-axis...")
            self.y_motor.set_position_percent(0)  # Move to minimum
            time.sleep(3)  # Give more time for DC motor movement
            min_y_voltage = self.y_sensor.read_voltage()
            
            self.y_motor.set_position_percent(100)  # Move to maximum
            time.sleep(3)  # Give more time for DC motor movement
            max_y_voltage = self.y_sensor.read_voltage()
            
            calibration_data['y_axis']['min_voltage'] = min_y_voltage
            calibration_data['y_axis']['max_voltage'] = max_y_voltage
            
            # Return to center
            self.set_position(50, 50)
            
            logging.info(f"Calibration complete: {calibration_data}")
            return calibration_data
            
        except Exception as e:
            logging.error(f"Calibration failed: {e}")
            return calibration_data
    
    def _position_update_loop(self):
        """Background thread to read positions and call callback"""
        update_interval = self.config['system']['position_update_interval']
        
        while self.running:
            try:
                # Read current positions
                x_pos, y_pos = self.get_current_position()
                self.current_x_position = x_pos
                self.current_y_position = y_pos
                
                # Call position update callback if set
                if self.position_callback:
                    self.position_callback(x_pos, y_pos)
                
                time.sleep(update_interval)
                
            except Exception as e:
                logging.error(f"Error in position update loop: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the controller"""
        if self.running:
            return
        
        logging.info("Starting TV Arm Controller...")
        self.running = True
        
        # Start position update thread
        self.position_thread = threading.Thread(target=self._position_update_loop, daemon=True)
        self.position_thread.start()
        
        # Move to default position if configured
        if self.config['system']['restore_position_on_startup']:
            default_x = self.config['system']['default_x_position']
            default_y = self.config['system']['default_y_position']
            self.set_position(default_x, default_y)
        
        logging.info("TV Arm Controller started")
    
    def stop(self):
        """Stop the controller"""
        if not self.running:
            return
        
        logging.info("Stopping TV Arm Controller...")
        self.running = False
        
        # Wait for position thread to finish
        if self.position_thread and self.position_thread.is_alive():
            self.position_thread.join(timeout=2)
        
        # Stop motors
        self.x_motor.stop()
        self.y_motor.stop()
        
        # Cleanup GPIO
        if GPIO:
            GPIO.cleanup()
        
        logging.info("TV Arm Controller stopped")
    
    def emergency_stop(self):
        """Emergency stop - immediately stop all movement"""
        logging.warning("EMERGENCY STOP activated!")
        self.stop()
    
    def get_sensor_diagnostics(self) -> dict:
        """Get sensor diagnostic information for troubleshooting"""
        return {
            'x_sensor': self.x_sensor.get_sensor_stats(),
            'y_sensor': self.y_sensor.get_sensor_stats()
        }


def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown"""
    logging.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    import yaml
    import argparse
    
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='TV Arm Controller')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--calibrate', action='store_true', help='Run calibration mode')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    args = parser.parse_args()
    
    # Load configuration
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Set up logging
    logging.basicConfig(
        level=getattr(logging, config['system']['log_level']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config['system']['log_file']),
            logging.StreamHandler()
        ]
    )
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create controller
    controller = TVArmController(config)
    
    try:
        if args.calibrate:
            # Calibration mode
            print("Starting calibration mode...")
            controller.start()
            calibration_data = controller.calibrate_position_sensors()
            print("Calibration results:")
            for axis, data in calibration_data.items():
                print(f"  {axis}: min={data['min_voltage']:.3f}V, max={data['max_voltage']:.3f}V")
            
        elif args.test:
            # Test mode
            print("Starting test mode...")
            controller.start()
            
            def position_update(x, y):
                print(f"Position: X={x:.1f}%, Y={y:.1f}%")
            
            controller.set_position_callback(position_update)
            
            # Test movement pattern
            positions = [(0, 0), (100, 0), (100, 100), (0, 100), (50, 50)]
            for x, y in positions:
                print(f"Moving to X={x}%, Y={y}%")
                controller.set_position(x, y)
                time.sleep(3)
            
            print("Test complete. Press Ctrl+C to exit.")
            while True:
                time.sleep(1)
        
        else:
            # Normal mode - just start controller
            controller.start()
            print("TV Arm Controller running. Press Ctrl+C to exit.")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        controller.stop()
        print("TV Arm Controller stopped.")
