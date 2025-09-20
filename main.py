#!/usr/bin/env python3
"""
TV Arm Controller - Main application
Integrates hardware control with Home Assistant MQTT
"""

import sys
import time
import signal
import logging
import argparse
import yaml
from pathlib import Path

from tv_arm_controller import TVArmController
from home_assistant_integration import HomeAssistantMQTT
from path_recorder import PathRecorder


class TVArmApplication:
    """Main application class that coordinates hardware and Home Assistant integration"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.controller = None
        self.ha_integration = None
        self.path_recorder = None
        self.running = False
        
        # Set up logging
        self._setup_logging()
        
        logging.info(f"TV Arm Application initialized with config: {config_path}")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            print(f"Error loading configuration from {config_path}: {e}")
            sys.exit(1)
    
    def _setup_logging(self):
        """Configure logging based on config settings"""
        log_level = getattr(logging, self.config['system']['log_level'].upper())
        log_file = self.config['system']['log_file']
        
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"Logging configured: level={self.config['system']['log_level']}, file={log_file}")
    
    def _setup_command_handlers(self):
        """Set up command handlers for Home Assistant integration"""
        if not self.ha_integration or not self.controller:
            return
        
        # Cover commands
        def handle_open():
            """Handle OPEN command - move to predefined open position"""
            logging.info("Executing OPEN command")
            self.controller.set_position(100, 100)  # Move to top-right
            self.ha_integration.set_cover_state("opening")
            
        def handle_close():
            """Handle CLOSE command - move to predefined close position"""
            logging.info("Executing CLOSE command")
            self.controller.set_position(0, 0)  # Move to bottom-left
            self.ha_integration.set_cover_state("closing")
            
        def handle_stop():
            """Handle STOP command - stop all movement"""
            logging.info("Executing STOP command")
            # Note: Current servo implementation doesn't support stopping mid-movement
            # But we can update the state
            self.ha_integration.set_cover_state("stopped")
            
        def handle_set_position(position: int):
            """Handle SET_POSITION command"""
            logging.info(f"Executing SET_POSITION command: {position}%")
            # Convert single position to X,Y coordinates (you might want to customize this)
            x_pos = position
            y_pos = position
            self.controller.set_position(x_pos, y_pos)
            
        def handle_set_x_position(x_position: float):
            """Handle X-axis position command"""
            logging.info(f"Setting X position to {x_position}%")
            self.controller.set_x_position(x_position)
            
        def handle_set_y_position(y_position: float):
            """Handle Y-axis position command"""
            logging.info(f"Setting Y position to {y_position}%")
            self.controller.set_y_position(y_position)
        
        def handle_start_recording(path_name: str = None):
            """Handle start recording command"""
            logging.info(f"Starting path recording: {path_name or 'auto-generated name'}")
            if self.path_recorder:
                success = self.path_recorder.start_recording(path_name)
                if success:
                    self.ha_integration.publish_message("homeassistant/sensor/tv_arm_recording/state", "recording")
                return success
            return False
        
        def handle_stop_recording():
            """Handle stop recording command"""
            logging.info("Stopping path recording")
            if self.path_recorder:
                success = self.path_recorder.stop_recording()
                if success:
                    self.ha_integration.publish_message("homeassistant/sensor/tv_arm_recording/state", "stopped")
                return success
            return False
        
        def handle_play_path(path_name: str, speed: float = 1.0):
            """Handle play path command"""
            logging.info(f"Playing path: {path_name} at {speed}x speed")
            if self.path_recorder:
                success = self.path_recorder.play_path(path_name, speed)
                if success:
                    self.ha_integration.publish_message("homeassistant/sensor/tv_arm_playback/state", "playing")
                return success
            return False
        
        def handle_stop_playback():
            """Handle stop playback command"""
            logging.info("Stopping path playback")
            if self.path_recorder:
                success = self.path_recorder.stop_playback()
                if success:
                    self.ha_integration.publish_message("homeassistant/sensor/tv_arm_playback/state", "stopped")
                return success
            return False
        
        # Register command handlers
        self.ha_integration.set_command_handler('open', handle_open)
        self.ha_integration.set_command_handler('close', handle_close)
        self.ha_integration.set_command_handler('stop', handle_stop)
        self.ha_integration.set_command_handler('set_position', handle_set_position)
        self.ha_integration.set_command_handler('set_x_position', handle_set_x_position)
        self.ha_integration.set_command_handler('set_y_position', handle_set_y_position)
        
        # Path recording command handlers
        self.ha_integration.set_command_handler('start_recording', handle_start_recording)
        self.ha_integration.set_command_handler('stop_recording', handle_stop_recording)
        self.ha_integration.set_command_handler('play_path', handle_play_path)
        self.ha_integration.set_command_handler('stop_playback', handle_stop_playback)
        
        logging.info("Command handlers configured")
    
    def _position_update_callback(self, x_position: float, y_position: float):
        """Callback for position updates from hardware controller"""
        if self.ha_integration:
            self.ha_integration.update_position(x_position, y_position)
    
    def start(self) -> bool:
        """Start the TV Arm application"""
        if self.running:
            logging.warning("Application already running")
            return True
        
        logging.info("Starting TV Arm Application...")
        
        try:
            # Initialize hardware controller
            logging.info("Initializing hardware controller...")
            self.controller = TVArmController(self.config)
            self.controller.set_position_callback(self._position_update_callback)
            
            # Initialize Home Assistant integration
            logging.info("Initializing Home Assistant integration...")
            self.ha_integration = HomeAssistantMQTT(self.config)
            
            # Initialize Path Recorder
            logging.info("Initializing Path Recorder...")
            self.path_recorder = PathRecorder(self.controller, self.config)
            
            # Set up command handlers
            self._setup_command_handlers()
            
            # Start hardware controller
            logging.info("Starting hardware controller...")
            self.controller.start()
            
            # Start Home Assistant integration
            logging.info("Starting Home Assistant integration...")
            if not self.ha_integration.start():
                logging.error("Failed to start Home Assistant integration")
                # Continue running without HA integration
            
            self.running = True
            logging.info("TV Arm Application started successfully")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start TV Arm Application: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the TV Arm application"""
        if not self.running:
            return
        
        logging.info("Stopping TV Arm Application...")
        self.running = False
        
        # Stop Path Recorder
        if self.path_recorder:
            self.path_recorder.cleanup()
            self.path_recorder = None
        
        # Stop Home Assistant integration
        if self.ha_integration:
            self.ha_integration.stop()
            self.ha_integration = None
        
        # Stop hardware controller
        if self.controller:
            self.controller.stop()
            self.controller = None
        
        logging.info("TV Arm Application stopped")
    
    def run_calibration(self) -> dict:
        """Run calibration procedure"""
        if not self.controller:
            logging.error("Hardware controller not initialized")
            return {}
        
        logging.info("Starting calibration procedure...")
        
        # Start controller if not running
        was_running = self.running
        if not was_running:
            self.controller.start()
        
        try:
            # Run calibration
            calibration_data = self.controller.calibrate_position_sensors()
            
            logging.info("Calibration completed successfully")
            logging.info(f"Calibration results: {calibration_data}")
            
            return calibration_data
            
        except Exception as e:
            logging.error(f"Calibration failed: {e}")
            return {}
        
        finally:
            # Stop controller if we started it
            if not was_running:
                self.controller.stop()
    
    def run_test_sequence(self):
        """Run test movement sequence"""
        if not self.controller:
            logging.error("Hardware controller not initialized")
            return
        
        logging.info("Starting test sequence...")
        
        # Start controller if not running
        was_running = self.running
        if not was_running:
            self.controller.start()
        
        try:
            # Test positions: corners and center
            test_positions = [
                (0, 0, "Bottom-Left"),
                (100, 0, "Bottom-Right"), 
                (100, 100, "Top-Right"),
                (0, 100, "Top-Left"),
                (50, 50, "Center")
            ]
            
            for x, y, description in test_positions:
                logging.info(f"Moving to {description}: X={x}%, Y={y}%")
                print(f"Moving to {description}: X={x}%, Y={y}%")
                
                self.controller.set_position(x, y)
                
                # Wait and show current position
                time.sleep(3)
                current_x, current_y = self.controller.get_current_position()
                print(f"Current position: X={current_x:.1f}%, Y={current_y:.1f}%")
                
                time.sleep(2)  # Pause between movements
            
            logging.info("Test sequence completed")
            print("Test sequence completed")
            
        except Exception as e:
            logging.error(f"Test sequence failed: {e}")
            print(f"Test sequence failed: {e}")
        
        finally:
            # Stop controller if we started it
            if not was_running:
                self.controller.stop()
    
    def is_running(self) -> bool:
        """Check if application is running"""
        return self.running
    
    def run_teaching_mode(self):
        """Run interactive teaching mode"""
        print("Initializing hardware controller for teaching mode...")
        
        # Initialize controller if not already done
        if not self.controller:
            try:
                self.controller = TVArmController(self.config)
                logging.info("Hardware controller initialized for teaching mode")
            except Exception as e:
                logging.error(f"Failed to initialize hardware controller: {e}")
                print(f"Error initializing hardware controller: {e}")
                print("Make sure all dependencies are installed and hardware is connected.")
                return
        
        # Initialize components
        was_running = self.running
        if not was_running:
            self.controller.start(teaching_mode=True)  # Don't auto-move in teaching mode
            self.path_recorder = PathRecorder(self.controller, self.config)
        
        try:
            while True:
                print("\n" + "=" * 40)
                print("TEACHING MODE MENU")
                print("=" * 40)
                print("1. Start recording a new path")
                print("2. Stop current recording")
                print("3. List recorded paths")
                print("4. Play a recorded path")
                print("5. Delete a recorded path")
                print("6. Show current position")
                print("7. Show sensor diagnostics")
                print("8. Move to WALL position")
                print("9. Move to EXTENDED position")
                print("10. Manual step-through path playback")
                print("11. Exit teaching mode")
                print()
                
                choice = input("Enter your choice (1-11): ").strip()
                
                if choice == '1':
                    path_name = input("Enter path name (or press Enter for auto-generated): ").strip()
                    if not path_name:
                        path_name = None
                    
                    print("\nStarting recording...")
                    print("Manually move the TV arm to create your path.")
                    print("The system will record the position every 0.1 seconds.")
                    print("Press Enter when done recording.")
                    
                    if self.path_recorder.start_recording(path_name):
                        input("Recording... Press Enter to stop.")
                        if self.path_recorder.stop_recording():
                            print("Path recorded successfully!")
                        else:
                            print("Failed to save path.")
                    else:
                        print("Failed to start recording.")
                
                elif choice == '2':
                    if self.path_recorder.stop_recording():
                        print("Recording stopped and saved.")
                    else:
                        print("No active recording to stop.")
                
                elif choice == '3':
                    self._list_paths_interactive()
                
                elif choice == '4':
                    self._play_path_interactive()
                
                elif choice == '5':
                    self._delete_path_interactive()
                
                elif choice == '6':
                    x, y = self.controller.get_current_position()
                    print(f"Current position: X={x:.1f}%, Y={y:.1f}%")
                
                elif choice == '7':
                    # Show sensor diagnostics
                    diagnostics = self.controller.get_sensor_diagnostics()
                    print("\nSensor Diagnostics:")
                    print("-" * 40)
                    for sensor_name, stats in diagnostics.items():
                        print(f"{sensor_name.upper()}:")
                        print(f"  Channel: {stats['channel']}")
                        print(f"  Last valid voltage: {stats['last_valid_voltage']:.3f}V" if stats['last_valid_voltage'] else "  Last valid voltage: None")
                        print(f"  Last valid position: {stats['last_valid_position']:.1f}%" if stats['last_valid_position'] else "  Last valid position: None")
                        print(f"  Consecutive errors: {stats['consecutive_errors']}")
                        print(f"  Max drift threshold: {stats['max_drift_percent']:.1f}%")
                        print()
                
                elif choice == '8':
                    # Move to WALL position
                    wall_x = 96.9  # Your measured wall position
                    wall_y = 23.1
                    print(f"Moving to WALL position: X={wall_x:.1f}%, Y={wall_y:.1f}%")
                    print("Using closed-loop control - will wait for actual position...")
                    try:
                        print("Moving X axis to wall position...")
                        x_success = self.controller.set_x_position(wall_x, use_closed_loop=False)  # Use open-loop for now
                        print("Moving Y axis to wall position...")
                        y_success = self.controller.set_y_position(wall_y, use_closed_loop=False)  # Use open-loop for now
                        if x_success and y_success:
                            print("✅ Movement commands sent to WALL position!")
                            print("Check current position to verify arrival...")
                        else:
                            print("❌ Failed to send movement commands")
                    except Exception as e:
                        print(f"❌ Error moving to wall: {e}")
                
                elif choice == '9':
                    # Move to EXTENDED position
                    ext_x = 62.3  # Your measured extended position
                    ext_y = 88.7
                    print(f"Moving to EXTENDED position: X={ext_x:.1f}%, Y={ext_y:.1f}%")
                    print("Using closed-loop control - will wait for actual position...")
                    try:
                        print("Moving X axis to extended position...")
                        x_success = self.controller.set_x_position(ext_x, use_closed_loop=False)  # Use open-loop for now
                        print("Moving Y axis to extended position...")
                        y_success = self.controller.set_y_position(ext_y, use_closed_loop=False)  # Use open-loop for now
                        if x_success and y_success:
                            print("✅ Movement commands sent to EXTENDED position!")
                            print("Check current position to verify arrival...")
                        else:
                            print("❌ Failed to send movement commands")
                    except Exception as e:
                        print(f"❌ Error moving to extended: {e}")
                
                elif choice == '10':
                    # Manual step-through path playback
                    self._manual_step_playback()
                
                elif choice == '11':
                    print("Exiting teaching mode...")
                    break
                
                else:
                    print("Invalid choice. Please enter 1-11.")
                    
        except KeyboardInterrupt:
            print("\nTeaching mode interrupted.")
        except Exception as e:
            logging.error(f"Error in teaching mode: {e}")
            print(f"Error in teaching mode: {e}")
        finally:
            if self.path_recorder:
                self.path_recorder.cleanup()
            if not was_running:
                self.controller.stop()
    
    def _list_paths_interactive(self):
        """List paths in interactive mode"""
        paths = self.path_recorder.list_paths()
        if not paths:
            print("No recorded paths found.")
            return
        
        print(f"\nFound {len(paths)} recorded paths:")
        print("-" * 60)
        for i, path in enumerate(paths, 1):
            duration = path['duration']
            points = path['point_count']
            recorded_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path['recorded_at']))
            print(f"{i}. {path['name']} - {duration:.1f}s, {points} points, recorded: {recorded_time}")
    
    def _play_path_interactive(self):
        """Play path in interactive mode"""
        paths = self.path_recorder.list_paths()
        if not paths:
            print("No recorded paths found.")
            return
        
        self._list_paths_interactive()
        
        try:
            choice = int(input("\nEnter path number to play: ")) - 1
            if 0 <= choice < len(paths):
                path_name = paths[choice]['name']
                speed = input("Enter playback speed (default 1.0): ").strip()
                speed = float(speed) if speed else 1.0
                
                print(f"Playing path '{path_name}' at {speed}x speed...")
                print("Press Ctrl+C to stop playback.")
                
                if self.path_recorder.play_path(path_name, speed):
                    # Wait for playback to complete
                    while self.path_recorder.is_playing:
                        time.sleep(0.5)
                    print("Playback completed.")
                else:
                    print("Failed to start playback.")
            else:
                print("Invalid path number.")
        except (ValueError, KeyboardInterrupt):
            print("Playback cancelled.")
            if self.path_recorder.is_playing:
                self.path_recorder.stop_playback()
    
    def _delete_path_interactive(self):
        """Delete path in interactive mode"""
        paths = self.path_recorder.list_paths()
        if not paths:
            print("No recorded paths found.")
            return
        
        self._list_paths_interactive()
        
        try:
            choice = int(input("\nEnter path number to delete: ")) - 1
            if 0 <= choice < len(paths):
                path_name = paths[choice]['name']
                confirm = input(f"Are you sure you want to delete '{path_name}'? (y/N): ").strip().lower()
                if confirm == 'y':
                    if self.path_recorder.delete_path(path_name):
                        print(f"Path '{path_name}' deleted successfully.")
                    else:
                        print(f"Failed to delete path '{path_name}'.")
                else:
                    print("Deletion cancelled.")
            else:
                print("Invalid path number.")
        except ValueError:
            print("Invalid input.")
    
    def _manual_step_playback(self):
        """Manual step-through path playback"""
        paths = self.path_recorder.list_paths()
        if not paths:
            print("No recorded paths found.")
            return
        
        self._list_paths_interactive()
        
        try:
            choice = int(input("\nEnter path number for manual step-through: ")) - 1
            if 0 <= choice < len(paths):
                path_name = paths[choice]['name']
                print(f"\n🎯 Manual Step-Through: {path_name}")
                print("=" * 50)
                print("The system will move to each datapoint and wait for your input.")
                print("You can:")
                print("- Press Enter to continue to next datapoint")
                print("- Type 'q' and Enter to quit")
                print("- Use Ctrl+C to emergency stop")
                print()
                
                confirm = input("Start manual step-through? (y/N): ").strip().lower()
                if confirm == 'y':
                    if self.path_recorder.play_path(path_name, 1.0, manual_step=True):
                        print("Manual step-through started...")
                        # Wait for playback to complete
                        while self.path_recorder.is_playing:
                            time.sleep(0.5)
                        print("Manual step-through completed.")
                    else:
                        print("Failed to start manual step-through.")
                else:
                    print("Manual step-through cancelled.")
            else:
                print("Invalid path number.")
        except (ValueError, KeyboardInterrupt):
            print("Manual step-through cancelled.")
            if self.path_recorder.is_playing:
                self.path_recorder.stop_playback()
    
    def list_recorded_paths(self):
        """List all recorded paths (command line mode)"""
        if not self.controller:
            self.controller = TVArmController(self.config)
        
        self.path_recorder = PathRecorder(self.controller, self.config)
        paths = self.path_recorder.list_paths()
        
        if not paths:
            print("No recorded paths found.")
            return
        
        print(f"Found {len(paths)} recorded paths:")
        print("-" * 80)
        print("Name".ljust(20) + "Duration".ljust(12) + "Points".ljust(8) + "Recorded At")
        print("-" * 80)
        
        for path in paths:
            name = path['name'][:19]
            duration = f"{path['duration']:.1f}s"
            points = str(path['point_count'])
            recorded_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path['recorded_at']))
            print(name.ljust(20) + duration.ljust(12) + points.ljust(8) + recorded_time)
    
    def play_recorded_path(self, path_name: str):
        """Play a specific recorded path (command line mode)"""
        if not self.controller:
            self.controller = TVArmController(self.config)
            self.controller.start(teaching_mode=True)  # Use teaching mode to prevent auto-movement
        
        self.path_recorder = PathRecorder(self.controller, self.config)
        
        print(f"Playing recorded path: {path_name}")
        print("Press Ctrl+C to stop playback.")
        
        try:
            if self.path_recorder.play_path(path_name):
                # Wait for playback to complete
                while self.path_recorder.is_playing:
                    time.sleep(0.5)
                print("Playback completed.")
            else:
                print(f"Failed to play path '{path_name}'. Check if the path exists.")
        except KeyboardInterrupt:
            print("\nPlayback stopped by user.")
            self.path_recorder.stop_playback()
        finally:
            self.controller.stop()


