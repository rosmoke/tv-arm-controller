#!/usr/bin/env python3
"""
Manual TV Arm Control - Arrow key control for real-time TV arm movement
Use arrow keys to control X and Y axes manually
"""

import sys
import time
import termios
import tty
import select
import threading
from typing import Optional


class ManualController:
    """Manual arrow key controller for TV arm"""
    
    def __init__(self, tv_controller):
        self.tv_controller = tv_controller
        self.running = False
        self.control_thread = None
        
        # Control settings
        self.step_size = 2.0  # Percentage to move per key press
        self.continuous_speed = 60.0  # Speed for continuous movement (increased for faster manual control)
        self.speed_multiplier = 1.5  # Internal multiplier for actual motor speed
        self.position_update_interval = 0.3  # How often to show position (balance between accuracy and I2C load)
        
        # Current movement state
        self.moving_x = 0  # -1 = left, 0 = stop, 1 = right
        self.moving_y = 0  # -1 = down, 0 = stop, 1 = up
        
        # Position caching to reduce I2C calls and prevent deadlock
        self.last_position_read = 0
        self.cached_x_pos = 0
        self.cached_y_pos = 0
        self.position_cache_duration = 0.2  # Cache position for 200ms (balance between accuracy and I2C load)
        
        # I2C deadlock prevention
        self.last_safety_check = 0
        self.safety_check_interval = 0.05  # Check safety every 50ms for responsive manual control
        self.i2c_lock = threading.Lock()  # Serialize I2C operations to prevent deadlock
        
        # Terminal settings for raw key input
        self.old_settings = None
    
    def setup_terminal(self):
        """Setup terminal for raw key input"""
        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            return True
        except Exception as e:
            print(f"❌ Error setting up terminal: {e}")
            return False
    
    def restore_terminal(self):
        """Restore terminal to normal mode"""
        if self.old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except:
                pass
    
    def get_key(self) -> Optional[str]:
        """Get a single key press without blocking"""
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            key = sys.stdin.read(1)
            # Handle escape sequences for arrow keys
            if key == '\x1b':  # ESC sequence
                if select.select([sys.stdin], [], [], 0.1) == ([sys.stdin], [], []):
                    key += sys.stdin.read(1)
                    if key == '\x1b[':
                        if select.select([sys.stdin], [], [], 0.1) == ([sys.stdin], [], []):
                            key += sys.stdin.read(1)
            return key
        return None
    
    def process_key(self, key: str):
        """Process key press and control motors directly with safety limits"""
        # Calculate actual motor speed (UI speed * multiplier)
        actual_speed = min(100.0, self.continuous_speed * self.speed_multiplier)
        
        if key == '\x1b[A':  # Up arrow - Y motor forward
            print("↑ Y UP")
            safe_speed = self._check_motor_safety('y', 'forward', actual_speed)
            if safe_speed > 0:
                self.tv_controller.y_motor.set_direction_forward()
                self.tv_controller.y_motor.set_speed(safe_speed)
            else:
                print("🛑 Y SAFETY STOP")
                self.tv_controller.y_motor.stop_motor()
        elif key == '\x1b[B':  # Down arrow - Y motor reverse
            print("↓ Y DOWN")
            safe_speed = self._check_motor_safety('y', 'reverse', actual_speed)
            if safe_speed > 0:
                self.tv_controller.y_motor.set_direction_reverse()
                self.tv_controller.y_motor.set_speed(safe_speed)
            else:
                print("🛑 Y SAFETY STOP")
                self.tv_controller.y_motor.stop_motor()
        elif key == '\x1b[C':  # Right arrow - X motor forward
            print("→ X RIGHT")
            safe_speed = self._check_motor_safety('x', 'forward', actual_speed)
            if safe_speed > 0:
                self.tv_controller.x_motor.set_direction_forward()
                self.tv_controller.x_motor.set_speed(safe_speed)
            else:
                print("🛑 X SAFETY STOP")
                self.tv_controller.x_motor.stop_motor()
        elif key == '\x1b[D':  # Left arrow - X motor reverse
            print("← X LEFT")
            safe_speed = self._check_motor_safety('x', 'reverse', actual_speed)
            if safe_speed > 0:
                self.tv_controller.x_motor.set_direction_reverse()
                self.tv_controller.x_motor.set_speed(safe_speed)
            else:
                print("🛑 X SAFETY STOP")
                self.tv_controller.x_motor.stop_motor()
        elif key == ' ':  # Spacebar - stop all
            print("⏹️  STOP ALL")
            self.tv_controller.x_motor.stop_motor()
            self.tv_controller.y_motor.stop_motor()
        elif key == 'q' or key == '\x03':  # Q or Ctrl+C
            print("🚪 QUIT")
            self.running = False
            return False
        elif key == '+':  # Increase speed
            self.continuous_speed = min(100.0, self.continuous_speed + 5.0)
            print(f"⚡ Speed: {self.continuous_speed:.0f}%")
        elif key == '-':  # Decrease speed
            self.continuous_speed = max(10.0, self.continuous_speed - 5.0)
            print(f"⚡ Speed: {self.continuous_speed:.0f}%")
        elif key == 's':  # Show current position
            try:
                x, y = self.tv_controller.get_current_position()
                print(f"📍 Position: X={x:.1f}%, Y={y:.1f}%")
            except:
                print("❌ Error reading position")
        
        return True
    
    def _get_cached_position(self):
        """Get position with caching and I2C deadlock prevention"""
        current_time = time.time()
        if current_time - self.last_position_read > self.position_cache_duration:
            # Use lock to serialize I2C operations and prevent deadlock
            if self.i2c_lock.acquire(blocking=False):  # Non-blocking acquire
                try:
                    self.cached_x_pos, self.cached_y_pos = self.tv_controller.get_current_position()
                    self.last_position_read = current_time
                except Exception as e:
                    print(f"❌ Position read error: {e}")
                    # Keep using cached values on error - prevents deadlock
                finally:
                    self.i2c_lock.release()
            # If lock not available, use cached values (prevents blocking)
        return self.cached_x_pos, self.cached_y_pos
    
    def _check_motor_safety(self, axis: str, direction: str, requested_speed: float) -> float:
        """Check safety limits and return safe speed (0 = stop)"""
        try:
            # Throttle safety checks to prevent I2C deadlock
            current_time = time.time()
            if current_time - self.last_safety_check < self.safety_check_interval:
                return requested_speed  # Skip safety check, use last known safe speed
            
            self.last_safety_check = current_time
            
            # Get cached position to reduce I2C calls
            x_pos, y_pos = self._get_cached_position()
            
            if axis == 'x':
                # Get X sensor voltage with I2C lock protection
                if self.i2c_lock.acquire(blocking=False):  # Non-blocking acquire
                    try:
                        current_voltage = self.tv_controller.x_sensor.read_voltage()
                    except Exception as e:
                        print(f"❌ X voltage read error: {e}")
                        return requested_speed  # Allow movement on sensor error
                    finally:
                        self.i2c_lock.release()
                else:
                    return requested_speed  # Skip safety check if I2C busy
                config = self.tv_controller.config['hardware']['calibration']['x_axis']
            else:
                # Get Y sensor voltage with I2C lock protection
                if self.i2c_lock.acquire(blocking=False):  # Non-blocking acquire
                    try:
                        current_voltage = self.tv_controller.y_sensor.read_voltage()
                    except Exception as e:
                        print(f"❌ Y voltage read error: {e}")
                        return requested_speed  # Allow movement on sensor error
                    finally:
                        self.i2c_lock.release()
                else:
                    return requested_speed  # Skip safety check if I2C busy
                config = self.tv_controller.config['hardware']['calibration']['y_axis']
            
            # Get safety settings
            min_voltage = config['min_voltage']
            max_voltage = config['max_voltage']
            safety_margin = config.get('safety_margin', 0.05)
            slow_zone_margin = config.get('slow_zone_margin', 0.1)
            safety_slow_speed = config.get('safety_slow_speed', 30)
            
            # Debug output
            print(f"\n🔍 {axis.upper()} Safety Check:")
            print(f"   Voltage: {current_voltage:.3f}V, Range: {min_voltage:.3f}V-{max_voltage:.3f}V")
            print(f"   Margins: safety={safety_margin:.3f}V, slow={slow_zone_margin:.3f}V")
            print(f"   Direction: {direction}, Requested: {requested_speed:.1f}%")
            
            # Check safety using motor's safety method
            if axis == 'x':
                should_stop, max_speed = self.tv_controller.x_motor.check_safety_limits(
                    current_voltage, min_voltage, max_voltage, 
                    safety_margin, slow_zone_margin, safety_slow_speed, direction)
            else:
                should_stop, max_speed = self.tv_controller.y_motor.check_safety_limits(
                    current_voltage, min_voltage, max_voltage,
                    safety_margin, slow_zone_margin, safety_slow_speed, direction)
            
            print(f"   Result: stop={should_stop}, max_speed={max_speed:.1f}%")
            
            if should_stop:
                print(f"   🛑 STOPPING {axis.upper()} motor")
                return 0
            else:
                final_speed = min(requested_speed, max_speed)
                print(f"   ✅ {axis.upper()} speed: {requested_speed:.1f}% → {final_speed:.1f}%")
                return final_speed
                
        except Exception as e:
            print(f"❌ Safety check error for {axis}: {e}")
            return 0  # Stop on error for safety
    
    def control_loop(self):
        """Main control loop for position display"""
        last_position_update = 0
        
        while self.running:
            try:
                # Get current position periodically
                current_time = time.time()
                if current_time - last_position_update > self.position_update_interval:
                    try:
                        x, y = self._get_cached_position()
                        print(f"\r📍 X={x:5.1f}%, Y={y:5.1f}% | Speed: {self.continuous_speed:.0f}%        ", end="", flush=True)
                        last_position_update = current_time
                    except:
                        pass
                
                time.sleep(0.1)  # Balanced response time (100ms)
                
            except Exception as e:
                print(f"\n❌ Error in control loop: {e}")
                break
    
    def run(self):
        """Run manual control mode"""
        print("🎮 Manual TV Arm Control")
        print("=" * 50)
        print("HOLD arrow keys for continuous movement:")
        print("  ↑ ↓  - Y axis (up/down)")
        print("  ← →  - X axis (left/right)")
        print("  SPACE - Emergency stop")
        print("  + -   - Adjust motor speed")
        print("  S     - Show current position")
        print("  Q     - Quit manual control")
        print()
        print("Motors move ONLY while keys are held down!")
        print("Release key to stop immediately.")
        print()
        
        if not self.setup_terminal():
            return False
        
        try:
            self.running = True
            
            # Start control loop thread
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            
            # Main key processing loop
            last_key_time = 0
            key_timeout = 0.15  # Stop motors if no key pressed for 150ms
            
            while self.running:
                key = self.get_key()
                current_time = time.time()
                
                if key:
                    last_key_time = current_time
                    if not self.process_key(key):
                        break
                else:
                    # No key pressed - check if we should stop motors
                    if current_time - last_key_time > key_timeout:
                        # Stop motors if no key has been pressed recently
                        self.tv_controller.x_motor.stop_motor()
                        self.tv_controller.y_motor.stop_motor()
                        last_key_time = current_time  # Reset to prevent repeated stopping
                
                time.sleep(0.02)  # Faster key detection (20ms for responsive control)
            
            # Stop all motors when exiting
            self.tv_controller.x_motor.stop_motor()
            self.tv_controller.y_motor.stop_motor()
            
            print("\n🛑 Manual control stopped - motors stopped")
            return True
            
        except KeyboardInterrupt:
            print("\n🛑 Manual control interrupted")
            return True
        except Exception as e:
            print(f"\n❌ Error in manual control: {e}")
            return False
        finally:
            self.running = False
            self.restore_terminal()


def main():
    """Test manual control standalone"""
    import yaml
    from tv_arm_controller import TVArmController
    
    print("🚀 Manual TV Arm Control Test")
    print("Loading configuration...")
    
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        controller = TVArmController(config)
        controller.start(teaching_mode=True)
        
        manual = ManualController(controller)
        manual.run()
        
        controller.stop()
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
