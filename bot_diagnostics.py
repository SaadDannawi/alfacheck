#!/usr/bin/env python3
"""
Telegram Bot Diagnostics Script
This script helps identify and fix common issues with the Telegram bot.
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any

# Import bot modules
try:
    from bot_config import bot_config
    from database import db_manager
    from user_manager import user_manager
    from language_manager import language_manager
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError as e:
    print(f"[ERROR] Failed to import required modules: {e}")
    sys.exit(1)

class BotDiagnostics:
    """Comprehensive bot diagnostics."""
    
    def __init__(self):
        self.issues = []
        self.fixes = []
        
    def log_issue(self, category: str, issue: str, fix: str = None):
        """Log an issue and potential fix."""
        self.issues.append({"category": category, "issue": issue, "fix": fix})
        if fix:
            self.fixes.append(fix)
    
    def check_configuration(self) -> bool:
        """Check bot configuration."""
        print("\n🔍 Checking Bot Configuration...")
        
        # Check bot token
        token = bot_config.get_bot_token()
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            self.log_issue("Configuration", "Invalid bot token", 
                          "Set BOT_TOKEN in bot_config.py or TELEGRAM_BOT_TOKEN environment variable")
            return False
        
        # Check authorization settings
        if bot_config.ENABLE_USER_AUTHORIZATION and not bot_config.ALLOW_PUBLIC_ACCESS:
            print(f"   ✓ Authorization enabled - Admin IDs: {bot_config.ADMIN_USER_IDS}")
        elif bot_config.ALLOW_PUBLIC_ACCESS:
            print(f"   ⚠️  Public access enabled - Anyone can use the bot")
        else:
            print(f"   ✓ Authorization disabled - All users can access")
        
        print(f"   ✓ Bot token configured")
        print(f"   ✓ Max accounts per request: {bot_config.MAX_ACCOUNTS_PER_REQUEST}")
        print(f"   ✓ Batch processing: {'Enabled' if bot_config.ENABLE_BATCH_PROCESSING else 'Disabled'}")
        
        return True
    
    def check_database(self) -> bool:
        """Check database connectivity and structure."""
        print("\n🔍 Checking Database...")
        
        try:
            # Test database connection
            with db_manager.get_session() as session:
                # Test basic query
                from database import User
                user_count = session.query(User).count()
                print(f"   ✓ Database connected - {user_count} users in database")
                
                # Check if admin user exists and is authorized
                admin_ids = bot_config.ADMIN_USER_IDS
                for admin_id in admin_ids:
                    admin_user = session.query(User).filter(User.user_id == admin_id).first()
                    if admin_user:
                        if admin_user.is_authorized:
                            print(f"   ✓ Admin user {admin_id} exists and is authorized")
                        else:
                            print(f"   ⚠️  Admin user {admin_id} exists but not authorized")
                            self.log_issue("Database", f"Admin user {admin_id} not authorized",
                                          f"Run: db_manager.authorize_user({admin_id})")
                    else:
                        print(f"   ⚠️  Admin user {admin_id} not found in database")
                        self.log_issue("Database", f"Admin user {admin_id} not in database",
                                      f"User will be created on first /start command")
                
                return True
                
        except Exception as e:
            self.log_issue("Database", f"Database connection failed: {e}",
                          "Check database file permissions and SQLite installation")
            print(f"   ❌ Database error: {e}")
            return False
    
    async def check_telegram_api(self) -> bool:
        """Check Telegram API connectivity."""
        print("\n🔍 Checking Telegram API...")
        
        try:
            token = bot_config.get_bot_token()
            bot = Bot(token=token)
            
            # Test API connection
            me = await bot.get_me()
            print(f"   ✓ Bot connected: @{me.username} ({me.first_name})")
            
            # Test webhook status
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                print(f"   ⚠️  Webhook is set: {webhook_info.url}")
                self.log_issue("Telegram API", "Webhook is configured",
                              "Delete webhook to use polling: await bot.delete_webhook()")
            else:
                print(f"   ✓ No webhook configured (polling mode)")
            
            return True
            
        except TelegramError as e:
            self.log_issue("Telegram API", f"Telegram API error: {e}",
                          "Check bot token and internet connection")
            print(f"   ❌ Telegram API error: {e}")
            return False
        except Exception as e:
            self.log_issue("Telegram API", f"Unexpected error: {e}",
                          "Check bot configuration and dependencies")
            print(f"   ❌ Unexpected error: {e}")
            return False
    
    def check_error_handling(self) -> bool:
        """Check error handling in the bot code."""
        print("\n🔍 Checking Error Handling...")
        
        # Check if there are unhandled exceptions in logs
        log_file = "scraper.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                    
                # Look for common error patterns
                if "BadRequest: Can't parse entities" in log_content:
                    self.log_issue("Error Handling", "Markdown parsing errors in messages",
                                  "Fix markdown formatting in error messages")
                    print(f"   ⚠️  Found markdown parsing errors")
                
                if "No error handlers are registered" in log_content:
                    self.log_issue("Error Handling", "No error handlers registered",
                                  "Add error handlers to the bot application")
                    print(f"   ⚠️  No error handlers registered")
                
                if "ValueError: No password provided" in log_content:
                    print(f"   ⚠️  Users sending messages without passwords")
                
                print(f"   ✓ Log file analyzed")
                
            except Exception as e:
                print(f"   ⚠️  Could not read log file: {e}")
        else:
            print(f"   ⚠️  No log file found")
        
        return True
    
    def check_user_authorization(self) -> bool:
        """Check user authorization issues."""
        print("\n🔍 Checking User Authorization...")
        
        try:
            with db_manager.get_session() as session:
                from database import User
                
                # Check authorization settings
                if bot_config.ENABLE_USER_AUTHORIZATION and not bot_config.ALLOW_PUBLIC_ACCESS:
                    authorized_users = session.query(User).filter(User.is_authorized == True).all()
                    print(f"   ✓ Authorization required - {len(authorized_users)} authorized users")
                    
                    if len(authorized_users) == 0:
                        self.log_issue("Authorization", "No users are authorized",
                                      "Authorize admin users or enable public access")
                        print(f"   ⚠️  No users are authorized to use the bot")
                
                elif bot_config.ALLOW_PUBLIC_ACCESS:
                    print(f"   ✓ Public access enabled - All users can use the bot")
                
                else:
                    print(f"   ✓ Authorization disabled - All users can use the bot")
                
                return True
                
        except Exception as e:
            print(f"   ❌ Authorization check failed: {e}")
            return False
    
    def generate_fixes(self) -> List[str]:
        """Generate Python code to fix identified issues."""
        fixes = []
        
        # Fix markdown parsing errors
        if any("markdown parsing" in issue["issue"].lower() for issue in self.issues):
            fixes.append("""
