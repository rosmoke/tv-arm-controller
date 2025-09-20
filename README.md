# TV Arm Controller with Home Assistant Integration

A complete motorized TV arm controller system using Raspberry Pi Zero 2 W, servo motors, potentiometer feedback, and Home Assistant integration via MQTT.

## 🎯 Features

- **Dual-axis servo control** - Precise X/Y positioning of TV arm
- **Position feedback** - Real-time position sensing via potentiometers and ADS1115 ADC
- **Home Assistant integration** - Automatic MQTT discovery and control
- **Web interface** - Control via Home Assistant dashboard
- **Calibration system** - Automatic sensor calibration
- **Safety features** - Position limits and emergency stop
- **Systemd service** - Automatic startup and monitoring
- **Comprehensive logging** - Debug and monitoring capabilities

## 🔧 Hardware Requirements

### Components
- **Raspberry Pi Zero 2 W (2021)** - Main controller
- **ADS1115** - 16-bit I2C ADC for position feedback
- **2x Servo Motors** - For X/Y axis movement
- **2x 10kΩ Potentiometers** (PT10MH02-103A2020-S) - Position feedback
- **Power supply** - 5V/3A for Pi and servos
- **Jumper wires and breadboard** - For connections

### Wiring Diagram

#### Raspberry Pi Zero 2 W to ADS1115 (I2C)
```
Pi Pin  | Pi Function | ADS1115 Pin
--------|--------------|-------------
Pin 1   | 3.3V        | VDD
Pin 3   | GPIO 2 (SDA)| SDA  
Pin 5   | GPIO 3 (SCL)| SCL
Pin 6   | GND         | GND
```

#### Servo Motors to Raspberry Pi
```
Servo   | Pi Pin | Pi Function    | Wire Color
--------|--------|----------------|------------
Servo 1 | Pin 12 | GPIO 18 (PWM)  | Signal (Orange)
        | Pin 2  | 5V             | Power (Red)
        | Pin 14 | GND            | Ground (Brown)
Servo 2 | Pin 35 | GPIO 19 (PWM)  | Signal (Orange)  
        | Pin 4  | 5V             | Power (Red)
        | Pin 20 | GND            | Ground (Brown)
```

#### Potentiometers to ADS1115
```
Potentiometer 1 (X-axis):
- Pin 1 (GND)    → ADS1115 GND
- Pin 2 (Wiper)  → ADS1115 A0
- Pin 3 (3.3V)   → ADS1115 VDD

Potentiometer 2 (Y-axis):  
- Pin 1 (GND)    → ADS1115 GND
- Pin 2 (Wiper)  → ADS1115 A2
- Pin 3 (3.3V)   → ADS1115 VDD
```

#### Alternative Power Distribution
You can use separate Pi pins for cleaner wiring:
```
Power Distribution:
- Pi Pin 1 (3.3V)  → ADS1115 VDD
- Pi Pin 17 (3.3V) → Both Potentiometers Pin 3
- Pi Pin 6 (GND)   → ADS1115 GND  
- Pi Pin 9 (GND)   → Potentiometer 1 Pin 1
- Pi Pin 25 (GND)  → Potentiometer 2 Pin 1
```

## 📦 Installation

### Quick Install
1. **Clone/copy the project** to your Raspberry Pi Zero 2 W
2. **Run the installation script:**
   ```bash
   cd tv-arm-controller
   chmod +x install.sh
   ./install.sh
   ```

### Manual Installation Steps

1. **Update system:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install dependencies:**
   ```bash
   sudo apt install -y python3 python3-pip python3-venv i2c-tools
   ```

3. **Enable I2C:**
   ```bash
   sudo raspi-config nonint do_i2c 0
   sudo usermod -a -G i2c $USER
   ```

4. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

Edit `config.yaml` to match your setup:

### Hardware Settings
```yaml
hardware:
  servo_x_pin: 18      # GPIO pin for X-axis servo
  servo_y_pin: 19      # GPIO pin for Y-axis servo
  ads1115:
    address: 0x48      # I2C address of ADS1115
  potentiometer:
    x_axis_channel: 0  # ADS1115 channel for X position
    y_axis_channel: 2  # ADS1115 channel for Y position
```

### Home Assistant MQTT Settings
```yaml
home_assistant:
  mqtt:
    broker: "192.168.1.100"     # Your Home Assistant IP
    username: "mqtt_user"        # MQTT username
    password: "mqtt_password"    # MQTT password
```

