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
        self.continuous_speed = 60.0  # Speed for continuous movement
        self.position_update_interval = 0.2  # How often to show position
        
        # Current movement state
        self.moving_x = 0  # -1 = left, 0 = stop, 1 = right
        self.moving_y = 0  # -1 = down, 0 = stop, 1 = up
        
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
        """Process key press and control motors directly"""
        if key == '\x1b[A':  # Up arrow - Y motor forward
            print("↑ Y UP")
            self.tv_controller.y_motor.set_direction_forward()
            self.tv_controller.y_motor.set_speed(self.continuous_speed)
        elif key == '\x1b[B':  # Down arrow - Y motor reverse
            print("↓ Y DOWN")
            self.tv_controller.y_motor.set_direction_reverse()
            self.tv_controller.y_motor.set_speed(self.continuous_speed)
        elif key == '\x1b[C':  # Right arrow - X motor forward
            print("→ X RIGHT")
            self.tv_controller.x_motor.set_direction_forward()
            self.tv_controller.x_motor.set_speed(self.continuous_speed)
        elif key == '\x1b[D':  # Left arrow - X motor reverse
            print("← X LEFT")
            self.tv_controller.x_motor.set_direction_reverse()
            self.tv_controller.x_motor.set_speed(self.continuous_speed)
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
    
    def control_loop(self):
        """Main control loop for position display"""
        last_position_update = 0
        
        while self.running:
            try:
                # Get current position periodically
                current_time = time.time()
                if current_time - last_position_update > self.position_update_interval:
                    try:
                        x, y = self.tv_controller.get_current_position()
                        print(f"\r📍 X={x:5.1f}%, Y={y:5.1f}% | Speed: {self.continuous_speed:.0f}%        ", end="", flush=True)
                        last_position_update = current_time
                    except:
                        pass
                
                time.sleep(0.1)  # Control loop frequency
                
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
                
                time.sleep(0.02)  # Fast polling for responsive control
            
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
