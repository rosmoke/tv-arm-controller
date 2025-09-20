#!/usr/bin/env python3
"""
Create Retract Path - Generate retract.json by reversing extend.json
Creates a perfect return path from extended position back to wall
"""

import json
import time
from pathlib import Path
from typing import List, Dict


def reverse_path(extend_path: str = "recorded_paths/extending.json", 
                retract_path: str = "recorded_paths/retracting.json"):
    """
    Create retract path by reversing the extend path
    """
    extend_file = Path(extend_path)
    retract_file = Path(retract_path)
    
    if not extend_file.exists():
        print(f"❌ Error: {extend_path} not found!")
        return False
    
    print(f"📖 Loading extend path: {extend_path}")
    
    # Load the extend path
    try:
        with open(extend_file, 'r') as f:
            extend_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading extend path: {e}")
        return False
    
    extend_points = extend_data.get('points', [])
    if not extend_points:
        print("❌ No points found in extend path!")
        return False
    
    print(f"   Original: {len(extend_points)} points, {extend_data.get('duration', 0):.1f}s duration")
    print(f"   Start: X={extend_points[0]['x_position']:.1f}%, Y={extend_points[0]['y_position']:.1f}%")
    print(f"   End: X={extend_points[-1]['x_position']:.1f}%, Y={extend_points[-1]['y_position']:.1f}%")
    
    # Reverse the points order
    reversed_points = extend_points[::-1]  # Reverse the list
    
    print(f"\n🔄 Creating retract path...")
    print(f"   Reversing {len(reversed_points)} points")
    
    # Recalculate timestamps and duration for the reversed path
    current_time = time.time()
    total_duration = extend_data.get('duration', 0)
    
    retract_points = []
    for i, point in enumerate(reversed_points):
        # Calculate new timestamp - reverse the timing
        original_progress = point['duration_from_start'] / total_duration if total_duration > 0 else 0
        new_progress = 1.0 - original_progress  # Reverse the progress
        new_duration = new_progress * total_duration
        
        retract_point = {
            'timestamp': current_time + new_duration,
            'x_position': point['x_position'],
            'y_position': point['y_position'],
            'duration_from_start': new_duration
        }
        retract_points.append(retract_point)
    
    # Sort by duration to ensure proper order
    retract_points.sort(key=lambda p: p['duration_from_start'])
    
    # Recalculate duration_from_start to start from 0
    if retract_points:
        for point in retract_points:
            point['duration_from_start'] = point['duration_from_start'] - retract_points[0]['duration_from_start']
    
    # Create retract path data
    retract_data = {
        'name': 'retracting',
        'recorded_at': current_time,
        'duration': total_duration,
        'point_count': len(retract_points),
        'points': retract_points,
        'generated_from': 'extending.json',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'reversed': True
    }
    
    print(f"   New start: X={retract_points[0]['x_position']:.1f}%, Y={retract_points[0]['y_position']:.1f}%")
    print(f"   New end: X={retract_points[-1]['x_position']:.1f}%, Y={retract_points[-1]['y_position']:.1f}%")
    
    # Save retract path
    try:
        with open(retract_file, 'w') as f:
            json.dump(retract_data, f, indent=2)
        
        print(f"✅ Retract path created: {retract_path}")
        print(f"   Duration: {total_duration:.1f}s")
        print(f"   Points: {len(retract_points)}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving retract path: {e}")
        return False


def main():
    print("🔄 TV Arm Path Reverser")
    print("=" * 40)
    print("Creates retracting.json by reversing extending.json")
    print()
    
    if reverse_path():
        print("\n🎉 Success!")
        print("You now have:")
        print("  - extending.json: Start → End position")
        print("  - retracting.json: End → Start position")
        print()
        print("Test with: python main.py --play-path retracting")
    else:
        print("\n❌ Failed to create retract path")


if __name__ == "__main__":
    main()
