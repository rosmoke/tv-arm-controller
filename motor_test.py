#!/usr/bin/env python3
"""
Simple Motor Test - Test DC motors directly without complex control loops
"""

import time
import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO not available - simulation mode")
    GPIO = None

def test_motor(ain1_pin, ain2_pin, pwm_pin, stby_pin, motor_name):
    """Test a single DC motor"""
    print(f"\n🔧 Testing {motor_name} Motor")
    print(f"Pins: AIN1={ain1_pin}, AIN2={ain2_pin}, PWM={pwm_pin}, STBY={stby_pin}")
    
    if not GPIO:
        print("⚠️  GPIO not available - skipping hardware test")
        return
    
    try:
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(ain1_pin, GPIO.OUT)
        GPIO.setup(ain2_pin, GPIO.OUT)
        GPIO.setup(pwm_pin, GPIO.OUT)
        if stby_pin:
            GPIO.setup(stby_pin, GPIO.OUT)
            GPIO.output(stby_pin, GPIO.HIGH)  # Enable motor driver
        
        # Setup PWM
        pwm = GPIO.PWM(pwm_pin, 1000)  # 1kHz frequency
        pwm.start(0)
        
        print("✅ GPIO setup complete")
        
        # Test sequence
        tests = [
            ("STOP", lambda: stop_motor(ain1_pin, ain2_pin, pwm)),
            ("FORWARD 30%", lambda: (set_forward(ain1_pin, ain2_pin), pwm.ChangeDutyCycle(30))),
            ("FORWARD 60%", lambda: (set_forward(ain1_pin, ain2_pin), pwm.ChangeDutyCycle(60))),
            ("FORWARD 90%", lambda: (set_forward(ain1_pin, ain2_pin), pwm.ChangeDutyCycle(90))),
            ("STOP", lambda: stop_motor(ain1_pin, ain2_pin, pwm)),
            ("REVERSE 30%", lambda: (set_reverse(ain1_pin, ain2_pin), pwm.ChangeDutyCycle(30))),
            ("REVERSE 60%", lambda: (set_reverse(ain1_pin, ain2_pin), pwm.ChangeDutyCycle(60))),
            ("REVERSE 90%", lambda: (set_reverse(ain1_pin, ain2_pin), pwm.ChangeDutyCycle(90))),
            ("STOP", lambda: stop_motor(ain1_pin, ain2_pin, pwm))
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔄 {test_name}")
            test_func()
            
            if "STOP" not in test_name:
                print(f"   Motor should be moving {test_name}")
                print("   Check for physical movement...")
                time.sleep(3)  # Give time to observe movement
            else:
                print("   Motor should be stopped")
                time.sleep(1)
        
        print(f"\n✅ {motor_name} motor test complete")
        pwm.stop()
        
    except Exception as e:
        print(f"❌ Error testing {motor_name} motor: {e}")
    finally:
        try:
            pwm.stop()
        except:
            pass

def set_forward(ain1_pin, ain2_pin):
    """Set motor direction to forward"""
    GPIO.output(ain1_pin, GPIO.HIGH)
    GPIO.output(ain2_pin, GPIO.LOW)
    print(f"   GPIO {ain1_pin}=HIGH, GPIO {ain2_pin}=LOW (FORWARD)")

def set_reverse(ain1_pin, ain2_pin):
    """Set motor direction to reverse"""
    GPIO.output(ain1_pin, GPIO.LOW)
    GPIO.output(ain2_pin, GPIO.HIGH)
    print(f"   GPIO {ain1_pin}=LOW, GPIO {ain2_pin}=HIGH (REVERSE)")

def stop_motor(ain1_pin, ain2_pin, pwm):
    """Stop motor"""
    GPIO.output(ain1_pin, GPIO.LOW)
    GPIO.output(ain2_pin, GPIO.LOW)
    pwm.ChangeDutyCycle(0)
    print(f"   GPIO {ain1_pin}=LOW, GPIO {ain2_pin}=LOW, PWM=0% (STOP)")

def main():
    print("🚀 DC Motor Hardware Test")
    print("=" * 40)
    print("This will test each motor at different speeds")
    print("Watch for physical movement and listen for motor sounds")
    print()
    
    try:
        # Test X-axis motor (Motor A)
        test_motor(
            ain1_pin=17,  # GPIO 17 - AIN1
            ain2_pin=27,  # GPIO 27 - AIN2
            pwm_pin=18,   # GPIO 18 - PWMA
            stby_pin=24,  # GPIO 24 - STBY
            motor_name="X-AXIS"
        )
        
        # Test Y-axis motor (Motor B)
        test_motor(
            ain1_pin=22,  # GPIO 22 - BIN1
            ain2_pin=23,  # GPIO 23 - BIN2
            pwm_pin=19,   # GPIO 19 - PWMB
            stby_pin=None,  # Shared STBY pin
            motor_name="Y-AXIS"
        )
        
        print("\n🎉 Motor test completed!")
        print("If motors didn't move, check:")
        print("- 12V power supply to TB6612FNG VM pin")
        print("- Motor connections to A01/A02, B01/B02")
        print("- Common ground connections")
        print("- TB6612FNG heat dissipation")
        
    except KeyboardInterrupt:
        print("\n⏹️  Motor test interrupted")
    except Exception as e:
        print(f"\n❌ Motor test failed: {e}")
    finally:
        if GPIO:
            GPIO.cleanup()
            print("🧹 GPIO cleanup complete")

if __name__ == "__main__":
    main()
