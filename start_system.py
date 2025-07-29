#!/usr/bin/env python3
"""
Startup script for the Telegram Bot Dashboard System.
This script starts both the Telegram bot and the web dashboard.
"""

import subprocess
import sys
import os
import time
import threading
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_requirements():
    """Check if all required packages are installed."""
    try:
        import flask
        import flask_cors
        import telegram
        import sqlalchemy
        logger.info("[SUCCESS] All required packages are available")
        return True
    except ImportError as e:
        logger.error(f"[ERROR] Missing required package: {e}")
        print(f"\n[ERROR] Missing required package: {e}")
        print("Please install requirements with: pip install -r requirements.txt")
        return False

def run_migration():
    """Run database migration if needed."""
    try:
        logger.info("Running database migration...")
        result = subprocess.run([sys.executable, "migrate_transactions.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("[SUCCESS] Database migration completed")
            print("[SUCCESS] Database migration completed")
            return True
        else:
            logger.error(f"[ERROR] Migration failed: {result.stderr}")
            print(f"[ERROR] Migration failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"[ERROR] Migration error: {e}")
        print(f"[ERROR] Migration error: {e}")
        return False

def start_dashboard():
    """Start the Flask dashboard in a separate thread."""
    try:
        logger.info("Starting dashboard server...")
        # Start dashboard as a subprocess with output redirection
        dashboard_process = subprocess.Popen(
            [sys.executable, "dashboard.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        # Check if it's still running
        if dashboard_process.poll() is None:
            logger.info("[SUCCESS] Dashboard server started successfully")
            print("[SUCCESS] Dashboard server started at http://localhost:5000")
            return dashboard_process
        else:
            logger.error("[ERROR] Dashboard failed to start")
            print("[ERROR] Dashboard failed to start")
            return None
            
    except Exception as e:
        logger.error(f"[ERROR] Error starting dashboard: {e}")
        print(f"[ERROR] Error starting dashboard: {e}")
        return None

def start_bot():
    """Start the Telegram bot."""
    try:
        logger.info("Starting Telegram bot...")
        # Start bot as a subprocess with output redirection to a log file
        bot_log = open("bot_error.log", "a")
        bot_process = subprocess.Popen(
            [sys.executable, "telegram_bot.py"],
            stdout=bot_log,
            stderr=bot_log,
            text=True
        )
        time.sleep(3)
        if bot_process.poll() is None:
            logger.info("[SUCCESS] Telegram bot started successfully")
            print("[SUCCESS] Telegram bot started successfully")
            return bot_process
        else:
            logger.error("[ERROR] Bot failed to start")
            print("[ERROR] Bot failed to start")
            return None
    except Exception as e:
        logger.error(f"[ERROR] Error starting bot: {e}")
        print(f"[ERROR] Error starting bot: {e}")
        return None

def main():
    """Main function to start the entire system."""
    print("🚀 Starting Telegram Bot Dashboard System...")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("telegram_bot.py"):
        print("❌ Error: telegram_bot.py not found in current directory")
        print("Please run this script from the bot's directory")
        return
    
    # Check requirements
    if not check_requirements():
        return
    
    # Run migration
    if not run_migration():
        print("⚠️  Migration failed, but continuing...")
    
    # Start dashboard
    dashboard_process = start_dashboard()
    if not dashboard_process:
        print("❌ Failed to start dashboard. Exiting.")
        return
    
    # Start bot
    bot_process = start_bot()
    if not bot_process:
        print("❌ Failed to start bot. Stopping dashboard.")
        dashboard_process.terminate()
        return
    
    print("\n" + "=" * 50)
    print("🎉 System started successfully!")
    print("\n📊 Dashboard: http://localhost:5000")
    print("🤖 Telegram Bot: Running and ready to receive messages")
    print("\n💡 Tips:")
    print("   - Send numbers to your bot to start scanning")
    print("   - Each scan will generate a unique transaction ID")
    print("   - Access detailed results via the dashboard link")
    print("   - Press Ctrl+C to stop both services")
    print("\n" + "=" * 50)
    
    try:
        # Keep the script running and monitor processes
        while True:
            time.sleep(10)  # Increased interval to reduce overhead
            
            # Check if processes are still running
            if dashboard_process.poll() is not None:
                logger.error("[ERROR] Dashboard process stopped unexpectedly")
                print("[ERROR] Dashboard process stopped unexpectedly")
                break
                
            if bot_process.poll() is not None:
                logger.error("[ERROR] Bot process stopped unexpectedly")
                print("[ERROR] Bot process stopped unexpectedly")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Shutting down system...")
        
    finally:
        # Clean shutdown
        if dashboard_process and dashboard_process.poll() is None:
            dashboard_process.terminate()
            logger.info("Dashboard process terminated")
            
        if bot_process and bot_process.poll() is None:
            bot_process.terminate()
            logger.info("Bot process terminated")
            
        print("✅ System shutdown complete")

if __name__ == "__main__":
    main()