# Fix markdown parsing errors
def fix_markdown_errors():
    # Update error messages to avoid markdown parsing issues
    # Replace problematic characters in error messages
    pass
""")
        
        # Fix authorization issues
        if any("not authorized" in issue["issue"].lower() for issue in self.issues):
            admin_ids = bot_config.ADMIN_USER_IDS
            fixes.append(f"""
# Fix authorization issues
def fix_authorization():
    from database import db_manager
    
    # Authorize admin users
    admin_ids = {admin_ids}
    for admin_id in admin_ids:
        db_manager.authorize_user(admin_id)
        print(f"Authorized user {{admin_id}}")
""")
        
        # Add error handlers
        if any("error handlers" in issue["issue"].lower() for issue in self.issues):
            fixes.append("""
# Add error handlers to bot
def add_error_handlers(application):
    async def error_handler(update, context):
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later.",
                    parse_mode=None  # Disable markdown to avoid parsing errors
                )
            except Exception:
                pass  # Ignore if we can't send error message
    
    application.add_error_handler(error_handler)
""")
        
        return fixes
    
    async def run_diagnostics(self) -> Dict[str, Any]:
        """Run all diagnostic checks."""
        print("🚀 Starting Telegram Bot Diagnostics...")
        print("=" * 50)
        
        results = {
            "configuration": self.check_configuration(),
            "database": self.check_database(),
            "telegram_api": await self.check_telegram_api(),
            "error_handling": self.check_error_handling(),
            "user_authorization": self.check_user_authorization()
        }
        
        print("\n" + "=" * 50)
        print("📋 DIAGNOSTIC SUMMARY")
        print("=" * 50)
        
        # Show results
        for check, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{check.replace('_', ' ').title()}: {status}")
        
        # Show issues
        if self.issues:
            print("\n🚨 ISSUES FOUND:")
            for i, issue in enumerate(self.issues, 1):
                print(f"{i}. [{issue['category']}] {issue['issue']}")
                if issue['fix']:
                    print(f"   💡 Fix: {issue['fix']}")
        
        # Generate fixes
        fixes = self.generate_fixes()
        if fixes:
            print("\n🔧 GENERATED FIXES:")
            for fix in fixes:
                print(fix)
        
        return results

async def main():
    """Main diagnostic function."""
    diagnostics = BotDiagnostics()
    results = await diagnostics.run_diagnostics()
    
    # Quick fix for common issues
    print("\n🔧 APPLYING QUICK FIXES...")
    
    # Fix authorization for admin users
    try:
        admin_ids = bot_config.ADMIN_USER_IDS
        for admin_id in admin_ids:
            if db_manager.authorize_user(admin_id):
                print(f"✅ Authorized admin user {admin_id}")
            else:
                print(f"ℹ️  Admin user {admin_id} already authorized")
    except Exception as e:
        print(f"❌ Failed to authorize admin users: {e}")
    
    # Summary
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All diagnostics passed! The bot should work correctly.")
    else:
        print("\n⚠️  Some issues were found. Please review the fixes above.")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())