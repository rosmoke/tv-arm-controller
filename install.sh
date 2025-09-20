#!/bin/bash

# TV Arm Controller Installation Script
# For Raspberry Pi Zero 2 W running Raspberry Pi OS

set -e  # Exit on any error

echo "=========================================="
echo "TV Arm Controller Installation Script"
echo "=========================================="
echo

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi hardware."
    echo "Some hardware-specific packages may not install correctly."
    echo
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "Please do not run this script as root. Run as pi user instead."
    exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="tv-arm-controller"
INSTALL_DIR="/opt/$PROJECT_NAME"
SERVICE_NAME="tv-arm-controller"
USER=$(whoami)

echo "Installation directory: $INSTALL_DIR"
echo "Running as user: $USER"
echo "Project directory: $SCRIPT_DIR"
echo

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Update system packages
echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install system dependencies
echo "Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    i2c-tools \
    build-essential \
    libi2c-dev \
    python3-smbus

# Enable I2C interface
echo "Enabling I2C interface..."
sudo raspi-config nonint do_i2c 0

# Add user to i2c group
echo "Adding $USER to i2c group..."
sudo usermod -a -G i2c $USER

# Create installation directory
echo "Creating installation directory..."
sudo mkdir -p $INSTALL_DIR
sudo chown $USER:$USER $INSTALL_DIR

# Copy project files
echo "Copying project files..."
cp -r $SCRIPT_DIR/* $INSTALL_DIR/
cd $INSTALL_DIR

# Create Python virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip in virtual environment
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create log directory
echo "Creating log directory..."
sudo mkdir -p /var/log
sudo touch /var/log/tv-arm-controller.log
sudo chown $USER:$USER /var/log/tv-arm-controller.log

# Create systemd service directory if it doesn't exist
mkdir -p systemd

# Create systemd service file
echo "Creating systemd service file..."
cat > systemd/tv-arm-controller.service << EOF
[Unit]
Description=TV Arm Controller with Home Assistant Integration
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py --daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tv-arm-controller

# Security settings
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$INSTALL_DIR /var/log
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes

[Install]
WantedBy=multi-user.target
EOF

# Install systemd service
echo "Installing systemd service..."
sudo cp systemd/tv-arm-controller.service /etc/systemd/system/
sudo systemctl daemon-reload

# Create configuration backup
echo "Creating configuration backup..."
cp config.yaml config.yaml.example

# Set proper permissions
echo "Setting file permissions..."
chmod +x main.py
chmod +x tv_arm_controller.py
chmod +x home_assistant_integration.py
chmod 644 config.yaml
chmod 644 requirements.txt

# Test I2C connection
echo "Testing I2C connection..."
if command_exists i2cdetect; then
    echo "Scanning I2C bus for devices..."
    i2cdetect -y 1 || echo "No I2C devices found (this is normal if ADS1115 is not connected yet)"
else
    echo "i2cdetect not available, skipping I2C test"
fi

# Create helper scripts
echo "Creating helper scripts..."

# Start script
cat > start.sh << 'EOF'
#!/bin/bash
sudo systemctl start tv-arm-controller
sudo systemctl status tv-arm-controller
EOF
chmod +x start.sh

# Stop script
cat > stop.sh << 'EOF'
#!/bin/bash
sudo systemctl stop tv-arm-controller
sudo systemctl status tv-arm-controller
EOF
chmod +x stop.sh

# Status script
cat > status.sh << 'EOF'
#!/bin/bash
echo "Service Status:"
sudo systemctl status tv-arm-controller
echo
echo "Recent Logs:"
sudo journalctl -u tv-arm-controller -n 20 --no-pager
EOF
chmod +x status.sh

# Logs script
cat > logs.sh << 'EOF'
#!/bin/bash
echo "Following TV Arm Controller logs (Ctrl+C to exit):"
sudo journalctl -u tv-arm-controller -f
EOF
chmod +x logs.sh

# Test script
cat > test.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python main.py --test
EOF
chmod +x test.sh

# Calibrate script
cat > calibrate.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python main.py --calibrate
EOF
chmod +x calibrate.sh

echo
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Edit the configuration file:"
echo "   sudo nano $INSTALL_DIR/config.yaml"
echo
echo "2. Update MQTT broker settings for your Home Assistant instance"
echo
echo "3. Connect your hardware according to the wiring diagram"
echo
echo "4. Test the hardware connection:"
echo "   cd $INSTALL_DIR && ./test.sh"
echo
echo "5. Calibrate the position sensors:"
echo "   cd $INSTALL_DIR && ./calibrate.sh"
echo
echo "6. Enable and start the service:"
echo "   sudo systemctl enable tv-arm-controller"
echo "   cd $INSTALL_DIR && ./start.sh"
echo
echo "Useful commands:"
echo "- Start service:    cd $INSTALL_DIR && ./start.sh"
echo "- Stop service:     cd $INSTALL_DIR && ./stop.sh"
echo "- Check status:     cd $INSTALL_DIR && ./status.sh"
echo "- View logs:        cd $INSTALL_DIR && ./logs.sh"
echo "- Run test:         cd $INSTALL_DIR && ./test.sh"
echo "- Calibrate:        cd $INSTALL_DIR && ./calibrate.sh"
echo
echo "Configuration file: $INSTALL_DIR/config.yaml"
echo "Log file: /var/log/tv-arm-controller.log"
echo
echo "The TV Arm Controller will appear in Home Assistant automatically"
echo "once the service is running and connected to your MQTT broker."
echo
echo "IMPORTANT: You may need to log out and log back in for the i2c"
echo "group membership to take effect, or run: newgrp i2c"
echo
echo "Installation complete!"
EOF

