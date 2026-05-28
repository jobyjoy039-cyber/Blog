#!/usr/bin/env bash
set -e

# Install Python dependencies
pip install -r requirements.txt --quiet

# Create necessary directories
mkdir -p uploads outputs weights

# Start the Flask app
python app.py
