"""Configuration file for Telegram Bot."""

import os
from typing import Optional

# Bot Configuration
class BotConfig:
    """Telegram bot configuration."""
    
    # Bot Token - Get this from @BotFather on Telegram
    # Method 1: Set directly here (not recommended for production)
    BOT_TOKEN: str = "7925074479:AAHx9cn0h_6gQSVcLLpt84iGRh46RaMWZcs"
    
    # Method 2: Use environment variable (recommended)
    # Set environment variable: TELEGRAM_BOT_TOKEN=your_token_here
    # BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    
    # Bot Settings - OPTIMIZED FOR HIGH VOLUME PROCESSING
    MAX_ACCOUNTS_PER_REQUEST: int = 1000  # Increased to handle 1000 numbers
    PROCESSING_DELAY_SECONDS: float = 0.05  # Ultra-minimal delay for maximum speed
    
    # Batch Processing Settings - MAXIMUM SPEED OPTIMIZATION
    BATCH_SIZE: int = 50  # Increased batch size for faster processing
    MAX_CONCURRENT_WORKERS: int = 50  # Increased concurrent workers for very high speed processing
    ENABLE_BATCH_PROCESSING: bool = True  # Enable batch processing mode
    REQUEST_DELAY: float = 0.05  # Ultra-minimal delay between API requests
    BATCH_DELAY: float = 0.1  # Ultra-minimal delay between batches
    
    # Message Settings
    ENABLE_MARKDOWN: bool = True
    SEND_INDIVIDUAL_RESULTS: bool = True
    SEND_FINAL_CSV: bool = True
    
    # Admin Settings (optional)
    ADMIN_USER_IDS: list = [658557968]  # List of admin user IDs for special privileges
    
    # Authorization Settings
    ENABLE_USER_AUTHORIZATION: bool = True  # Require admin approval for new users
    AUTHORIZED_USER_IDS: list = []  # List of authorized user IDs who can use the bot
    ALLOW_PUBLIC_ACCESS: bool = False  # Allow anyone to use the bot without authorization
    
    # Concurrent Processing Settings
    MAX_CONCURRENT_USERS: int = 20  # Maximum number of users processing simultaneously (optimized for stability)
    USER_RATE_LIMIT_MINUTES: int = 2  # Minutes between requests per user (optimized for stability)
    MAX_REQUESTS_PER_USER_PER_HOUR: int = 15  # Maximum requests per user per hour (optimized)
    
    @classmethod
    def get_bot_token(cls) -> Optional[str]:
        """Get bot token with fallback to environment variable."""
        # Try environment variable first
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if token:
            return token
        
        # Fallback to class variable
        if cls.BOT_TOKEN and cls.BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
            return cls.BOT_TOKEN
        
        return None
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in cls.ADMIN_USER_IDS
    
    @classmethod
    def is_authorized(cls, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        # Admins are always authorized
        if cls.is_admin(user_id):
            return True
        
        # If public access is allowed, everyone is authorized
        if cls.ALLOW_PUBLIC_ACCESS:
            return True
        
        # If authorization is disabled, everyone is authorized
        if not cls.ENABLE_USER_AUTHORIZATION:
            return True
        
        # Check authorization from database
        try:
            from database import db_manager
            return db_manager.is_user_authorized(user_id)
        except Exception:
            # Fallback to in-memory list if database is not available
            return user_id in cls.AUTHORIZED_USER_IDS
    
    @classmethod
    def add_authorized_user(cls, user_id: int) -> bool:
        """Add user to authorized list."""
        if user_id not in cls.AUTHORIZED_USER_IDS:
            cls.AUTHORIZED_USER_IDS.append(user_id)
            return True
        return False
    
    @classmethod
    def remove_authorized_user(cls, user_id: int) -> bool:
        """Remove user from authorized list."""
        if user_id in cls.AUTHORIZED_USER_IDS:
            cls.AUTHORIZED_USER_IDS.remove(user_id)
            return True
        return False
    
    @classmethod
    def validate_config(cls) -> tuple[bool, str]:
        """Validate bot configuration."""
        token = cls.get_bot_token()
        if not token:
            return False, "Bot token not configured. Please set BOT_TOKEN or TELEGRAM_BOT_TOKEN environment variable."
        
        if token == "YOUR_BOT_TOKEN_HERE":
            return False, "Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token from @BotFather."
        
        if cls.MAX_ACCOUNTS_PER_REQUEST <= 0:
            return False, "MAX_ACCOUNTS_PER_REQUEST must be greater than 0."
        
        if cls.MAX_ACCOUNTS_PER_REQUEST > 1000:
            return False, "MAX_ACCOUNTS_PER_REQUEST should not exceed 1000 for performance reasons."
        
        # Validate batch processing settings
        if cls.BATCH_SIZE <= 0:
            return False, "BATCH_SIZE must be greater than 0."
        
        if cls.BATCH_SIZE > 100:
            return False, "BATCH_SIZE should not exceed 100 to avoid overwhelming the server."
        
        if cls.MAX_CONCURRENT_WORKERS <= 0:
            return False, "MAX_CONCURRENT_WORKERS must be greater than 0."
        
        if cls.MAX_CONCURRENT_WORKERS > 50:
            return False, "MAX_CONCURRENT_WORKERS should not exceed 50 for stability."
        
        if cls.BATCH_DELAY < 0:
            return False, "BATCH_DELAY cannot be negative."
        
        if cls.BATCH_DELAY > 60:
            return False, "BATCH_DELAY should not exceed 60 seconds for reasonable processing time."
        
        if cls.REQUEST_DELAY < 0:
            return False, "REQUEST_DELAY cannot be negative."
        
        if cls.REQUEST_DELAY > 10:
            return False, "REQUEST_DELAY should not exceed 10 seconds for reasonable processing time."
        
        # Warning for potentially problematic configurations
        warnings = []
        if cls.BATCH_SIZE > 30 and cls.MAX_CONCURRENT_WORKERS > 15:
            warnings.append("High concurrency settings may cause rate limiting.")
        
        if cls.REQUEST_DELAY < 0.05:
            warnings.append("Very low REQUEST_DELAY may trigger rate limiting.")
        
        if cls.BATCH_DELAY < 0.1 and cls.BATCH_SIZE > 30:
            warnings.append("Low BATCH_DELAY with large BATCH_SIZE may overwhelm the server.")
        
        warning_msg = " Warnings: " + "; ".join(warnings) if warnings else ""
        
        return True, f"Configuration is valid.{warning_msg}"

# Create global config instance
bot_config = BotConfig()