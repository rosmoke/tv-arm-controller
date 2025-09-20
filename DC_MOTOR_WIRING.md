# DC Motor Wiring Guide - TB6612FNG Motor Driver

## 🔌 **Complete Wiring Diagram**

### **Power Connections**
```
12V Power Supply:
12V+ → TB6612FNG VM (motor power)
12V- → Common Ground

5V Power Supply (for Pi):  
5V+ → TB6612FNG VCC (logic power) + Pi 5V pins
5V- → Common Ground
```

### **TB6612FNG to Raspberry Pi Zero 2 W**
```
TB6612FNG Pin | Pi Pin | Pi GPIO | Function
--------------|--------|---------|----------
VCC           | Pin 2  | 5V      | Logic power supply
GND           | Pin 6  | GND     | Ground
AIN1          | Pin 11 | GPIO 17 | Motor A direction 1
AIN2          | Pin 13 | GPIO 27 | Motor A direction 2  
PWMA          | Pin 12 | GPIO 18 | Motor A speed control (PWM)
BIN1          | Pin 15 | GPIO 22 | Motor B direction 1
BIN2          | Pin 16 | GPIO 23 | Motor B direction 2
PWMB          | Pin 35 | GPIO 19 | Motor B speed control (PWM)
STBY          | Pin 18 | GPIO 24 | Standby (HIGH = enable)
```

### **DC Motors to TB6612FNG**
```
Motor A (X-axis):
Wire 1 → TB6612FNG A01
Wire 2 → TB6612FNG A02

Motor B (Y-axis):
Wire 1 → TB6612FNG B01  
Wire 2 → TB6612FNG B02
```

### **Position Feedback (ADS1115 + Potentiometers)**
```
ADS1115 to Pi (I2C):
VDD → Pin 1 (3.3V)
GND → Pin 6 (GND)
SDA → Pin 3 (GPIO 2)
SCL → Pin 5 (GPIO 3)

Potentiometer 1 (X-axis):
Pin 1 (GND) → ADS1115 GND
Pin 2 (Wiper) → ADS1115 A0  
Pin 3 (3.3V) → ADS1115 VDD

Potentiometer 2 (Y-axis):
Pin 1 (GND) → ADS1115 GND
Pin 2 (Wiper) → ADS1115 A2
Pin 3 (3.3V) → ADS1115 VDD
```

## ⚡ **Power Supply Requirements**

### **12V Supply (for Motors)**
- **Voltage**: 12V DC
- **Current**: Depends on your motors (typically 2-5A total)
- **Connection**: TB6612FNG VM pin

### **5V Supply (for Logic)**  
- **Voltage**: 5V DC
- **Current**: ~3A (Pi + logic circuits)
- **Connection**: TB6612FNG VCC + Pi power pins

### **Ground Connection**
- **All grounds must be connected together**
- 12V-, 5V-, TB6612FNG GND, Pi GND

## 🎛️ **Motor Control Logic**

### **Direction Control**
```
Forward:  AIN1=HIGH, AIN2=LOW  + PWM speed
Reverse:  AIN1=LOW,  AIN2=HIGH + PWM speed
Stop:     AIN1=LOW,  AIN2=LOW  + PWM=0
Brake:    AIN1=HIGH, AIN2=HIGH + PWM=100
```

### **Speed Control**
- **PWM Frequency**: 1000Hz (configurable)
- **Duty Cycle**: 0-100% (0 = stop, 100 = full speed)

## 🔧 **Pin Summary Table**

| Component | Connection | Pi Pin | Pi GPIO | Notes |
|-----------|------------|--------|---------|-------|
| **Power** |
| 5V Logic | TB6612FNG VCC | Pin 2 | 5V | Logic power |
| Ground | TB6612FNG GND | Pin 6 | GND | Common ground |
| **Motor A (X-axis)** |
| Direction 1 | TB6612FNG AIN1 | Pin 11 | GPIO 17 | Forward/reverse |
| Direction 2 | TB6612FNG AIN2 | Pin 13 | GPIO 27 | Forward/reverse |
| Speed PWM | TB6612FNG PWMA | Pin 12 | GPIO 18 | 0-100% speed |
| **Motor B (Y-axis)** |
| Direction 1 | TB6612FNG BIN1 | Pin 15 | GPIO 22 | Forward/reverse |
| Direction 2 | TB6612FNG BIN2 | Pin 16 | GPIO 23 | Forward/reverse |
| Speed PWM | TB6612FNG PWMB | Pin 35 | GPIO 19 | 0-100% speed |
| **Control** |
| Standby | TB6612FNG STBY | Pin 18 | GPIO 24 | Enable motors |
| **Position Feedback** |
| I2C Data | ADS1115 SDA | Pin 3 | GPIO 2 | Position sensing |
| I2C Clock | ADS1115 SCL | Pin 5 | GPIO 3 | Position sensing |

## 🛡️ **Safety Notes**

1. **Power Supply Isolation**: Use separate supplies for 12V motors and 5V logic
2. **Common Ground**: All grounds must be connected together
3. **Standby Pin**: Pull STBY HIGH to enable motors, LOW to disable
4. **Motor Stall**: TB6612FNG has built-in current limiting
5. **Heat Dissipation**: TB6612FNG may need heatsink for high current motors

## 🔍 **Troubleshooting**

### **Motors Don't Move**
- Check STBY pin is HIGH (GPIO 24)
- Verify 12V power supply to VM
- Check motor connections to A01/A02, B01/B02

### **Erratic Movement**
- Check common ground connection
- Verify 5V logic supply is stable
- Check GPIO pin connections

### **Position Feedback Issues**
- Verify potentiometer wiring to ADS1115
- Check I2C connections (SDA/SCL)
- Test with `i2cdetect -y 1` (should show 0x48)

## 📋 **Next Steps**

1. **Wire according to this diagram**
2. **Copy updated files to Pi**: `scp` the modified files
3. **Test the new DC motor setup**: `python main.py --test`
4. **Calibrate position sensors**: `./calibrate.sh`
5. **Start the service**: `./start.sh`

The system will now control DC motors instead of servos while maintaining the same Home Assistant integration! 🚀

