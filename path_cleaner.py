#!/usr/bin/env python3
"""
Path Cleaner - Utility to clean and optimize recorded TV arm paths
- Make paths unidirectional (one-way only)
- Reduce data points by removing every 2nd point
- Clean up recorded movement data
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
import shutil
from datetime import datetime


class PathCleaner:
    """Cleans and optimizes recorded TV arm movement paths"""
    
    def __init__(self, paths_directory: str = "recorded_paths"):
        self.paths_directory = Path(paths_directory)
        self.backup_directory = Path(f"{paths_directory}_backup")
        
        if not self.paths_directory.exists():
            print(f"Error: Paths directory '{paths_directory}' not found!")
            sys.exit(1)
    
    def backup_paths(self):
        """Create backup of original paths before cleaning"""
        if self.backup_directory.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{self.paths_directory.name}_backup_{timestamp}"
            backup_path = self.backup_directory.parent / backup_name
            shutil.move(str(self.backup_directory), str(backup_path))
            print(f"Moved existing backup to: {backup_name}")
        
        shutil.copytree(str(self.paths_directory), str(self.backup_directory))
        print(f"✅ Backup created: {self.backup_directory}")
    
    def load_path_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a path JSON file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return None
    
    def save_path_file(self, file_path: Path, path_data: Dict[str, Any]):
        """Save a path JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(path_data, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Error saving {file_path}: {e}")
            return False
    
    def make_unidirectional(self, points: List[Dict]) -> List[Dict]:
        """
        Remove outlier datapoints that don't follow linear progression
        Keeps only points that maintain smooth movement from previous point
        """
        if len(points) < 3:
            return points
        
        # Analyze overall movement
        start_point = points[0]
        end_point = points[-1]
        
        x_movement = end_point['x_position'] - start_point['x_position']
        y_movement = end_point['y_position'] - start_point['y_position']
        
        print(f"   Movement analysis: X={x_movement:.1f}%, Y={y_movement:.1f}%")
        
        # Start with first point
        cleaned_points = [points[0]]
        
        # Threshold for detecting outliers (percentage change that's too large)
        outlier_threshold = 15.0  # If movement changes by more than 15% from expected, it's likely an outlier
        
        for i in range(1, len(points)):
            current_point = points[i]
            last_valid_point = cleaned_points[-1]
            
            # Calculate expected linear progression
            if len(cleaned_points) >= 2:
                # Use trend from last two valid points to predict expected values
                prev_point = cleaned_points[-2]
                
                # Calculate velocity (change per unit time)
                time_diff = last_valid_point['timestamp'] - prev_point['timestamp']
                if time_diff > 0:
                    x_velocity = (last_valid_point['x_position'] - prev_point['x_position']) / time_diff
                    y_velocity = (last_valid_point['y_position'] - prev_point['y_position']) / time_diff
                    
                    # Predict where we should be at current timestamp
                    current_time_diff = current_point['timestamp'] - last_valid_point['timestamp']
                    expected_x = last_valid_point['x_position'] + (x_velocity * current_time_diff)
                    expected_y = last_valid_point['y_position'] + (y_velocity * current_time_diff)
                    
                    # Check if current point is close to expected position
                    x_deviation = abs(current_point['x_position'] - expected_x)
                    y_deviation = abs(current_point['y_position'] - expected_y)
                    
                    # If deviation is too large, it's likely an outlier
                    if x_deviation > outlier_threshold or y_deviation > outlier_threshold:
                        print(f"   Outlier detected at point {i}: X deviation {x_deviation:.1f}%, Y deviation {y_deviation:.1f}%")
                        continue  # Skip this outlier point
            
            else:
                # For the second point, just check if movement is reasonable
                x_change = abs(current_point['x_position'] - last_valid_point['x_position'])
                y_change = abs(current_point['y_position'] - last_valid_point['y_position'])
                
                # If change is extremely large, it's likely an outlier
                if x_change > 30.0 or y_change > 30.0:
                    print(f"   Large jump detected at point {i}: X change {x_change:.1f}%, Y change {y_change:.1f}%")
                    continue  # Skip this outlier point
            
            # Point passed validation, add it
            cleaned_points.append(current_point)
        
        # Ensure we have the final destination if it's reasonable
        if len(points) > 1 and points[-1] not in cleaned_points:
            final_point = points[-1]
            last_valid = cleaned_points[-1]
            
            # Check if final point is a reasonable end position
            x_change = abs(final_point['x_position'] - last_valid['x_position'])
            y_change = abs(final_point['y_position'] - last_valid['y_position'])
            
            if x_change <= 30.0 and y_change <= 30.0:  # Reasonable final movement
                cleaned_points.append(final_point)
        
        # Recalculate duration_from_start for cleaned points
        if cleaned_points:
            start_time = cleaned_points[0]['timestamp']
            for point in cleaned_points:
                point['duration_from_start'] = point['timestamp'] - start_time
        
        reduction = len(points) - len(cleaned_points)
        print(f"   Outlier removal: {len(points)} → {len(cleaned_points)} points (removed {reduction} outliers)")
        
        return cleaned_points
    
    def reduce_datapoints(self, points: List[Dict], keep_every_nth: int = 2) -> List[Dict]:
        """
        Reduce data points by keeping every nth point
        Always keep first and last points
        """
        if len(points) <= 2:
            return points
        
        # Always keep first point
        reduced_points = [points[0]]
        
        # Keep every nth point from the middle
        for i in range(keep_every_nth, len(points) - 1, keep_every_nth):
            reduced_points.append(points[i])
        
        # Always keep last point (if it wasn't already included)
        if len(points) > 1 and points[-1] not in reduced_points:
            reduced_points.append(points[-1])
        
        # Recalculate duration_from_start for reduced points
        if reduced_points:
            start_time = reduced_points[0]['timestamp']
            for point in reduced_points:
                point['duration_from_start'] = point['timestamp'] - start_time
        
        reduction = len(points) - len(reduced_points)
        print(f"   Data reduction: {len(points)} → {len(reduced_points)} points (removed {reduction} points)")
        
        return reduced_points
    
    def clean_path_file(self, file_path: Path, make_unidirectional: bool = True, reduce_points: bool = True):
        """Clean a single path file"""
        print(f"\n🔧 Cleaning: {file_path.name}")
        
        # Load the path data
        path_data = self.load_path_file(file_path)
        if not path_data:
            return False
        
        original_points = path_data.get('points', [])
        if not original_points:
            print("   ⚠️  No points found in file")
            return False
        
        print(f"   Original: {len(original_points)} points, {path_data.get('duration', 0):.1f}s duration")
        
        # Start with original points
        cleaned_points = original_points.copy()
        
        # Apply unidirectional filtering
        if make_unidirectional:
            cleaned_points = self.make_unidirectional(cleaned_points)
        
        # Apply data point reduction
        if reduce_points:
            cleaned_points = self.reduce_datapoints(cleaned_points, keep_every_nth=2)
        
        # Update path data
        path_data['points'] = cleaned_points
        path_data['point_count'] = len(cleaned_points)
        if cleaned_points:
            path_data['duration'] = cleaned_points[-1]['duration_from_start']
        
        # Add cleaning metadata
        path_data['cleaned'] = True
        path_data['cleaned_at'] = datetime.now().isoformat()
        path_data['original_point_count'] = len(original_points)
        
        print(f"   ✅ Final: {len(cleaned_points)} points, {path_data.get('duration', 0):.1f}s duration")
        
        # Save cleaned file
        return self.save_path_file(file_path, path_data)
    
    def clean_all_paths(self, make_unidirectional: bool = True, reduce_points: bool = True):
        """Clean all path files in the directory"""
        json_files = list(self.paths_directory.glob("*.json"))
        
        if not json_files:
            print("No JSON path files found!")
            return
        
        print(f"Found {len(json_files)} path files to clean")
        
        # Create backup first
        self.backup_paths()
        
        success_count = 0
        for file_path in json_files:
            if self.clean_path_file(file_path, make_unidirectional, reduce_points):
                success_count += 1
        
        print(f"\n🎉 Cleaning complete!")
        print(f"✅ Successfully cleaned: {success_count}/{len(json_files)} files")
        print(f"📁 Original files backed up to: {self.backup_directory}")
    
    def list_paths(self):
        """List all path files with their info"""
        json_files = list(self.paths_directory.glob("*.json"))
        
        if not json_files:
            print("No JSON path files found!")
            return
        
        print(f"\nFound {len(json_files)} path files:")
        print("-" * 80)
        print("Name".ljust(25) + "Points".ljust(8) + "Duration".ljust(12) + "Cleaned".ljust(8) + "Size")
        print("-" * 80)
        
        for file_path in sorted(json_files):
            path_data = self.load_path_file(file_path)
            if path_data:
                name = file_path.stem[:24]
                points = path_data.get('point_count', 0)
                duration = f"{path_data.get('duration', 0):.1f}s"
                cleaned = "Yes" if path_data.get('cleaned', False) else "No"
                size = f"{file_path.stat().st_size / 1024:.1f}KB"
                
                print(name.ljust(25) + str(points).ljust(8) + duration.ljust(12) + cleaned.ljust(8) + size)


def main():
    parser = argparse.ArgumentParser(description='Clean and optimize recorded TV arm paths')
    parser.add_argument('--paths-dir', default='recorded_paths', 
                       help='Directory containing recorded paths (default: recorded_paths)')
    parser.add_argument('--list', action='store_true', 
                       help='List all path files and their info')
    parser.add_argument('--no-unidirectional', action='store_true', 
                       help='Skip making paths unidirectional')
    parser.add_argument('--no-reduce', action='store_true', 
                       help='Skip reducing data points')
    parser.add_argument('--keep-every', type=int, default=2, 
                       help='Keep every Nth data point (default: 2)')
    
    args = parser.parse_args()
    
    cleaner = PathCleaner(args.paths_dir)
    
    if args.list:
        cleaner.list_paths()
    else:
        print("🧹 TV Arm Path Cleaner")
        print("=" * 40)
        
        make_unidirectional = not args.no_unidirectional
        reduce_points = not args.no_reduce
        
        print(f"Settings:")
        print(f"  - Make unidirectional: {'Yes' if make_unidirectional else 'No'}")
        print(f"  - Reduce data points: {'Yes' if reduce_points else 'No'}")
        if reduce_points:
            print(f"  - Keep every {args.keep_every} points")
        
        confirm = input("\nProceed with cleaning? (y/N): ").strip().lower()
        if confirm == 'y':
            cleaner.clean_all_paths(make_unidirectional, reduce_points)
        else:
            print("Cleaning cancelled.")


if __name__ == "__main__":
    main()
