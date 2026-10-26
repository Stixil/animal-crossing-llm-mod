@echo off
echo 🐬 Animal Crossing LLM Mod - Easy Installer
echo =============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo ✅ Python found: 
python --version
echo.

REM Create virtual environment
echo 🔧 Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo 🔧 Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 🔧 Installing dependencies...
pip install -r requirements.txt

echo.
echo 🎉 Installation complete!
echo.
echo Next steps:
echo 1. Create a .env file with your API keys
echo 2. Run Animal Crossing in Dolphin emulator
echo 3. Start the mod with: python ac_parser_encoder.py --watch
echo.
echo For help, see README.md
echo.
echo Happy modding! 🎮✨
pause
