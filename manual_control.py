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
        self.continuous_speed = 30.0  # Speed for continuous movement
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
        """Process key press and control motors"""
        if key == '\x1b[A':  # Up arrow
            print("↑ Y UP")
            self.moving_y = 1
        elif key == '\x1b[B':  # Down arrow
            print("↓ Y DOWN")
            self.moving_y = -1
        elif key == '\x1b[C':  # Right arrow
            print("→ X RIGHT")
            self.moving_x = 1
        elif key == '\x1b[D':  # Left arrow
            print("← X LEFT")
            self.moving_x = -1
        elif key == ' ':  # Spacebar - stop all
            print("⏹️  STOP ALL")
            self.moving_x = 0
            self.moving_y = 0
            self.tv_controller.x_motor.stop_motor()
            self.tv_controller.y_motor.stop_motor()
        elif key == 'q' or key == '\x03':  # Q or Ctrl+C
            print("🚪 QUIT")
            self.running = False
            return False
        elif key == '+':  # Increase step size
            self.step_size = min(10.0, self.step_size + 0.5)
            print(f"📏 Step size: {self.step_size:.1f}%")
        elif key == '-':  # Decrease step size
            self.step_size = max(0.5, self.step_size - 0.5)
            print(f"📏 Step size: {self.step_size:.1f}%")
        elif key == 's':  # Show current position
            try:
                x, y = self.tv_controller.get_current_position()
                print(f"📍 Position: X={x:.1f}%, Y={y:.1f}%")
            except:
                print("❌ Error reading position")
        
        return True
    
    def control_loop(self):
        """Main control loop for continuous movement"""
        last_position_update = 0
        
        while self.running:
            try:
                # Get current position periodically
                current_time = time.time()
                if current_time - last_position_update > self.position_update_interval:
                    try:
                        x, y = self.tv_controller.get_current_position()
                        print(f"\r📍 X={x:5.1f}%, Y={y:5.1f}% | Moving: X={'→' if self.moving_x > 0 else '←' if self.moving_x < 0 else '■'} Y={'↑' if self.moving_y > 0 else '↓' if self.moving_y < 0 else '■'}", end="", flush=True)
                        last_position_update = current_time
                    except:
                        pass
                
                # Apply continuous movement
                if self.moving_x != 0:
                    try:
                        x, y = self.tv_controller.get_current_position()
                        if self.moving_x > 0:  # Move right (increase X)
                            new_x = min(100.0, x + self.step_size)
                            print(f"\n🔧 X: {x:.1f}% → {new_x:.1f}%")
                            self.tv_controller.set_x_position(new_x, use_closed_loop=False)
                        else:  # Move left (decrease X)
                            new_x = max(0.0, x - self.step_size)
                            print(f"\n🔧 X: {x:.1f}% → {new_x:.1f}%")
                            self.tv_controller.set_x_position(new_x, use_closed_loop=False)
                    except Exception as e:
                        print(f"\n❌ X motor error: {e}")
                
                if self.moving_y != 0:
                    try:
                        x, y = self.tv_controller.get_current_position()
                        if self.moving_y > 0:  # Move up (increase Y)
                            new_y = min(100.0, y + self.step_size)
                            print(f"\n🔧 Y: {y:.1f}% → {new_y:.1f}%")
                            self.tv_controller.set_y_position(new_y, use_closed_loop=False)
                        else:  # Move down (decrease Y)
                            new_y = max(0.0, y - self.step_size)
                            print(f"\n🔧 Y: {y:.1f}% → {new_y:.1f}%")
                            self.tv_controller.set_y_position(new_y, use_closed_loop=False)
                    except Exception as e:
                        print(f"\n❌ Y motor error: {e}")
                
                time.sleep(0.1)  # Control loop frequency
                
            except Exception as e:
                print(f"\n❌ Error in control loop: {e}")
                break
    
    def run(self):
        """Run manual control mode"""
        print("🎮 Manual TV Arm Control")
        print("=" * 50)
        print("Use arrow keys to control the TV arm:")
        print("  ↑ ↓  - Y axis (up/down)")
        print("  ← →  - X axis (left/right)")
        print("  SPACE - Stop all movement")
        print("  + -   - Adjust step size")
        print("  S     - Show current position")
        print("  Q     - Quit manual control")
        print()
        print("Press any arrow key to start...")
        print()
        
        if not self.setup_terminal():
            return False
        
        try:
            self.running = True
            
            # Start control loop thread
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            
            # Main key processing loop
            while self.running:
                key = self.get_key()
                if key:
                    if not self.process_key(key):
                        break
                time.sleep(0.05)  # Small delay to prevent CPU spinning
            
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