def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown"""
    logging.info(f"Received signal {signum}, shutting down...")
    if hasattr(signal_handler, 'app') and signal_handler.app:
        signal_handler.app.stop()
    sys.exit(0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='TV Arm Controller with Home Assistant Integration')
    parser.add_argument('--config', default='config.yaml', 
                       help='Configuration file path (default: config.yaml)')
    parser.add_argument('--calibrate', action='store_true', 
                       help='Run calibration mode and exit')
    parser.add_argument('--test', action='store_true', 
                       help='Run test sequence and exit')
    parser.add_argument('--teach', action='store_true',
                       help='Run interactive teaching mode')
    parser.add_argument('--list-paths', action='store_true',
                       help='List all recorded paths and exit')
    parser.add_argument('--play-path', type=str,
                       help='Play a specific recorded path and exit')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (no interactive output)')
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not Path(args.config).exists():
        print(f"Configuration file not found: {args.config}")
        print("Please create a config.yaml file or specify a different path with --config")
        sys.exit(1)
    
    # Create application
    app = TVArmApplication(args.config)
    
    # Set up signal handlers for graceful shutdown
    signal_handler.app = app
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.calibrate:
            # Calibration mode
            print("=" * 50)
            print("TV ARM CONTROLLER - CALIBRATION MODE")
            print("=" * 50)
            print()
            print("This will move the servos to their extreme positions")
            print("to calibrate the potentiometer readings.")
            print()
            input("Make sure the TV arm can move freely, then press Enter to continue...")
            
            calibration_data = app.run_calibration()
            
            if calibration_data:
                print("\nCalibration Results:")
                print("-" * 30)
                for axis, data in calibration_data.items():
                    min_v = data.get('min_voltage', 'N/A')
                    max_v = data.get('max_voltage', 'N/A')
                    print(f"{axis.upper()}: Min={min_v:.3f}V, Max={max_v:.3f}V")
                
                print("\nUpdate your config.yaml with these values:")
                print("hardware:")
                print("  calibration:")
                for axis, data in calibration_data.items():
                    min_v = data.get('min_voltage', 0.1)
                    max_v = data.get('max_voltage', 3.2)
                    print(f"    {axis}:")
                    print(f"      min_voltage: {min_v:.3f}")
                    print(f"      max_voltage: {max_v:.3f}")
            else:
                print("Calibration failed. Check the logs for details.")
                sys.exit(1)
        
        elif args.test:
            # Test mode
            print("=" * 50)
            print("TV ARM CONTROLLER - TEST MODE")
            print("=" * 50)
            print()
            print("This will move the TV arm through a test sequence.")
            print()
            input("Make sure the TV arm can move freely, then press Enter to continue...")
            
            app.run_test_sequence()
        
        elif args.teach:
            # Teaching mode
            print("=" * 50)
            print("TV ARM CONTROLLER - TEACHING MODE")
            print("=" * 50)
            print()
            print("In teaching mode, you can:")
            print("1. Manually move the TV arm to record a path")
            print("2. Play back recorded paths")
            print("3. List and manage recorded paths")
            print()
            
            app.run_teaching_mode()
        
        elif args.list_paths:
            # List paths mode
            app.list_recorded_paths()
        
        elif args.play_path:
            # Play specific path mode
            app.play_recorded_path(args.play_path)
            
        else:
            # Normal operation mode
            if not args.daemon:
                print("=" * 50)
                print("TV ARM CONTROLLER - STARTING")
                print("=" * 50)
                print()
            
            # Start the application
            if app.start():
                if not args.daemon:
                    print("TV Arm Controller is running.")
                    print("- Check Home Assistant for the new TV Arm device")
                    print("- Monitor logs for debugging information")
                    print("- Press Ctrl+C to stop")
                    print()
                
                # Main loop
                while app.is_running():
                    time.sleep(1)
            else:
                print("Failed to start TV Arm Controller. Check the logs for details.")
                sys.exit(1)
    
    except KeyboardInterrupt:
        if not args.daemon:
            print("\nShutdown requested by user...")
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")
        print(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        app.stop()
        if not args.daemon:
            print("TV Arm Controller stopped.")


if __name__ == "__main__":
    main()

