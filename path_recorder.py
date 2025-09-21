#!/usr/bin/env python3
"""
Path Recorder - Teaching and Playback System
Records manual movements and replays them automatically
"""

import time
import json
import logging
import threading
from typing import List, Dict, Tuple, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class PathPoint:
    """Represents a single point in a recorded path"""
    timestamp: float
    x_position: float
    y_position: float
    duration_from_start: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PathPoint':
        return cls(**data)


class PathRecorder:
    """Handles recording and playback of TV arm movement paths"""
    
    def __init__(self, controller, config: dict):
        self.controller = controller
        self.config = config
        
        # Recording state
        self.is_recording = False
        self.is_playing = False
        self.current_path: List[PathPoint] = []
        self.recording_start_time = 0.0
        self.recording_thread = None
        self.playback_thread = None
        
        # Callbacks
        self.recording_callback: Optional[Callable] = None
        self.playback_callback: Optional[Callable] = None
        
        # Configuration
        self.recording_interval = config.get('path_recording', {}).get('recording_interval', 0.1)
        self.position_tolerance = config.get('path_recording', {}).get('position_tolerance', 1.0)
        self.paths_directory = Path(config.get('path_recording', {}).get('paths_directory', 'recorded_paths'))
        
        # Ensure paths directory exists
        self.paths_directory.mkdir(exist_ok=True)
        
        logging.info(f"Path Recorder initialized - recording interval: {self.recording_interval}s")
    
    def set_recording_callback(self, callback: Callable):
        """Set callback for recording status updates"""
        self.recording_callback = callback
    
    def set_playback_callback(self, callback: Callable):
        """Set callback for playback status updates"""
        self.playback_callback = callback
    
    def start_recording(self, path_name: str = None) -> bool:
        """Start recording a new path"""
        if self.is_recording:
            logging.warning("Already recording a path")
            return False
        
        if self.is_playing:
            logging.warning("Cannot start recording while playing back a path")
            return False
        
        if not path_name:
            path_name = f"path_{int(time.time())}"
        
        logging.info(f"Starting path recording: {path_name}")
        
        # Reset recording state
        self.current_path = []
        self.recording_start_time = time.time()
        self.is_recording = True
        self.current_path_name = path_name
        
        # Start recording thread
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()
        
        if self.recording_callback:
            self.recording_callback("started", path_name, len(self.current_path))
        
        return True
    
    def stop_recording(self) -> bool:
        """Stop recording and save the current path"""
        if not self.is_recording:
            logging.warning("Not currently recording")
            return False
        
        logging.info(f"Stopping path recording: {self.current_path_name}")
        self.is_recording = False
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2)
        
        # Save the recorded path
        if len(self.current_path) > 0:
            success = self.save_path(self.current_path_name, self.current_path)
            if success:
                logging.info(f"Path recorded successfully: {len(self.current_path)} points over {self.current_path[-1].duration_from_start:.1f}s")
                if self.recording_callback:
                    self.recording_callback("completed", self.current_path_name, len(self.current_path))
                return True
            else:
                logging.error("Failed to save recorded path")
                if self.recording_callback:
                    self.recording_callback("error", self.current_path_name, len(self.current_path))
                return False
        else:
            logging.warning("No path data recorded")
            if self.recording_callback:
                self.recording_callback("empty", self.current_path_name, 0)
            return False
    
    def _recording_loop(self):
        """Background thread that records position data"""
        last_x, last_y = None, None
        
        while self.is_recording:
            try:
                # Get current position from controller
                current_x, current_y = self.controller.get_current_position()
                current_time = time.time()
                duration = current_time - self.recording_start_time
                
                # Only record if position changed significantly
                if (last_x is None or last_y is None or 
                    abs(current_x - last_x) > self.position_tolerance or 
                    abs(current_y - last_y) > self.position_tolerance):
                    
                    point = PathPoint(
                        timestamp=current_time,
                        x_position=current_x,
                        y_position=current_y,
                        duration_from_start=duration
                    )
                    
                    self.current_path.append(point)
                    last_x, last_y = current_x, current_y
                    
                    logging.debug(f"Recorded point: X={current_x:.1f}%, Y={current_y:.1f}% at {duration:.1f}s")
                    
                    if self.recording_callback:
                        self.recording_callback("recording", self.current_path_name, len(self.current_path))
                
                time.sleep(self.recording_interval)
                
            except Exception as e:
                logging.error(f"Error in recording loop: {e}")
                time.sleep(0.5)
    
    def play_path(self, path_name: str, speed_multiplier: float = 1.0, manual_step: bool = False) -> bool:
        """Play back a recorded path"""
        if self.is_playing:
            logging.warning("Already playing back a path")
            return False
        
        if self.is_recording:
            logging.warning("Cannot start playback while recording")
            return False
        
        # Load the path
        path_data = self.load_path(path_name)
        if not path_data:
            logging.error(f"Failed to load path: {path_name}")
            return False
        
        mode_desc = "manual step-through" if manual_step else "automatic"
        logging.info(f"Starting path playback: {path_name} ({len(path_data)} points, speed: {speed_multiplier}x, mode: {mode_desc})")
        
        self.is_playing = True
        self.current_playback_path = path_data
        self.current_path_name = path_name  # Store path name for skip logic
        self.playback_speed = speed_multiplier
        self.manual_step_mode = manual_step
        
        # Start playback thread
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()
        
        if self.playback_callback:
            self.playback_callback("started", path_name, len(path_data))
        
        return True
    
    def stop_playback(self) -> bool:
        """Stop current path playback"""
        if not self.is_playing:
            logging.warning("Not currently playing back a path")
            return False
        
        logging.info("Stopping path playback")
        self.is_playing = False
        
        # Wait for playback thread to finish
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2)
        
        if self.playback_callback:
            self.playback_callback("stopped", "", 0)
        
        return True
    
    def _playback_loop(self):
        """Background thread that plays back recorded path with step-by-step verification"""
        try:
            # Slightly more forgiving tolerances - X motor struggles with final 0.1%
            # Y motor is achieving perfect precision, X needs a bit more tolerance
            x_tolerance = 0.5   # 0.5% tolerance for X axis (was 0.3% but motor stops at 0.4% error)
            y_tolerance = 0.08  # 0.08% tolerance for Y axis (perfect precision achieved)
            max_wait_per_point = 35.0  # Extended timeout for Y motor to fully reach targets
            
            for i, point in enumerate(self.current_playback_path):
                if not self.is_playing:
                    break
                
                target_x = point.x_position
                target_y = point.y_position
                
                # Check if we should skip this datapoint (correct skip logic)
                current_x, current_y = self.controller.get_current_position()
                
                # Track the actual datapoint number we're working on (1-based)
                actual_datapoint_number = point.point_number if hasattr(point, 'point_number') else i + 1
                
                # For extend path: skip if current position is ALREADY PAST this datapoint
                # For retract path: skip if current position is ALREADY PAST this datapoint  
                path_name = getattr(self, 'current_path_name', '').lower()
                
                should_skip = False
                if 'extend' in path_name:
                    # EXTEND: Skip if we're already extended past this datapoint (both X AND Y past target)
                    if current_x > target_x and current_y > target_y:
                        should_skip = True
                        logging.info(f"🔄 SKIPPING DATAPOINT {actual_datapoint_number}: Already extended past X={target_x:.1f}%, Y={target_y:.1f}% (current: X={current_x:.1f}%, Y={current_y:.1f}%)")
                elif 'retract' in path_name:
                    # RETRACT: Skip if we're already retracted past this datapoint (both X AND Y past target)
                    if current_x < target_x and current_y < target_y:
                        should_skip = True
                        logging.info(f"🔄 SKIPPING DATAPOINT {actual_datapoint_number}: Already retracted past X={target_x:.1f}%, Y={target_y:.1f}% (current: X={current_x:.1f}%, Y={current_y:.1f}%)")
                
                if should_skip:
                    continue
                
                logging.info(f"=== DATAPOINT {actual_datapoint_number}/{len(self.current_playback_path)} ===")
                logging.info(f"Target: X={target_x:.1f}%, Y={target_y:.1f}%")
                
                # Reset motor lock flags for new datapoint
                x_was_stopped = hasattr(self, 'x_stopped') and self.x_stopped
                y_was_stopped = hasattr(self, 'y_stopped') and self.y_stopped
                
                if hasattr(self, 'x_stopped'):
                    delattr(self, 'x_stopped')
                if hasattr(self, 'y_stopped'):
                    delattr(self, 'y_stopped')
                if hasattr(self, 'x_last_position'):
                    delattr(self, 'x_last_position')
                if hasattr(self, 'y_last_position'):
                    delattr(self, 'y_last_position')
                if hasattr(self, 'x_last_valid_position'):
                    delattr(self, 'x_last_valid_position')
                if hasattr(self, 'y_last_valid_position'):
                    delattr(self, 'y_last_valid_position')
                
                logging.info(f"🔄 Reset motor flags: X was {'LOCKED' if x_was_stopped else 'FREE'}, Y was {'LOCKED' if y_was_stopped else 'FREE'} -> both now FREE")
                
                # Adjust tolerances for very small targets to improve accuracy
                adjusted_x_tolerance = x_tolerance
                adjusted_y_tolerance = y_tolerance
                
                # For targets near 0%, use tighter tolerance for better accuracy
                if target_x <= 1.0:
                    adjusted_x_tolerance = 0.1  # Tighter tolerance for X near 0%
                    logging.info(f"🎯 X NEAR ZERO: Using tight tolerance {adjusted_x_tolerance}% for target {target_x}% (normal: {x_tolerance}%)")
                
                if target_y <= 1.0:
                    adjusted_y_tolerance = 0.1  # Tighter tolerance for Y near 0%  
                    logging.info(f"🎯 Y NEAR ZERO: Using tight tolerance {adjusted_y_tolerance}% for target {target_y}% (normal: {y_tolerance}%)")
                
                # Only log tolerances if they seem unusual
                if adjusted_x_tolerance > 1.0 or adjusted_y_tolerance > 1.0:
                    logging.warning(f"🎯 UNUSUAL TOLERANCES: X={adjusted_x_tolerance}%, Y={adjusted_y_tolerance}% for targets X={target_x}%, Y={target_y}%")
                
                # Move both axes simultaneously
                success = self._move_to_position_simultaneous(
                    target_x, target_y, adjusted_x_tolerance, adjusted_y_tolerance, max_wait_per_point
                )
                
                if not success:
                    logging.warning(f"Failed to reach datapoint X={target_x:.1f}%, Y={target_y:.1f}%")
                    break
                
                # Both axes reached target
                current_x, current_y = self.controller.get_current_position()
                logging.info(f"✅ REACHED DATAPOINT {actual_datapoint_number}: X={current_x:.1f}%, Y={current_y:.1f}%")
                
                if self.playback_callback:
                    self.playback_callback("playing", "", i + 1)
                
                # Manual step mode - wait for user input
                if hasattr(self, 'manual_step_mode') and self.manual_step_mode:
                    if i + 1 < len(self.current_playback_path):  # Not the last point
                        next_point = self.current_playback_path[i + 1]
                        print("\n" + "="*60)
                        # Get the next datapoint's actual number
                        next_datapoint_number = next_point.point_number if hasattr(next_point, 'point_number') else i + 2
                        print(f"🎯 REACHED DATAPOINT {actual_datapoint_number}/{len(self.current_playback_path)}")
                        print(f"Current: X={current_x:.1f}%, Y={current_y:.1f}%")
                        print(f"Next target: DATAPOINT {next_datapoint_number} - X={next_point.x_position:.1f}%, Y={next_point.y_position:.1f}%")
                        print("="*60)
                        print("Press Enter to continue to next datapoint, or 'q' to quit...")
                        print(">>> ", end="", flush=True)
                        
                        try:
                            user_input = input().strip().lower()
                            if user_input == 'q':
                                logging.info("Manual step playback stopped by user")
                                self.is_playing = False
                                break
                            else:
                                print("Continuing to next datapoint...")
                        except EOFError:
                            # Handle case where input is not available
                            logging.info("No input available, continuing automatically")
                            time.sleep(1.0)
                    else:
                        print("\n" + "="*60)
                        print(f"🎉 COMPLETED! Reached final datapoint {actual_datapoint_number}/{len(self.current_playback_path)}")
                        print(f"Final position: X={current_x:.1f}%, Y={current_y:.1f}%")
                        print("="*60)
                else:
                    logging.info(f"Proceeding to next datapoint...")
                    # Small pause between datapoints in automatic mode
                    time.sleep(0.5)
            
            # Stop both motors at end of path
            logging.info("Stopping both motors at end of path...")
            self.controller.x_motor.stop_motor()
            self.controller.y_motor.stop_motor()
            
            self.is_playing = False
            logging.info("🎉 Path playback completed successfully - motors stopped")
            
            if self.playback_callback:
                self.playback_callback("completed", "", len(self.current_playback_path))
                
        except Exception as e:
            logging.error(f"Error in playback loop: {e}")
            self.is_playing = False
            if self.playback_callback:
                self.playback_callback("error", "", 0)
    
    def _move_to_position_with_verification(self, axis: str, target: float, tolerance: float, max_wait: float) -> bool:
        """Move a single axis to target position with verification"""
        start_time = time.time()
        consecutive_good_readings = 0
        required_readings = 2
        
        logging.info(f"{axis}: Starting movement to {target:.1f}%")
        
        while time.time() - start_time < max_wait:
            if not self.is_playing:
                return False
            
            try:
                # Get current position with timeout protection
                logging.info(f"{axis}: Reading current position...")
                current_x, current_y = self.controller.get_current_position()
                current = current_x if axis == 'X' else current_y
                
                error = abs(current - target)
                logging.info(f"{axis}: Current={current:.1f}%, Target={target:.1f}%, Error={error:.1f}%")
                
                # Check if within tolerance
                if error <= tolerance:
                    consecutive_good_readings += 1
                    logging.info(f"{axis}: ✅ Within tolerance ({consecutive_good_readings}/{required_readings} checks)")
                    
                    if consecutive_good_readings >= required_readings:
                        logging.info(f"{axis}: 🎯 Position confirmed!")
                        # Stop the motor for this axis
                        if axis == 'X':
                            self.controller.x_motor.stop_motor()
                        else:
                            self.controller.y_motor.stop_motor()
                        return True
                        
                    time.sleep(1.0)  # Wait longer before next check
                else:
                    consecutive_good_readings = 0
                    
                    # Send movement command
                    logging.info(f"{axis}: Sending move command to {target:.1f}%")
                    if axis == 'X':
                        self.controller.set_x_position(target, use_closed_loop=False)  # Use open-loop to avoid nested loops
                    else:
                        self.controller.set_y_position(target, use_closed_loop=False)
                    
                    time.sleep(3.0)  # Wait much longer for motor movement
                    
            except Exception as e:
                logging.error(f"{axis}: Error during position verification: {e}")
                time.sleep(0.5)
        
        # Timeout
        try:
            current_x, current_y = self.controller.get_current_position()
            current = current_x if axis == 'X' else current_y
            logging.warning(f"{axis}: ⏰ Timeout - Current={current:.1f}%, Target={target:.1f}%")
        except Exception as e:
            logging.error(f"{axis}: Error reading final position: {e}")
        return False
    
    def _move_to_position_simultaneous(self, target_x: float, target_y: float, x_tolerance: float, y_tolerance: float, max_wait: float) -> bool:
        """Move both X and Y axes simultaneously to target position"""
        start_time = time.time()
        consecutive_good_readings = 0
        required_readings = 1  # Only need 1 good reading with tight tolerances and glitch filtering
        
        logging.info(f"Moving both axes simultaneously: X→{target_x:.1f}%, Y→{target_y:.1f}%")
        
        # Get starting position to determine expected direction
        start_x, start_y = self.controller.get_current_position()
        expected_x_direction = 1 if target_x > start_x else -1 if target_x < start_x else 0
        expected_y_direction = 1 if target_y > start_y else -1 if target_y < start_y else 0
        
        logging.info(f"Expected directions: X={'forward' if expected_x_direction > 0 else 'backward' if expected_x_direction < 0 else 'none'}, "
                    f"Y={'forward' if expected_y_direction > 0 else 'backward' if expected_y_direction < 0 else 'none'}")
        
        # Send initial movement commands to both motors with correct directions
        logging.info("Sending initial movement commands to both motors...")
        
        # Get current position to determine correct directions
        current_x, current_y = self.controller.get_current_position()
        
        # Set correct directions for X motor with detailed logging
        if target_x > current_x:
            self.controller.x_motor.set_direction_forward()
            logging.info(f"X direction: FORWARD ({current_x:.1f}% → {target_x:.1f}%) - EXTENDING")
        elif target_x < current_x:
            self.controller.x_motor.set_direction_reverse()
            logging.info(f"X direction: REVERSE ({current_x:.1f}% → {target_x:.1f}%) - RETRACTING")
        else:
            logging.info(f"X direction: NONE (already at {target_x:.1f}%)")
            
        # CRITICAL: Log the expected movement direction
        logging.info(f"X EXPECTED: {'INCREASE' if target_x > current_x else 'DECREASE' if target_x < current_x else 'STAY'} from {current_x:.1f}% to {target_x:.1f}%")
        
        # Set correct directions for Y motor
        if target_y > current_y:
            self.controller.y_motor.set_direction_forward()
            logging.info(f"Y direction: FORWARD ({current_y:.1f}% → {target_y:.1f}%)")
        elif target_y < current_y:
            self.controller.y_motor.set_direction_reverse()
            logging.info(f"Y direction: REVERSE ({current_y:.1f}% → {target_y:.1f}%)")
        else:
            logging.info(f"Y direction: NONE (already at {target_y:.1f}%)")
        
        # Set initial speeds
        self.controller.x_motor.set_speed(50.0)
        self.controller.y_motor.set_speed(50.0)
        
        logging.info(f"✅ Movement commands sent: X→{target_x:.1f}%, Y→{target_y:.1f}%")
        
        # Start monitoring immediately - no fixed delay
        logging.info("Starting position monitoring...")
        iteration_count = 0
        
        # Initialize position tracking for overshoot detection
        self.x_last_position = None
        self.y_last_position = None
        x_command_count = 0
        y_command_count = 0
        max_commands_per_axis = 15  # Emergency stop after 15 commands per axis (more attempts)

        while time.time() - start_time < max_wait:
            if not self.is_playing:
                return False
            
            iteration_count += 1
            try:
                # Get 3 sensor readings and use consensus to eliminate glitches
                readings_x = []
                readings_y = []
                
                for i in range(3):
                    try:
                        x_reading, y_reading = self.controller.get_current_position()
                        readings_x.append(x_reading)
                        readings_y.append(y_reading)
                        if i < 2:  # Small delay between readings
                            time.sleep(0.01)  # 10ms between readings
                    except Exception as e:
                        logging.warning(f"Sensor reading {i+1} failed: {e}")
                        continue
                
                # Use consensus of 3 readings - pick the two closest values and average them
                current_x = self._get_consensus_reading(readings_x, 'X')
                current_y = self._get_consensus_reading(readings_y, 'Y')
                
                x_error = abs(current_x - target_x)
                y_error = abs(current_y - target_y)
                
                # Check each axis independently - stop when reached OR OVERSHOT target
                x_at_target = self._is_axis_at_target(current_x, target_x, x_tolerance, 'X')
                y_at_target = self._is_axis_at_target(current_y, target_y, y_tolerance, 'Y')
                
                # TODO: Overshoot detection was causing false positives - disabled temporarily
                # The system was incorrectly detecting 1.8% as "overshot" from 51.0% target
                
                # Only log position every 20 iterations to reduce spam
                if iteration_count % 20 == 0 or x_at_target or y_at_target:
                    logging.info(f"Position: X={current_x:.1f}%→{target_x:.1f}% (Δ{x_error:.1f}%), Y={current_y:.1f}%→{target_y:.1f}% (Δ{y_error:.1f}%) [iter {iteration_count}]")
                
                # Stop motors that have reached their targets (but don't reset counter)
                if x_at_target and not hasattr(self, 'x_stopped'):
                    logging.info(f"🎯 X motor reached target {target_x:.1f}% (current: {current_x:.1f}%)")
                    self.controller.x_motor.stop_motor()
                    self.controller.x_motor.set_speed(0)
                    self.x_stopped = True
                elif hasattr(self, 'x_stopped') and self.x_stopped:
                    pass  # X already stopped - no need to log every iteration
                
                if y_at_target and not hasattr(self, 'y_stopped'):
                    logging.info(f"🎯 Y motor reached target {target_y:.1f}% (current: {current_y:.1f}%)")
                    self.controller.y_motor.stop_motor()
                    self.controller.y_motor.set_speed(0)
                    self.y_stopped = True
                
                # Check if both axes are at target
                if x_at_target and y_at_target:
                    consecutive_good_readings += 1
                    logging.info(f"✅ Both axes at target ({consecutive_good_readings}/{required_readings} checks)")
                    
                    if consecutive_good_readings >= required_readings:
                        logging.info(f"🎯 DATAPOINT SUCCESS! Both axes reached target: X={current_x:.1f}%→{target_x:.1f}%, Y={current_y:.1f}%→{target_y:.1f}%")
                        # Stop both motors to ensure they don't drift
                        self.controller.x_motor.stop_motor()
                        self.controller.x_motor.set_speed(0)
                        self.controller.y_motor.stop_motor()
                        self.controller.y_motor.set_speed(0)
                        logging.info("🛑 Both motors stopped - datapoint complete")
                        
                        # Reset flags for next datapoint
                        if hasattr(self, 'x_stopped'):
                            delattr(self, 'x_stopped')
                        if hasattr(self, 'y_stopped'):
                            delattr(self, 'y_stopped')
                        return True
                        
                    time.sleep(0.5)  # Shorter wait - we're very close to success
                else:
                    consecutive_good_readings = 0
                    
                    # Send correction commands only for axes that need adjustment
                    corrections_sent = False
                    
                    # Dynamic speed calculation based on distance to target - independent for X and Y
                    def calculate_x_approach_speed(x_error, base_speed):
                        """Calculate X motor speed based on distance to target - aggressive slowdown to prevent overshoot"""
                        if x_error <= 0.3:  # Within 0.3% of target - very slow for precision
                            approach_speed = base_speed * 0.3  # 30% speed when very close
                            logging.info(f"X PRECISION: {x_error:.2f}% error → {approach_speed:.0f}% speed (30% - preventing overshoot)")
                        elif x_error <= 1.0:  # Within 1% of target - slow down significantly  
                            approach_speed = base_speed * 0.5  # 50% speed when approaching
                            logging.info(f"X SLOW DOWN: {x_error:.2f}% error → {approach_speed:.0f}% speed (50% - approaching target)")
                        else:  # Far from target
                            approach_speed = base_speed  # Full speed
                        return approach_speed
                    
                    def calculate_y_approach_speed(y_error, base_speed):
                        """Calculate Y motor speed based on distance to target - aggressive slowdown to prevent overshoot"""
                        if y_error <= 0.08:  # Within 0.08% of target - very slow for precision
                            approach_speed = base_speed * 0.3  # 30% speed when very close
                            logging.info(f"Y PRECISION: {y_error:.2f}% error → {approach_speed:.0f}% speed (30% - preventing overshoot)")
                        elif y_error <= 0.3:  # Within 0.3% of target - slow down significantly
                            approach_speed = base_speed * 0.5  # 50% speed when approaching
                            logging.info(f"Y SLOW DOWN: {y_error:.2f}% error → {approach_speed:.0f}% speed (50% - approaching target)")
                        else:  # Far from target
                            approach_speed = base_speed  # Full speed
                        return approach_speed
                    
                    # Only send commands to X motor if it hasn't been stopped yet
                    if hasattr(self, 'x_stopped') and self.x_stopped:
                        if iteration_count % 50 == 0:  # Only log every 50 iterations to reduce spam
                            logging.info(f"X axis LOCKED: {current_x:.1f}% [iter {iteration_count}]")
                    elif x_error > x_tolerance and not x_at_target and not (hasattr(self, 'x_stopped') and self.x_stopped):
                        # Check if motor is moving in wrong direction (away from target)
                        if hasattr(self, 'x_last_position') and self.x_last_position is not None:
                            last_error = abs(self.x_last_position - target_x)
                            movement = abs(current_x - self.x_last_position)
                            
                            # Only check for major direction reversal (>5% movement in clearly wrong direction)
                            # Be very lenient for large movements - sensor glitches can cause false readings
                            # For large targets (>10% away), require substantial wrong movement to lock
                            if target_x > 10.0:  # Large movement targets - be very lenient
                                if movement > 5.0 and x_error > last_error + 3.0:  # Very lenient for large movements
                                    logging.warning(f"🚫 X MAJOR DIRECTION REVERSAL: {self.x_last_position:.1f}% → {current_x:.1f}% (moving away from {target_x:.1f}%)")
                                    logging.warning(f"   Last error: {last_error:.1f}%, Current error: {x_error:.1f}%, Movement: {movement:.1f}%")
                                    self.controller.x_motor.stop_motor()
                                    self.controller.x_motor.set_speed(0)
                                    self.x_stopped = True
                                    logging.warning(f"🔒 X MOTOR LOCKED due to direction reversal [iteration {iteration_count}]")
                                else:
                                    if iteration_count % 100 == 0:  # Reduce X continuing spam
                                        logging.info(f"⏳ X CONTINUING: {current_x:.1f}% → {target_x:.1f}% (large movement, allowing sensor variations)")
                            else:  # Small movement targets - be extremely lenient 
                                if movement > 10.0 and x_error > last_error + 5.0:  # VERY lenient - only catastrophic reversals
                                    logging.warning(f"🚫 X CATASTROPHIC REVERSAL: {self.x_last_position:.1f}% → {current_x:.1f}% (moving away from {target_x:.1f}%)")
                                    logging.warning(f"   Last error: {last_error:.1f}%, Current error: {x_error:.1f}%, Movement: {movement:.1f}%")
                                    self.controller.x_motor.stop_motor()
                                    self.controller.x_motor.set_speed(0)
                                    self.x_stopped = True
                                    logging.warning(f"🔒 X MOTOR LOCKED due to catastrophic reversal [iteration {iteration_count}]")
                                else:
                                    if iteration_count % 100 == 0:  # Reduce X continuing spam
                                        logging.info(f"⏳ X CONTINUING: {current_x:.1f}% → {target_x:.1f}% (error: {x_error:.1f}%, allowing all variations)")
                        else:
                            if iteration_count <= 5:  # Only log first few iterations
                                logging.info(f"⏳ X CONTINUING: {current_x:.1f}% → {target_x:.1f}% (error: {x_error:.1f}%, first check)")
                        # Send speed adjustment commands based on distance to target
                        base_x_speed = 50.0  # Default speed for X motor
                        new_x_speed = calculate_x_approach_speed(x_error, base_x_speed)
                        
                        # Determine direction for X motor
                        if target_x > current_x:
                            self.controller.x_motor.set_direction_forward()
                        else:
                            self.controller.x_motor.set_direction_reverse()
                        
                        self.controller.x_motor.set_speed(new_x_speed)
                        corrections_sent = True
                        
                        # Update last position for next check
                        self.x_last_position = current_x
                    elif x_at_target:
                        logging.info(f"X axis OK: {current_x:.1f}% (within {x_tolerance}% of {target_x:.1f}%)")
                    
                    # Only send commands to Y motor if it hasn't been stopped yet
                    if hasattr(self, 'y_stopped') and self.y_stopped:
                        if iteration_count % 50 == 0:  # Only log every 50 iterations to reduce spam
                            logging.info(f"Y axis LOCKED: {current_y:.1f}% [iter {iteration_count}]")
                    elif y_error > y_tolerance and not y_at_target:
                        # Check if motor is moving in wrong direction (away from target)
                        if hasattr(self, 'y_last_position') and self.y_last_position is not None:
                            last_error = abs(self.y_last_position - target_y)
                            movement = abs(current_y - self.y_last_position)
                            
                            # Y motor is very slow to respond - only stop for major direction reversals
                            # Be very lenient for large movements - sensor glitches can cause false readings
                            if target_y > 10.0:  # Large movement targets - be very lenient
                                if movement > 5.0 and y_error > last_error + 3.0:  # Very lenient for large movements
                                    logging.warning(f"🚫 Y MAJOR DIRECTION REVERSAL: {self.y_last_position:.1f}% → {current_y:.1f}% (moving away from {target_y:.1f}%)")
                                    logging.warning(f"   Last error: {last_error:.1f}%, Current error: {y_error:.1f}%, Movement: {movement:.1f}%")
                                    self.controller.y_motor.stop_motor()
                                    self.controller.y_motor.set_speed(0)
                                    self.y_stopped = True
                                else:
                                    if iteration_count % 100 == 0:  # Reduce Y continuing spam  
                                        logging.info(f"⏳ Y CONTINUING: {current_y:.1f}% → {target_y:.1f}% (large movement, allowing sensor variations)")
                            else:  # Small movement targets - be extremely lenient for Y motor
                                if movement > 15.0 and y_error > last_error + 8.0:  # EXTREMELY lenient - Y motor has sensor delay issues
                                    logging.warning(f"🚫 Y CATASTROPHIC REVERSAL: {self.y_last_position:.1f}% → {current_y:.1f}% (moving away from {target_y:.1f}%)")
                                    logging.warning(f"   Last error: {last_error:.1f}%, Current error: {y_error:.1f}%, Movement: {movement:.1f}%")
                                    self.controller.y_motor.stop_motor()
                                    self.controller.y_motor.set_speed(0)
                                    self.y_stopped = True
                                else:
                                    if iteration_count % 100 == 0:  # Reduce Y continuing spam
                                        logging.info(f"⏳ Y CONTINUING: {current_y:.1f}% → {target_y:.1f}% (error: {y_error:.1f}%, allowing sensor delays)")
                        else:
                            if iteration_count <= 5:  # Only log first few iterations
                                logging.info(f"⏳ Y CONTINUING: {current_y:.1f}% → {target_y:.1f}% (error: {y_error:.1f}%, first check)")
                        # Send speed adjustment commands based on distance to target
                        base_y_speed = 50.0  # Default speed for Y motor (will be multiplied by 1.5x in motor controller)
                        new_y_speed = calculate_y_approach_speed(y_error, base_y_speed)
                        
                        # Determine direction for Y motor
                        if target_y > current_y:
                            self.controller.y_motor.set_direction_forward()
                        else:
                            self.controller.y_motor.set_direction_reverse()
                        
                        self.controller.y_motor.set_speed(new_y_speed)
                        corrections_sent = True
                        
                        # Update last position for next check
                        self.y_last_position = current_y
                    elif y_at_target:
                        logging.info(f"Y axis OK: {current_y:.1f}% (within {y_tolerance}% of {target_y:.1f}%)")
                    
                    if corrections_sent:
                        time.sleep(0.05)  # Ultra fast checking when corrections sent
                    else:
                        time.sleep(0.02)  # Extremely frequent checking for precise target detection
                    
            except Exception as e:
                logging.error(f"Error during simultaneous movement: {e}")
                time.sleep(0.5)
        
        # Timeout - stop both motors
        self.controller.x_motor.stop_motor()
        self.controller.y_motor.stop_motor()
        
        try:
            current_x, current_y = self.controller.get_current_position()
            logging.warning(f"⏰ Timeout - Current: X={current_x:.1f}%, Y={current_y:.1f}%, Target: X={target_x:.1f}%, Y={target_y:.1f}%")
        except Exception as e:
            logging.error(f"Error reading final position: {e}")
        return False
    
    def _get_consensus_reading(self, readings: list, axis: str) -> float:
        """
        Get consensus from 3 sensor readings by finding the two closest values and averaging them
        This eliminates sensor glitches that cause single bad readings
        """
        if len(readings) < 2:
            if len(readings) == 1:
                return readings[0]
            else:
                logging.error(f"No valid {axis} sensor readings available")
                return 0.0
        
        if len(readings) == 2:
            avg = (readings[0] + readings[1]) / 2
            logging.debug(f"{axis} consensus (2 readings): {readings[0]:.1f}%, {readings[1]:.1f}% → {avg:.1f}%")
            return avg
        
        # For 3 readings, find the two closest and average them
        distances = [
            (abs(readings[0] - readings[1]), 0, 1),  # distance between 0,1
            (abs(readings[0] - readings[2]), 0, 2),  # distance between 0,2  
            (abs(readings[1] - readings[2]), 1, 2),  # distance between 1,2
        ]
        
        # Find the pair with minimum distance (most consistent)
        min_distance, idx1, idx2 = min(distances)
        consensus = (readings[idx1] + readings[idx2]) / 2
        
        logging.debug(f"{axis} consensus (3 readings): [{readings[0]:.1f}%, {readings[1]:.1f}%, {readings[2]:.1f}%] → closest pair: {readings[idx1]:.1f}%, {readings[idx2]:.1f}% → {consensus:.1f}%")
        
        # Log if we had to reject a glitchy reading
        rejected_idx = [0, 1, 2]
        rejected_idx.remove(idx1)
        rejected_idx.remove(idx2)
        if rejected_idx and min_distance > 2.0:  # If we rejected a reading that was >2% different
            logging.warning(f"🔧 {axis} GLITCH REJECTED: {readings[rejected_idx[0]]:.1f}% (consensus: {consensus:.1f}%)")
        
        return consensus

    def _is_axis_at_target(self, current: float, target: float, tolerance: float, axis: str) -> bool:
        """
        Check if axis has reached target within tolerance
        """
        error = abs(current - target)
        
        # Only log debug info if error is very large (debugging tolerance issues)
        if error > 10.0:
            logging.warning(f"🔍 {axis} LARGE ERROR: current={current:.1f}%, target={target:.1f}%, error={error:.1f}%, tolerance={tolerance}%")
        
        # Only accept if strictly within tolerance - prevent boundary edge cases
        if error < tolerance:
            logging.info(f"{axis} AT TARGET: {current:.1f}% within {tolerance}% of {target:.1f}%")
            return True
        else:
            logging.debug(f"{axis} NOT AT TARGET: {current:.1f}% error {error:.1f}% > tolerance {tolerance}%")
            return False
    
    def _check_overshoot(self, current: float, target: float, axis: str) -> bool:
        """
        Check if motor has overshot the target by more than 2% (clear overshoot)
        This prevents motors from running away in the wrong direction
        """
        overshoot_tolerance = 2.0  # 2% overshoot tolerance
        
        # Calculate if we've gone significantly past the target
        if current > target + overshoot_tolerance:
            logging.warning(f"{axis} OVERSHOOT: {current:.1f}% > {target:.1f}% + {overshoot_tolerance}% (went too far forward)")
            return True
        elif current < target - overshoot_tolerance:
            logging.warning(f"{axis} OVERSHOOT: {current:.1f}% < {target:.1f}% - {overshoot_tolerance}% (went too far backward)")
            return True
        else:
            return False
    
    def save_path(self, path_name: str, path_data: List[PathPoint]) -> bool:
        """Save a recorded path to disk"""
        try:
            file_path = self.paths_directory / f"{path_name}.json"
            
            # Convert path data to dictionary format
            path_dict = {
                'name': path_name,
                'recorded_at': time.time(),
                'duration': path_data[-1].duration_from_start if path_data else 0,
                'point_count': len(path_data),
                'points': [point.to_dict() for point in path_data]
            }
            
            with open(file_path, 'w') as f:
                json.dump(path_dict, f, indent=2)
            
            logging.info(f"Path saved: {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving path {path_name}: {e}")
            return False
    
    def load_path(self, path_name: str) -> Optional[List[PathPoint]]:
        """Load a recorded path from disk"""
        try:
            file_path = self.paths_directory / f"{path_name}.json"
            
            if not file_path.exists():
                logging.error(f"Path file not found: {file_path}")
                return None
            
            with open(file_path, 'r') as f:
                path_dict = json.load(f)
            
            # Convert dictionary data back to PathPoint objects
            # Handle both old format ('points') and new format ('datapoints')
            point_data_list = path_dict.get('points', path_dict.get('datapoints', []))
            points = []
            
            for point_data in point_data_list:
                # Handle new format with different field names
                if 'x_position' in point_data and 'y_position' in point_data:
                    # New format - convert to PathPoint format
                    converted_point = {
                        'timestamp': point_data.get('timestamp', 0),
                        'x_position': point_data['x_position'],
                        'y_position': point_data['y_position'],
                        'duration_from_start': 0  # Default for new format
                    }
                    points.append(PathPoint.from_dict(converted_point))
                else:
                    # Old format - use as is
                    points.append(PathPoint.from_dict(point_data))
            
            logging.info(f"Path loaded: {path_name} ({len(points)} points)")
            return points
            
        except Exception as e:
            logging.error(f"Error loading path {path_name}: {e}")
            return None
    
    def list_paths(self) -> List[Dict]:
        """List all available recorded paths"""
        paths = []
        
        try:
            for file_path in self.paths_directory.glob("*.json"):
                try:
                    with open(file_path, 'r') as f:
                        path_dict = json.load(f)
                    
                    # Handle both old and new JSON formats
                    recorded_at = path_dict.get('recorded_at', 0)
                    if isinstance(recorded_at, str):
                        # Convert ISO timestamp to Unix timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
                            recorded_at = dt.timestamp()
                        except:
                            recorded_at = 0
                    
                    # Get point count from either field name
                    point_count = path_dict.get('point_count', path_dict.get('total_points', 0))
                    
                    paths.append({
                        'name': path_dict.get('name', file_path.stem),
                        'recorded_at': recorded_at,
                        'duration': path_dict.get('duration', 0),  # Default to 0 for new format
                        'point_count': point_count,
                        'file_path': str(file_path)
                    })
                except Exception as e:
                    logging.warning(f"Error reading path file {file_path}: {e}")
                    continue
            
            # Sort by recorded time (newest first)
            paths.sort(key=lambda x: x['recorded_at'], reverse=True)
            
        except Exception as e:
            logging.error(f"Error listing paths: {e}")
        
        return paths
    
    def delete_path(self, path_name: str) -> bool:
        """Delete a recorded path"""
        try:
            file_path = self.paths_directory / f"{path_name}.json"
            
            if file_path.exists():
                file_path.unlink()
                logging.info(f"Path deleted: {path_name}")
                return True
            else:
                logging.warning(f"Path not found: {path_name}")
                return False
                
        except Exception as e:
            logging.error(f"Error deleting path {path_name}: {e}")
            return False
    
    def get_recording_status(self) -> Dict:
        """Get current recording status"""
        return {
            'is_recording': self.is_recording,
            'is_playing': self.is_playing,
            'current_path_points': len(self.current_path) if self.is_recording else 0,
            'recording_duration': time.time() - self.recording_start_time if self.is_recording else 0
        }
    
    def cleanup(self):
        """Clean up resources"""
        if self.is_recording:
            self.stop_recording()
        if self.is_playing:
            self.stop_playback()
        
        logging.info("Path Recorder cleaned up")
