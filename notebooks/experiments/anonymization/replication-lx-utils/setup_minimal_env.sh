#!/bin/bash

# Setup script for minimal langextract environment

echo "Setting up minimal langextract environment..."

# Create virtual environment
python3 -m venv minimal_env

# Activate virtual environment
source minimal_env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install minimal requirements
pip install -r requirements.txt

# Install langextract in development mode
cd /Users/sofi/Desktop/CollectiveAI/langextract
pip install -e .

echo "Environment setup complete!"
echo "To activate: source minimal_env/bin/activate"
echo "To run converter: python minimal_converter.py"
