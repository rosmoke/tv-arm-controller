#!/usr/bin/env python3
"""
Debug Y-axis channel - test A1 and A2 directly
"""

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    import time

    print("🔍 Y-Axis Channel Debug")
    print("=" * 40)

    # Initialize ADS1115
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    ads.gain = 1  # ±4.096V range
    ads.data_rate = 32  # Slow for stability

    # Test all channels
    channels = {
        'A0': AnalogIn(ads, ADS.P0),
        'A1': AnalogIn(ads, ADS.P1), 
        'A2': AnalogIn(ads, ADS.P2),
        'A3': AnalogIn(ads, ADS.P3)
    }

    print("Testing all ADS1115 channels:")
    print("-" * 40)

    for i in range(5):  # Take 5 readings
        print(f"Reading {i+1}:")
        for name, channel in channels.items():
            try:
                voltage = channel.voltage
                print(f"  {name}: {voltage:.3f}V")
            except Exception as e:
                print(f"  {name}: ERROR - {e}")
        print()
        time.sleep(0.5)

    print("🔍 Look for:")
    print("- A0: Should show X potentiometer (~3.14V)")
    print("- A1: Should show Y potentiometer (~1.57V) if connected")
    print("- A2: Should show Y potentiometer (~1.57V) if still connected there")
    print("- A3: Should be 0.000V (unused)")

except ImportError as e:
    print(f"❌ Missing module: {e}")
    print("Run this on the Raspberry Pi with the ADS1115 connected")
except Exception as e:
    print(f"❌ Error: {e}")