## 🎛️ Usage

### First Time Setup

1. **Test hardware connections:**
   ```bash
   ./test.sh
   ```

2. **Calibrate position sensors:**
   ```bash
   ./calibrate.sh
   ```
   This will move servos to extreme positions and measure voltages.

3. **Update config with calibration values:**
   ```yaml
   hardware:
     calibration:
       x_axis:
         min_voltage: 0.123  # From calibration
         max_voltage: 3.234  # From calibration
       y_axis:
         min_voltage: 0.156  # From calibration  
         max_voltage: 3.198  # From calibration
   ```

### Service Management

```bash
# Enable service to start on boot
sudo systemctl enable tv-arm-controller

# Start service
./start.sh

# Check status  
./status.sh

# View logs
./logs.sh

# Stop service
./stop.sh
```

### Home Assistant Integration

The TV Arm will automatically appear in Home Assistant as:

1. **Cover Entity** - `cover.tv_arm`
   - Open/Close/Stop commands
   - Position control (0-100%)

2. **Number Entities** - Individual axis control
   - `number.tv_arm_x_position` - X-axis position (0-100%)
   - `number.tv_arm_y_position` - Y-axis position (0-100%)

### Manual Control

```bash
# Run test sequence
./test.sh

# Run calibration
./calibrate.sh

# Interactive mode
source venv/bin/activate
python main.py
```

## 🔍 Troubleshooting

### Common Issues

1. **I2C device not found:**
   ```bash
   # Check I2C is enabled
   sudo raspi-config
   
   # Scan for devices
   i2cdetect -y 1
   
   # Should show device at 0x48
   ```

2. **Permission denied on GPIO:**
   ```bash
   # Add user to gpio group
   sudo usermod -a -G gpio $USER
   newgrp gpio
   ```

3. **MQTT connection failed:**
   - Check Home Assistant IP address in config.yaml
   - Verify MQTT broker is running
   - Check username/password

4. **Servo not moving:**
   - Check power supply (servos need 5V)
   - Verify GPIO pin connections
   - Check servo signal wire connection

### Log Analysis

```bash
# View service logs
sudo journalctl -u tv-arm-controller -f

# View application log file
tail -f /var/log/tv-arm-controller.log

# Debug mode
source venv/bin/activate
python main.py --config config.yaml
```

### Hardware Testing

```bash
# Test I2C connection
i2cdetect -y 1

# Test GPIO pins
gpio readall

# Test potentiometer readings
source venv/bin/activate
python -c "
from tv_arm_controller import TVArmController
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
controller = TVArmController(config)
print(controller.get_current_position())
"
```

## 🛠️ Development

### Project Structure
```
tv-arm-controller/
├── main.py                          # Main application
├── tv_arm_controller.py             # Hardware control
├── home_assistant_integration.py    # MQTT/HA integration  
├── config.yaml                      # Configuration
├── requirements.txt                 # Python dependencies
├── install.sh                       # Installation script
├── systemd/                         # Service files
├── start.sh, stop.sh, status.sh     # Helper scripts
└── README.md                        # This file
```

### Adding Features

1. **Custom movement patterns:**
   - Modify `TVArmController.set_position()`
   - Add new MQTT command handlers

2. **Additional sensors:**
   - Use remaining ADS1115 channels (A1, A3)
   - Add sensor classes in `tv_arm_controller.py`

3. **Safety features:**
   - Implement limit switches
   - Add current monitoring

### Configuration Options

See `config.yaml` for all available options:
- Hardware pin assignments
- Servo parameters (pulse width, angles)
- Position limits and calibration
- MQTT topics and device info
- Logging and safety settings

## 📋 Specifications

- **Operating System:** Raspberry Pi OS (32-bit or 64-bit)
- **Python Version:** 3.7+
- **Power Requirements:** 5V/3A (Pi + 2 servos)
- **I2C Speed:** Standard (100kHz) or Fast (400kHz)
- **Servo Control:** 50Hz PWM, 1-2ms pulse width
- **Position Resolution:** 16-bit (ADS1115) = ~0.05mV resolution
- **Update Rate:** 10Hz position updates, 1Hz MQTT publishing

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is open source. Feel free to modify and distribute.

## 🙏 Acknowledgments

- Adafruit for excellent CircuitPython libraries
- Home Assistant community for MQTT discovery documentation
- Raspberry Pi Foundation for great hardware and documentation

---

**Happy controlling! 🎮📺**

