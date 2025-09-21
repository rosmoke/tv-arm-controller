#!/usr/bin/env python3
"""
Create Retract Path - Generate retract.json by reversing extend.json
Creates a perfect return path from extended position back to wall
"""

import json
import os

def create_retract_path():
    # Read the extend path
    extend_path = "recorded_paths/extend.json"
    retract_path = "recorded_paths/retract.json"
    
    if not os.path.exists(extend_path):
        print(f"Error: {extend_path} not found!")
        return
    
    with open(extend_path, 'r') as f:
        extend_data = json.load(f)
    
    # Create retract data by reversing the datapoints
    retract_data = {
        "name": "retract",
        "description": "TV arm retraction path - reversed from extend path",
        "recorded_at": extend_data["recorded_at"],
        "total_points": extend_data["total_points"],
        "datapoints": []
    }
    
    # Reverse the datapoints and renumber them
    reversed_points = extend_data["datapoints"][::-1]
    for i, point in enumerate(reversed_points):
        new_point = {
            "point_number": i + 1,
            "timestamp": point["timestamp"],
            "x_position": point["x_position"],
            "y_position": point["y_position"]
        }
        retract_data["datapoints"].append(new_point)
    
    # Save the retract path
    with open(retract_path, 'w') as f:
        json.dump(retract_data, f, indent=2)
    
    print(f"Created {retract_path} with {retract_data['total_points']} datapoints")
    print("Retract path datapoints:")
    for point in retract_data["datapoints"]:
        print(f"  Point {point['point_number']}: X={point['x_position']}%, Y={point['y_position']}%")

if __name__ == "__main__":
    create_retract_path()