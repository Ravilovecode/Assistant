#!/usr/bin/env python3
"""
Setup script for AI Receptionist
This script helps configure the environment and test the setup.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version OK: {sys.version.split()[0]}")
    return True

def install_requirements():
    """Install required packages"""
    try:
        print("📦 Installing requirements...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install requirements")
        return False

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found")
        return False
    
    required_vars = ['GEMINI_API_KEY', 'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'SECRET_KEY']
    missing_vars = []
    
    with open('.env', 'r') as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=your_" in content or var not in content:
                missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ Please update these variables in .env file: {', '.join(missing_vars)}")
        return False
    
    print("✅ Environment variables configured")
    return True

def test_imports():
    """Test if all required modules can be imported"""
    modules = [
        'flask', 'flask_socketio', 'google.generativeai', 'twilio.rest',
        'speech_recognition', 'gtts', 'requests', 'dotenv'
    ]
    
    failed_imports = []
    for module in modules:
        try:
            __import__(module)
        except ImportError:
            failed_imports.append(module)
    
    if failed_imports:
        print(f"❌ Failed to import: {', '.join(failed_imports)}")
        return False
    
    print("✅ All required modules imported successfully")
    return True

def main():
    print("🤖 AI Receptionist Setup")
    print("=" * 30)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install requirements
    if not install_requirements():
        return False
    
    # Test imports
    if not test_imports():
        print("Run 'pip install -r requirements.txt' to install missing packages")
        return False
    
    # Check environment file
    if not check_env_file():
        print("\n📋 Next steps:")
        print("1. Update the .env file with your actual API keys")
        print("2. Get Gemini API key: https://makersuite.google.com/app/apikey")
        print("3. Get Twilio credentials: https://console.twilio.com/")
        return False
    
    print("\n🎉 Setup completed successfully!")
    print("\n🚀 To start the application:")
    print("python app.py")
    print("\n🌐 Then open: http://localhost:5000")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)