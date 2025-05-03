#!/bin/bash
# Run the Telegram forwarder locally for development/testing

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "Python is not installed. Please install Python first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "pip is not installed. Please install pip first."
    exit 1
fi

# Install dependencies if not already installed
echo "Checking dependencies..."
pip install -r requirements.txt.render

# Create necessary directories
mkdir -p tmp
mkdir -p logs

# Run the application
echo "Starting Telegram Forwarder..."
python main.py