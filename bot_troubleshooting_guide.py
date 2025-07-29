#!/usr/bin/env python3
"""
Telegram Bot Troubleshooting Guide and Test Script
This script provides comprehensive troubleshooting steps and tests for the Telegram bot.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any

# Import bot modules
try:
    from bot_config import bot_config
    from database import db_manager
    from user_manager import user_manager
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError as e:
    print(f"[ERROR] Failed to import required modules: {e}")
    sys.exit(1)

class BotTroubleshooter:
    """Comprehensive bot troubleshooting."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f"🔧 {title}")
        print(f"{'='*60}")
    
    def print_section(self, title: str):
        """Print a formatted section header."""
        print(f"\n📋 {title}")
        print(f"{'-'*40}")
    
    async def test_bot_connectivity(self) -> bool:
        """Test basic bot connectivity."""
        self.print_section("Testing Bot Connectivity")
        
        try:
            token = bot_config.get_bot_token()
            if not token:
                print("❌ No bot token configured")
                return False
            
            bot = Bot(token=token)
            me = await bot.get_me()
            print(f"✅ Bot connected successfully: @{me.username} ({me.first_name})")
            print(f"   Bot ID: {me.id}")
            print(f"   Can join groups: {me.can_join_groups}")
            print(f"   Can read all group messages: {me.can_read_all_group_messages}")
            print(f"   Supports inline queries: {me.supports_inline_queries}")
            
            # Test webhook status
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                print(f"⚠️  Webhook configured: {webhook_info.url}")
                print(f"   Pending updates: {webhook_info.pending_update_count}")
                print(f"   💡 Consider deleting webhook for polling mode")
            else:
                print(f"✅ No webhook configured (polling mode active)")
            
            return True
            
        except TelegramError as e:
            print(f"❌ Telegram API error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test database connectivity and user authorization."""
        self.print_section("Testing Database Connectivity")
        
        try:
            with db_manager.get_session() as session:
                from database import User, UserSession
                
                # Test basic queries
                user_count = session.query(User).count()
                session_count = session.query(UserSession).filter(UserSession.is_active == True).count()
                
                print(f"✅ Database connected successfully")
                print(f"   Total users: {user_count}")
                print(f"   Active sessions: {session_count}")
                
                # Check admin users
                admin_ids = bot_config.ADMIN_USER_IDS
                print(f"\n👑 Admin Users Status:")
                for admin_id in admin_ids:
                    admin_user = session.query(User).filter(User.user_id == admin_id).first()
                    if admin_user:
                        status = "✅ Authorized" if admin_user.is_authorized else "❌ Not Authorized"
                        print(f"   User {admin_id}: {status}")
                        if not admin_user.is_authorized:
                            print(f"      💡 Fix: db_manager.authorize_user({admin_id})")
                    else:
                        print(f"   User {admin_id}: ⚠️  Not in database (will be created on first /start)")
                
                # Check authorization settings
                print(f"\n🔐 Authorization Settings:")
                print(f"   Authorization enabled: {bot_config.ENABLE_USER_AUTHORIZATION}")
                print(f"   Public access allowed: {bot_config.ALLOW_PUBLIC_ACCESS}")
                
                if bot_config.ENABLE_USER_AUTHORIZATION and not bot_config.ALLOW_PUBLIC_ACCESS:
                    authorized_count = session.query(User).filter(User.is_authorized == True).count()
                    print(f"   Authorized users: {authorized_count}")
                    if authorized_count == 0:
                        print(f"   ⚠️  No users are authorized to use the bot")
                
                return True
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False
    
    def test_configuration(self) -> bool:
        """Test bot configuration."""
        self.print_section("Testing Bot Configuration")
        
        try:
            # Test basic configuration
            print(f"✅ Configuration loaded successfully")
            print(f"   Max accounts per request: {bot_config.MAX_ACCOUNTS_PER_REQUEST}")
            print(f"   Batch processing: {'Enabled' if bot_config.ENABLE_BATCH_PROCESSING else 'Disabled'}")
            
            if bot_config.ENABLE_BATCH_PROCESSING:
                print(f"   Batch size: {bot_config.BATCH_SIZE}")
                print(f"   Max concurrent workers: {bot_config.MAX_CONCURRENT_WORKERS}")
                print(f"   Batch delay: {bot_config.BATCH_DELAY}s")
                print(f"   Request delay: {bot_config.REQUEST_DELAY}s")
            
            print(f"   Max concurrent users: {bot_config.MAX_CONCURRENT_USERS}")
            print(f"   Rate limit: {bot_config.USER_RATE_LIMIT_MINUTES} minutes")
            print(f"   Max requests per hour: {bot_config.MAX_REQUESTS_PER_USER_PER_HOUR}")
            
            # Validate configuration
            is_valid, message = bot_config.validate_config()
            if is_valid:
                print(f"✅ Configuration validation passed")
            else:
                print(f"❌ Configuration validation failed: {message}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Configuration error: {e}")
            return False
    
    def analyze_logs(self) -> Dict[str, Any]:
        """Analyze log files for common issues."""
        self.print_section("Analyzing Log Files")
        
        log_analysis = {
            "errors_found": [],
            "warnings_found": [],
            "recommendations": []
        }
        
        log_file = "scraper.log"
        if not os.path.exists(log_file):
            print(f"⚠️  Log file not found: {log_file}")
            return log_analysis
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # Analyze common error patterns
            error_patterns = {
                "BadRequest: Can't parse entities": "Markdown parsing errors in messages",
                "No error handlers are registered": "Missing error handlers",
                "ValueError: No password provided": "Users not providing passwords",
                "TelegramError": "Telegram API errors",
                "Database connection": "Database connectivity issues",
                "Authorization": "User authorization issues"
            }
            
            print(f"✅ Analyzing log file: {log_file}")
            
            for pattern, description in error_patterns.items():
                if pattern.lower() in log_content.lower():
                    log_analysis["errors_found"].append(description)
                    print(f"   ❌ Found: {description}")
            
            # Count recent errors (last 100 lines)
            recent_lines = log_content.split('\n')[-100:]
            recent_errors = sum(1 for line in recent_lines if '[ERROR]' in line)
            recent_warnings = sum(1 for line in recent_lines if '[WARNING]' in line)
            
            print(f"   Recent errors (last 100 lines): {recent_errors}")
            print(f"   Recent warnings (last 100 lines): {recent_warnings}")
            
            if not log_analysis["errors_found"]:
                print(f"   ✅ No critical error patterns found")
            
            return log_analysis
            
        except Exception as e:
            print(f"❌ Failed to analyze logs: {e}")
            return log_analysis
    
    def provide_solutions(self, issues: List[str]):
        """Provide solutions for common issues."""
        self.print_section("Recommended Solutions")
        
        solutions = {
            "Markdown parsing errors in messages": [
                "✅ FIXED: Added proper error handler to telegram_bot.py",
                "✅ FIXED: Updated error messages to escape markdown characters",
                "Restart the bot to apply fixes"
            ],
            "Missing error handlers": [
                "✅ FIXED: Added error handler to telegram_bot.py",
                "Restart the bot to apply fixes"
            ],
            "Users not providing passwords": [
                "Educate users to include 'pass: password' in their messages",
                "Encourage users to set default password with /setpassword",
                "This is normal user behavior, not a critical issue"
            ],
            "User authorization issues": [
                "✅ FIXED: Authorized admin users automatically",
                "Use /authorize command to authorize additional users",
                "Consider enabling public access if appropriate"
            ]
        }
        
        if not issues:
            print("🎉 No critical issues found! The bot should work correctly.")
            return
        
        for issue in issues:
            if issue in solutions:
                print(f"\n🔧 {issue}:")
                for solution in solutions[issue]:
                    print(f"   • {solution}")
    
    def generate_test_commands(self):
        """Generate test commands for manual testing."""
        self.print_section("Manual Testing Commands")
        
        print("📱 Test these commands in your Telegram bot:")
        print("\n1. Basic Commands:")
        print("   /start - Should show welcome message")
        print("   /language - Should show language options")
        print("   /users - Should show user list (admin only)")
        
        print("\n2. Authorization Commands (admin only):")
        print("   /authorize @username - Authorize a user")
        print("   /revoke @username - Revoke user authorization")
        
        print("\n3. Account Processing:")
        print("   Send account numbers with password:")
        print("   ```")
        print("   03123456")
        print("   71000000")
        print("   pass: your_password")
        print("   ```")
        
        print("\n4. Password Management:")
        print("   /setpassword your_default_password")
        print("   Then send just account numbers without password")
        
        print("\n🔍 Expected Behavior:")
        print("   • /start should work for everyone")
        print("   • Other commands should work only for authorized users")
        print("   • Account processing should show progress messages")
        print("   • Errors should be handled gracefully")
    
    async def run_full_diagnostics(self):
        """Run complete diagnostic suite."""
        self.print_header("TELEGRAM BOT TROUBLESHOOTING")
        
        print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        config_ok = self.test_configuration()
        db_ok = self.test_database_connectivity()
        api_ok = await self.test_bot_connectivity()
        log_analysis = self.analyze_logs()
        
        # Summary
        self.print_section("Diagnostic Summary")
        
        tests = {
            "Configuration": config_ok,
            "Database": db_ok,
            "Telegram API": api_ok
        }
        
        all_passed = all(tests.values())
        
        for test_name, passed in tests.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test_name}: {status}")
        
        # Provide solutions
        self.provide_solutions(log_analysis["errors_found"])
        
        # Generate test commands
        self.generate_test_commands()
        
        # Final recommendation
        self.print_section("Final Recommendation")
        
        if all_passed and not log_analysis["errors_found"]:
            print("🎉 SUCCESS: All diagnostics passed!")
            print("\n✅ Your bot should now work correctly.")
            print("\n🚀 Next steps:")
            print("   1. Start the bot: python telegram_bot.py")
            print("   2. Test with /start command")
            print("   3. Try processing some account numbers")
        else:
            print("⚠️  ISSUES DETECTED: Some problems were found.")
            print("\n🔧 Recommended actions:")
            print("   1. Review the solutions above")
            print("   2. Apply the suggested fixes")
            print("   3. Restart the bot")
            print("   4. Run this diagnostic again")
        
        return all_passed and not log_analysis["errors_found"]

async def main():
    """Main function."""
    troubleshooter = BotTroubleshooter()
    success = await troubleshooter.run_full_diagnostics()
    
    if success:
        print("\n🎯 Ready to start the bot!")
    else:
        print("\n🔄 Please address the issues and run diagnostics again.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())