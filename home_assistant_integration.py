#!/usr/bin/env python3
"""
Home Assistant MQTT Integration for TV Arm Controller
Provides MQTT discovery and control interface for Home Assistant
"""

import json
import logging
import threading
import time
from typing import Optional, Callable

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("paho-mqtt not available, running without MQTT support")
    mqtt = None


class HomeAssistantMQTT:
    """Home Assistant MQTT integration with auto-discovery"""
    
    def __init__(self, config: dict, position_callback: Optional[Callable] = None):
        self.config = config
        self.mqtt_config = config['home_assistant']['mqtt']
        self.device_config = config['home_assistant']['device']
        self.topics = config['home_assistant']['topics']
        
        self.client = None
        self.connected = False
        self.position_callback = position_callback
        self.publish_thread = None
        self.running = False
        
        # Current state
        self.current_x_position = 50.0
        self.current_y_position = 50.0
        self.cover_state = "stopped"  # open, closed, opening, closing, stopped
        self.cover_position = 50
        
        # Command handlers
        self.command_handlers = {}
        
        if mqtt:
            self._setup_mqtt_client()
        else:
            logging.warning("MQTT not available - Home Assistant integration disabled")
    
    def _setup_mqtt_client(self):
        """Initialize MQTT client"""
        try:
            self.client = mqtt.Client(client_id=self.mqtt_config['client_id'])
            
            # Set credentials if provided
            if self.mqtt_config.get('username') and self.mqtt_config.get('password'):
                self.client.username_pw_set(
                    self.mqtt_config['username'], 
                    self.mqtt_config['password']
                )
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            logging.info("MQTT client configured")
            
        except Exception as e:
            logging.error(f"Failed to setup MQTT client: {e}")
            self.client = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.connected = True
            logging.info(f"Connected to MQTT broker at {self.mqtt_config['broker']}:{self.mqtt_config['port']}")
            
            # Subscribe to command topics
            command_topics = [
                self.topics['command'],
                self.topics['x_position'], 
                self.topics['y_position']
            ]
            
            for topic in command_topics:
                client.subscribe(topic)
                logging.debug(f"Subscribed to {topic}")
            
            # Send discovery messages
            self._send_discovery_messages()
            
            # Send initial state
            self._publish_initial_state()
            
        else:
            self.connected = False
            logging.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.connected = False
        if rc != 0:
            logging.warning(f"Unexpected MQTT disconnection, return code {rc}")
        else:
            logging.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logging.debug(f"Received MQTT message: {topic} = {payload}")
            
            if topic == self.topics['command']:
                self._handle_cover_command(payload)
            elif topic == self.topics['x_position']:
                self._handle_x_position_command(payload)
            elif topic == self.topics['y_position']:
                self._handle_y_position_command(payload)
            else:
                logging.warning(f"Received message on unknown topic: {topic}")
                
        except Exception as e:
            logging.error(f"Error handling MQTT message: {e}")
    
    def _handle_cover_command(self, command: str):
        """Handle cover entity commands"""
        logging.info(f"Received cover command: {command}")
        
        if command == "OPEN":
            # Move to fully open position (could be defined as specific X,Y coordinates)
            self.cover_state = "opening"
            self._publish_cover_state()
            if 'open' in self.command_handlers:
                self.command_handlers['open']()
            
        elif command == "CLOSE":
            # Move to fully closed position
            self.cover_state = "closing"
            self._publish_cover_state()
            if 'close' in self.command_handlers:
                self.command_handlers['close']()
            
        elif command == "STOP":
            # Stop movement
            self.cover_state = "stopped"
            self._publish_cover_state()
            if 'stop' in self.command_handlers:
                self.command_handlers['stop']()
        
        elif command.startswith("SET_POSITION"):
            # Handle position command (e.g., "SET_POSITION 75")
            try:
                parts = command.split()
                if len(parts) == 2:
                    position = int(parts[1])
                    self.cover_position = max(0, min(100, position))
                    self.cover_state = "opening" if position > self.cover_position else "closing"
                    self._publish_cover_state()
                    if 'set_position' in self.command_handlers:
                        self.command_handlers['set_position'](position)
            except ValueError:
                logging.error(f"Invalid position command: {command}")
    
    def _handle_x_position_command(self, value: str):
        """Handle X-axis position command"""
        try:
            x_position = float(value)
            x_position = max(0.0, min(100.0, x_position))
            logging.info(f"Received X position command: {x_position}%")
            
            if 'set_x_position' in self.command_handlers:
                self.command_handlers['set_x_position'](x_position)
                
        except ValueError:
            logging.error(f"Invalid X position value: {value}")
    
    def _handle_y_position_command(self, value: str):
        """Handle Y-axis position command"""
        try:
            y_position = float(value)
            y_position = max(0.0, min(100.0, y_position))
            logging.info(f"Received Y position command: {y_position}%")
            
            if 'set_y_position' in self.command_handlers:
                self.command_handlers['set_y_position'](y_position)
                
        except ValueError:
            logging.error(f"Invalid Y position value: {value}")
    
    def _send_discovery_messages(self):
        """Send Home Assistant MQTT discovery messages"""
        if not self.connected:
            return
        
        device_info = {
            "identifiers": [self.device_config['identifier']],
            "name": self.device_config['name'],
            "manufacturer": self.device_config['manufacturer'],
            "model": self.device_config['model'],
            "sw_version": self.device_config['sw_version']
        }
        
        # Cover entity (main TV arm control)
        cover_config = {
            "name": "TV Arm",
            "unique_id": "tv_arm_cover",
            "device": device_info,
            "command_topic": self.topics['command'],
            "state_topic": self.topics['state'],
            "position_topic": self.topics['position'],
            "set_position_topic": self.topics['command'],
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "state_open": "open",
            "state_closed": "closed",
            "state_opening": "opening",
            "state_closing": "closing",
            "state_stopped": "stopped",
            "position_open": 100,
            "position_closed": 0,
            "device_class": "curtain",
            "optimistic": False
        }
        
        cover_discovery_topic = f"homeassistant/cover/tv_arm/config"
        self.client.publish(cover_discovery_topic, json.dumps(cover_config), retain=True)
        
        # X-axis position number entity
        x_position_config = {
            "name": "TV Arm X Position",
            "unique_id": "tv_arm_x_position",
            "device": device_info,
            "command_topic": self.topics['x_position'],
            "state_topic": self.topics['x_state'],
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
            "icon": "mdi:arrow-left-right",
            "mode": "slider"
        }
        
        x_discovery_topic = f"homeassistant/number/tv_arm_x/config"
        self.client.publish(x_discovery_topic, json.dumps(x_position_config), retain=True)
        
        # Y-axis position number entity
        y_position_config = {
            "name": "TV Arm Y Position",
            "unique_id": "tv_arm_y_position", 
            "device": device_info,
            "command_topic": self.topics['y_position'],
            "state_topic": self.topics['y_state'],
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
            "icon": "mdi:arrow-up-down",
            "mode": "slider"
        }
        
        y_discovery_topic = f"homeassistant/number/tv_arm_y/config"
        self.client.publish(y_discovery_topic, json.dumps(y_position_config), retain=True)
        
        logging.info("Sent Home Assistant discovery messages")
    
    def _publish_initial_state(self):
        """Publish initial state to Home Assistant"""
        if not self.connected:
            return
        
        # Publish cover state
        self._publish_cover_state()
        
        # Publish position states
        self.client.publish(self.topics['x_state'], str(int(self.current_x_position)))
        self.client.publish(self.topics['y_state'], str(int(self.current_y_position)))
        
        logging.info("Published initial state to Home Assistant")
    
    def _publish_cover_state(self):
        """Publish cover state and position"""
        if not self.connected:
            return
        
        self.client.publish(self.topics['state'], self.cover_state)
        self.client.publish(self.topics['position'], str(self.cover_position))
    
    def _publish_position_states(self):
        """Publish X and Y position states"""
        if not self.connected:
            return
        
        self.client.publish(self.topics['x_state'], str(int(self.current_x_position)))
        self.client.publish(self.topics['y_state'], str(int(self.current_y_position)))
    
    def _publish_loop(self):
        """Background thread to publish state updates"""
        publish_interval = self.config['system']['mqtt_publish_interval']
        
        while self.running:
            try:
                if self.connected:
                    # Update cover position based on average of X,Y positions
                    avg_position = int((self.current_x_position + self.current_y_position) / 2)
                    if avg_position != self.cover_position:
                        self.cover_position = avg_position
                        self._publish_cover_state()
                    
                    # Publish individual position states
                    self._publish_position_states()
                
                time.sleep(publish_interval)
                
            except Exception as e:
                logging.error(f"Error in MQTT publish loop: {e}")
                time.sleep(5)
    
    def set_command_handler(self, command: str, handler: Callable):
        """Set command handler function"""
        self.command_handlers[command] = handler
        logging.debug(f"Set command handler for '{command}'")
    
    def update_position(self, x_position: float, y_position: float):
        """Update current position (called by main controller)"""
        self.current_x_position = x_position
        self.current_y_position = y_position
        
        # Update cover state based on movement
        # This is a simple state machine - you might want to make it more sophisticated
        tolerance = self.config['system']['position_tolerance']
        
        # Check if we're at target positions (this would need to be passed in)
        # For now, just set to stopped if position is stable
        self.cover_state = "stopped"
    
    def set_cover_state(self, state: str):
        """Manually set cover state"""
        valid_states = ["open", "closed", "opening", "closing", "stopped"]
        if state in valid_states:
            self.cover_state = state
            if self.connected:
                self._publish_cover_state()
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        if not self.client:
            logging.error("MQTT client not initialized")
            return False
        
        try:
            self.client.connect(
                self.mqtt_config['broker'], 
                self.mqtt_config['port'], 
                60
            )
            
            # Start MQTT loop in background
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            return self.connected
            
        except Exception as e:
            logging.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def start(self) -> bool:
        """Start the Home Assistant integration"""
        if not mqtt:
            logging.warning("MQTT not available - cannot start Home Assistant integration")
            return False
        
        if self.running:
            return True
        
        logging.info("Starting Home Assistant MQTT integration...")
        
        # Connect to MQTT broker
        if not self.connect():
            logging.error("Failed to connect to MQTT broker")
            return False
        
        # Start background publish thread
        self.running = True
        self.publish_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.publish_thread.start()
        
        logging.info("Home Assistant integration started")
        return True
    
    def stop(self):
        """Stop the Home Assistant integration"""
        if not self.running:
            return
        
        logging.info("Stopping Home Assistant MQTT integration...")
        self.running = False
        
        # Stop publish thread
        if self.publish_thread and self.publish_thread.is_alive():
            self.publish_thread.join(timeout=2)
        
        # Disconnect from MQTT
        if self.client and self.connected:
            self.client.loop_stop()
            self.client.disconnect()
        
        self.connected = False
        logging.info("Home Assistant integration stopped")
    
    def is_connected(self) -> bool:
        """Check if connected to MQTT broker"""
        return self.connected


