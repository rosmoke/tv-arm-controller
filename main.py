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


class TVArmApplication:
    """Main application class that coordinates hardware and Home Assistant integration"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.controller = None
        self.ha_integration = None
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
        
        # Register command handlers
        self.ha_integration.set_command_handler('open', handle_open)
        self.ha_integration.set_command_handler('close', handle_close)
        self.ha_integration.set_command_handler('stop', handle_stop)
        self.ha_integration.set_command_handler('set_position', handle_set_position)
        self.ha_integration.set_command_handler('set_x_position', handle_set_x_position)
        self.ha_integration.set_command_handler('set_y_position', handle_set_y_position)
        
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

