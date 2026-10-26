#!/bin/bash

echo "🐬 Animal Crossing LLM Mod - Easy Installer"
echo "============================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "🔧 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "🔧 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Next steps:"
echo "1. Create a .env file with your API keys"
echo "2. Run Animal Crossing in Dolphin emulator"
echo "3. Start the mod with: python ac_parser_encoder.py --watch"
echo ""
echo "For help, see README.md"
echo ""
echo "Happy modding! 🎮✨"