if __name__ == "__main__":
    import yaml
    import sys
    
    # Test the Home Assistant integration
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Set up logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create integration
    ha_integration = HomeAssistantMQTT(config)
    
    # Set up test command handlers
    def test_open():
        print("OPEN command received")
        ha_integration.set_cover_state("opening")
        time.sleep(2)
        ha_integration.set_cover_state("open")
    
    def test_close():
        print("CLOSE command received")
        ha_integration.set_cover_state("closing")
        time.sleep(2)
        ha_integration.set_cover_state("closed")
    
    def test_stop():
        print("STOP command received")
        ha_integration.set_cover_state("stopped")
    
    def test_set_x_position(x):
        print(f"Set X position to {x}%")
        ha_integration.update_position(x, ha_integration.current_y_position)
    
    def test_set_y_position(y):
        print(f"Set Y position to {y}%")
        ha_integration.update_position(ha_integration.current_x_position, y)
    
    # Register handlers
    ha_integration.set_command_handler('open', test_open)
    ha_integration.set_command_handler('close', test_close)
    ha_integration.set_command_handler('stop', test_stop)
    ha_integration.set_command_handler('set_x_position', test_set_x_position)
    ha_integration.set_command_handler('set_y_position', test_set_y_position)
    
    # Start integration
    if ha_integration.start():
        print("Home Assistant integration test running. Press Ctrl+C to exit.")
        try:
            # Simulate position changes
            while True:
                import random
                x = random.uniform(0, 100)
                y = random.uniform(0, 100)
                ha_integration.update_position(x, y)
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
    else:
        print("Failed to start Home Assistant integration")
    
    ha_integration.stop()
    print("Test completed")

