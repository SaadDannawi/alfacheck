#!/usr/bin/env python3
"""Telegram Bot for Alfa Account Data Extraction."""

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update, Document, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import weakref

# Import existing scraper modules
from models import AccountCredentials, AccountData, ProcessingResult
from api_client import APIClient
from scraper import process_account, write_results
from config import file_config, network_config
from utils import setup_logging
from bot_config import bot_config
from user_manager import user_manager
from language_manager import language_manager, Language
from database import db_manager

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class TelegramAlfaBot:
    """Telegram bot for processing Alfa accounts."""
    
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        # Track active processing tasks for concurrent user support
        self._active_tasks: Dict[int, asyncio.Task] = {}
        self._task_lock = asyncio.Lock()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup bot command and message handlers."""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("authorize", self.authorize_command))
        self.application.add_handler(CommandHandler("revoke", self.revoke_command))
        self.application.add_handler(CommandHandler("users", self.users_command))
        self.application.add_handler(CommandHandler("language", self.language_command))
        self.application.add_handler(CommandHandler("setpassword", self.setpassword_command))
        self.application.add_handler(CallbackQueryHandler(self.language_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors that occur during message processing."""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            try:
                # Send a simple error message without markdown to avoid parsing errors
                await update.effective_message.reply_text(
                    "❌ An error occurred while processing your request. Please try again later.",
                    parse_mode=None  # Disable markdown parsing
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
                # If we can't send a message, just log the error
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        user_id = user.id
        username = user.username or "Unknown"
        
        # Create or update user session
        session = await user_manager.get_or_create_session(
            user_id=user_id,
            username=username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        logger.info(f"User {user_id} ({username}) started the bot")
        
        is_admin = bot_config.is_admin(user_id)
        is_authorized = bot_config.is_authorized(user_id)
        
        if is_admin:
            status = language_manager.get_text("admin", user_id)
        elif is_authorized:
            status = language_manager.get_text("authorized", user_id)
        elif bot_config.ALLOW_PUBLIC_ACCESS:
            status = language_manager.get_text("access_restricted", user_id)
        else:
            status = language_manager.get_text("access_denied", user_id)
        
        if not is_authorized and not bot_config.ALLOW_PUBLIC_ACCESS:
            welcome_message = (
                f"{language_manager.get_text('welcome_title', user_id)}\n\n"
                f"{language_manager.get_text('status', user_id)} {status}\n\n"
                f"{language_manager.get_text('unauthorized_message', user_id)}\n\n"
                f"**{language_manager.get_text('your_user_id', user_id)}** `{user_id}`\n"
                f"{language_manager.get_text('provide_id_to_admin', user_id)}"
            )
        else:
            batch_status = language_manager.get_text("enabled", user_id) if bot_config.ENABLE_BATCH_PROCESSING else language_manager.get_text("disabled", user_id)
            
            welcome_message = (
                f"{language_manager.get_text('welcome_title', user_id)}\n\n"
                f"{language_manager.get_text('status', user_id)} {status}\n\n"
                f"{language_manager.get_text('send_format_instruction', user_id)}\n\n"
                "**Option 1: With password in message**\n"
                "```\n"
                "03123456\n"
                "71000000\n"
                "76123123\n"
                "pass: your_password\n"
                "```\n\n"
                "**Option 2: Using default password**\n"
                "```\n"
                "03123456\n"
                "71000000\n"
                "76123123\n"
                "```\n\n"
                f"{language_manager.get_text('instructions_title', user_id)}\n"
                f"{language_manager.get_text('list_accounts', user_id)}\n"
                "• Use `/setpassword <password>` to set a default password\n"
                "• Add `pass: your_password` as the last line to override default\n"
                "• If no default is set and no password provided, you'll be prompted\n"
                f"{language_manager.get_text('maximum_accounts', user_id, max_accounts=bot_config.MAX_ACCOUNTS_PER_REQUEST)}\n"
                f"{language_manager.get_text('process_and_send', user_id)}\n"
                f"{language_manager.get_text('receive_csv', user_id)}\n\n"
                f"{language_manager.get_text('batch_processing', user_id)} {batch_status}\n"
                f"{language_manager.get_text('batch_size', user_id)} {bot_config.BATCH_SIZE}\n"
                f"{language_manager.get_text('max_workers', user_id)} {bot_config.MAX_CONCURRENT_WORKERS}\n\n"
                f"{language_manager.get_text('commands', user_id)}\n"
                "• `/setpassword <password>` - Set default password\n"
                f"{language_manager.get_text('language_command', user_id)}"
            )
            
            if is_admin:
                welcome_message += ("\n\n"
                    f"{language_manager.get_text('admin_commands', user_id)}\n"
                    f"{language_manager.get_text('authorize_command', user_id)}\n"
                    f"{language_manager.get_text('revoke_command', user_id)}\n"
                    f"{language_manager.get_text('users_command', user_id)}\n"
                    f"{language_manager.get_text('stats_command', user_id)}"
                )
        
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
    
    async def authorize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /authorize command (admin only)."""
        user_id = update.effective_user.id
        
        if not bot_config.is_admin(user_id):
            await update.message.reply_text(
                language_manager.get_text("admin_only", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                f"{language_manager.get_text('usage', user_id)} `/authorize <user_id>`\n\n"
                f"{language_manager.get_text('example', user_id)} `/authorize 123456789`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            # Authorize user in database
            success = db_manager.authorize_user(target_user_id)
            
            if success:
                await update.message.reply_text(
                    f"{language_manager.get_text('user_authorized', user_id)}\n\n"
                    f"{language_manager.get_text('user_granted_access', user_id, target_id=str(target_user_id))}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ **Error**\n\nUser {target_user_id} not found in database. They need to start the bot first.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except ValueError:
            await update.message.reply_text(
                language_manager.get_text("invalid_user_id", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /revoke command (admin only)."""
        user_id = update.effective_user.id
        
        if not bot_config.is_admin(user_id):
            await update.message.reply_text(
                language_manager.get_text("admin_only", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                f"{language_manager.get_text('usage', user_id)} `/revoke <user_id>`\n\n"
                f"{language_manager.get_text('example', user_id)} `/revoke 123456789`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            if target_user_id in bot_config.ADMIN_USER_IDS:
                await update.message.reply_text(
                    language_manager.get_text("cannot_revoke_admin", user_id),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Revoke user authorization in database
            success = db_manager.revoke_user_authorization(target_user_id)
            
            if success:
                await update.message.reply_text(
                    f"{language_manager.get_text('user_access_revoked', user_id)}\n\n"
                    f"{language_manager.get_text('user_no_longer_access', user_id, target_id=str(target_user_id))}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ **Error**\n\nUser {target_user_id} not found in database.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except ValueError:
            await update.message.reply_text(
                language_manager.get_text("invalid_user_id", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /users command (admin only)."""
        user_id = update.effective_user.id
        
        if not bot_config.is_admin(user_id):
            await update.message.reply_text(
                "🔒 **Access Denied**\n\n"
                "This command is only available to administrators.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        admin_list = "\n".join([f"• `{admin_id}`" for admin_id in bot_config.ADMIN_USER_IDS])
        
        # Get authorized users from database
        try:
            authorized_user_ids = db_manager.get_authorized_users()
            authorized_list = "\n".join([f"• `{user_id}`" for user_id in authorized_user_ids])
            
            if not authorized_list:
                authorized_list = "*No authorized users*"
        except Exception:
            authorized_list = "*Error retrieving authorized users*"
            authorized_user_ids = []
        
        message = (
            "👥 **User Management**\n\n"
            f"**Administrators ({len(bot_config.ADMIN_USER_IDS)}):**\n"
            f"{admin_list}\n\n"
            f"**Authorized Users ({len(authorized_user_ids)}):**\n"
            f"{authorized_list}\n\n"
            f"**Public Access:** {'✅ Enabled' if bot_config.ALLOW_PUBLIC_ACCESS else '🔒 Disabled'}"
        )
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    

    

    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /language command."""
        user_id = update.effective_user.id
        
        if not bot_config.is_authorized(user_id):
            await update.message.reply_text(
                language_manager.get_text("access_denied_message", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Create language selection keyboard
        keyboard = []
        current_lang = user_manager.get_user_language(user_id)
        
        for lang in Language:
            flag = "🇺🇸" if lang == Language.ENGLISH else "🇸🇦"
            lang_name = "English" if lang == Language.ENGLISH else "العربية"
            current = " ✓" if current_lang == lang else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{flag} {lang_name}{current}",
                    callback_data=f"lang_{lang.value}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            language_manager.get_text("select_language", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle language selection callback."""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not bot_config.is_authorized(user_id):
            await query.answer(language_manager.get_text("access_denied_short", user_id))
            return
        
        if query.data.startswith("lang_"):
            lang_code = query.data.split("_")[1]
            try:
                language = Language(lang_code)
                # Update both language_manager and user_manager
                language_manager.set_user_language(user_id, language)
                user_manager.set_user_language(user_id, language)
                
                await query.answer(language_manager.get_text("language_changed", user_id))
                
                # Update the message to show new selection
                keyboard = []
                current_lang = user_manager.get_user_language(user_id)
                
                for lang in Language:
                    flag = "🇺🇸" if lang == Language.ENGLISH else "🇸🇦"
                    lang_name = "English" if lang == Language.ENGLISH else "العربية"
                    current = " ✓" if current_lang == lang else ""
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{flag} {lang_name}{current}",
                            callback_data=f"lang_{lang.value}"
                        )
                    ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    language_manager.get_text("select_language", user_id),
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
            except ValueError:
                await query.answer(language_manager.get_text("invalid_language", user_id))
    
    async def setpassword_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setpassword command."""
        user_id = update.effective_user.id
        
        if not bot_config.is_authorized(user_id):
            await update.message.reply_text(
                language_manager.get_text("access_denied_message", user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                f"{language_manager.get_text('usage', user_id)} `/setpassword <password>`\n\n"
                f"{language_manager.get_text('example', user_id)} `/setpassword mypassword123`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        password = ' '.join(context.args)
        
        if len(password) < 1:
            await update.message.reply_text(
                "❌ **Error**\n\nPassword cannot be empty.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Save the default password for the user
        user_manager.set_user_default_password(user_id, password)
        
        await update.message.reply_text(
            "✅ **Default Password Set**\n\n"
            "Your default password has been saved successfully. "
            "It will be automatically applied to subsequent account processing requests "
            "when no password is specified in the message.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def parse_message(self, message_text: str, user_id: int) -> tuple[List[str], str]:
        """Parse message to extract account numbers and password."""
        import re
        
        lines = [line.strip() for line in message_text.strip().split('\n') if line.strip()]
        
        if len(lines) < 1:
            raise ValueError("Please provide at least one account number.")
        
        # Check if last line contains password pattern (pass: xxxx or password: xxxx)
        password_pattern = re.compile(r'^(pass|password)\s*:\s*(.+)$', re.IGNORECASE)
        password = None
        account_numbers = lines
        
        # Check if last line matches password pattern
        if lines:
            match = password_pattern.match(lines[-1])
            if match:
                password = match.group(2).strip()
                account_numbers = lines[:-1]  # Remove password line from account numbers
        
        # If no password found in message, try to get default password
        if password is None:
            default_password = user_manager.get_user_default_password(user_id)
            if default_password:
                password = default_password
            else:
                raise ValueError(
                    "No password provided. Please either:\n"
                    "• Add 'pass: your_password' as the last line of your message, or\n"
                    "• Set a default password using /setpassword command"
                )
        
        # Validate that we have account numbers
        if not account_numbers:
            raise ValueError("Please provide at least one account number.")
        
        # Validate account numbers (should be numeric)
        for num in account_numbers:
            if not num.isdigit():
                raise ValueError(f"Invalid account number: {num}. Account numbers should contain only digits.")
        
        if len(account_numbers) > bot_config.MAX_ACCOUNTS_PER_REQUEST:
            raise ValueError(f"Too many accounts. Maximum allowed: {bot_config.MAX_ACCOUNTS_PER_REQUEST}")
        
        return account_numbers, password
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages with account data."""
        try:
            user_id = update.effective_user.id
            
            # Check authorization
            if not bot_config.is_authorized(user_id):
                await update.message.reply_text(
                    language_manager.get_text("access_denied_message", user_id),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Check if user already has an active processing task (quick check without blocking)
            async with self._task_lock:
                user_has_active_task = user_id in self._active_tasks and not self._active_tasks[user_id].done()
            
            if user_has_active_task:
                await update.message.reply_text(
                    language_manager.get_text("already_processing", user_id) or 
                    "⚠️ **Already Processing**\n\nYou already have a request being processed. Please wait for it to complete.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Check if user can process request (concurrent processing enabled)
            can_process, error_message = await user_manager.can_process_request(
                user_id, 
                bot_config.MAX_CONCURRENT_USERS,
                bot_config.USER_RATE_LIMIT_MINUTES,
                bot_config.MAX_REQUESTS_PER_USER_PER_HOUR
            )
            if not can_process:
                await update.message.reply_text(
                    error_message,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Parse the message
            account_numbers, password = self.parse_message(update.message.text, user_id)
            
            # Calculate realistic processing time based on batch processing configuration
            base_time_per_account = 12  # Average time per account in seconds
            
            if bot_config.ENABLE_BATCH_PROCESSING and len(account_numbers) > 1:
                # Batch processing mode
                batch_size = min(bot_config.BATCH_SIZE, len(account_numbers))
                num_batches = (len(account_numbers) + batch_size - 1) // batch_size
                
                # Time per batch (accounts processed concurrently)
                time_per_batch = base_time_per_account  # Since accounts in batch run concurrently
                
                # Total time = (batches * time_per_batch) + (delays between batches)
                batch_delays = (num_batches - 1) * bot_config.BATCH_DELAY if num_batches > 1 else 0
                estimated_time_seconds = (num_batches * time_per_batch) + batch_delays
                
                # Add buffer for startup
                estimated_time_seconds += 5
            else:
                # Sequential processing mode
                estimated_time_seconds = len(account_numbers) * base_time_per_account
                # Add processing delays
                estimated_time_seconds += (len(account_numbers) - 1) * bot_config.PROCESSING_DELAY_SECONDS
                # Add buffer
                estimated_time_seconds += 5
            
            estimated_minutes = estimated_time_seconds / 60
            
            if estimated_minutes < 1:
                time_estimate = f"{int(estimated_time_seconds)} seconds"
            elif estimated_minutes < 60:
                time_estimate = f"{estimated_minutes:.1f} minutes"
            else:
                hours = int(estimated_minutes // 60)
                minutes = int(estimated_minutes % 60)
                time_estimate = f"{hours}h {minutes}m"
            
            # Determine processing mode message
            if bot_config.ENABLE_BATCH_PROCESSING and len(account_numbers) > 1:
                batch_size = min(bot_config.BATCH_SIZE, len(account_numbers))
                num_batches = (len(account_numbers) + batch_size - 1) // batch_size
                mode_info = f"🚀 **Batch Mode:** {num_batches} batches of {batch_size} accounts"
            else:
                mode_info = "⚡ **Sequential Mode:** Processing one by one"
            
            # Send confirmation
            await update.message.reply_text(
                f"📋 **Processing {len(account_numbers)} accounts...**\n\n"
                f"{mode_info}\n"
                f"⏳ **Estimated time:** ~{time_estimate}\n"
                f"📤 I'll send results for each account as they complete.\n\n"
                f"✅ **Concurrent Processing:** Multiple users can now process simultaneously!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Create processing task (non-blocking)
            task = asyncio.create_task(
                self._process_user_accounts(update, account_numbers, password, user_id)
            )
            
            # Quickly add task to active tasks and clean up completed ones
            async with self._task_lock:
                self._active_tasks[user_id] = task
                
                # Clean up completed tasks
                completed_tasks = [uid for uid, t in self._active_tasks.items() if t.done()]
                for uid in completed_tasks:
                    del self._active_tasks[uid]
            
        except ValueError as e:
            # Escape markdown characters in error message to prevent parsing errors
            error_msg = str(e).replace('•', '\\•').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
            await update.message.reply_text(
                f"❌ **Error:** {error_msg}\n\n"
                f"Please check the format and try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                f"❌ **Unexpected error occurred.** Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def _process_user_accounts(self, update: Update, account_numbers: List[str], password: str, user_id: int):
        """Process accounts for a specific user asynchronously."""
        try:
            # Start processing for this user
            await user_manager.start_processing(user_id)
            
            # Process accounts
            await self.process_accounts(update, account_numbers, password)
            
        except Exception as e:
            logger.error(f"Error processing accounts for user {user_id}: {e}")
            await update.message.reply_text(
                f"❌ **Processing failed:** {str(e)}\n\nPlease try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
        finally:
            # Always stop processing when done
            await user_manager.finish_processing(user_id)
            
            # Remove task from active tasks
            async with self._task_lock:
                if user_id in self._active_tasks:
                    del self._active_tasks[user_id]
    
    async def process_accounts(self, update: Update, account_numbers: List[str], password: str):
        """Process all accounts using batch concurrent processing."""
        import uuid
        import time
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Generate unique transaction ID
        transaction_id = str(uuid.uuid4())
        
        # Create transaction in database
        db_manager.create_transaction(user_id, transaction_id, len(account_numbers))
        
        # Start transaction timing
        start_time = time.time()
        
        # Create account credentials
        accounts = [AccountCredentials(username=num, password=password) for num in account_numbers]
        
        # Start processing request in database
        processing_mode = 'batch' if bot_config.ENABLE_BATCH_PROCESSING and len(accounts) > 1 else 'sequential'
        request_id = db_manager.start_processing_request(
            user_id=user_id,
            total_accounts=len(accounts),
            processing_mode=processing_mode
        )
        
        # Start transaction
        db_manager.start_transaction(transaction_id)
        
        # Initialize results
        results = ProcessingResult(total_accounts=len(accounts))
        processed_count = 0
        
        try:
            if bot_config.ENABLE_BATCH_PROCESSING:
                # Process accounts in batches with concurrent processing (works for single accounts too)
                await self.process_accounts_batch(update, accounts, results, processed_count, request_id, transaction_id)
            else:
                # Process accounts sequentially (fallback method)
                await self.process_accounts_sequential(update, accounts, results, processed_count, request_id, transaction_id)
            
            # Complete processing and send final file
            results.complete()
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Complete transaction
            db_manager.complete_transaction(
                transaction_id=transaction_id,
                successful_numbers=results.successful,
                failed_numbers=results.failed,
                processing_time=processing_time
            )
            
            # Complete processing request in database
            db_manager.complete_processing_request(
                request_id=request_id,
                successful=results.successful,
                partial=results.partial,
                failed=results.failed
            )
            
            # Update account count in user session
            await user_manager.add_processed_accounts(user_id, len(accounts))
            
            # Send final results with dashboard link
            await self.send_final_results(update, results, transaction_id)
            
        except Exception as e:
            # Calculate processing time even on error
            processing_time = time.time() - start_time
            
            # Complete transaction with error
            db_manager.complete_transaction(
                transaction_id=transaction_id,
                successful_numbers=results.successful,
                failed_numbers=results.failed,
                processing_time=processing_time,
                error_message=str(e)
            )
            
            # Complete processing request with error
            db_manager.complete_processing_request(
                request_id=request_id,
                successful=results.successful,
                partial=results.partial,
                failed=results.failed,
                error_message=str(e)
            )
            raise
    
    async def process_accounts_batch(self, update: Update, accounts: List[AccountCredentials], 
                                   results: ProcessingResult, processed_count: int, request_id: int, transaction_id: str):
        """Process accounts in concurrent batches."""
        total_accounts = len(accounts)
        batch_size = min(bot_config.BATCH_SIZE, total_accounts)
        
        # Split accounts into batches
        batches = [accounts[i:i + batch_size] for i in range(0, total_accounts, batch_size)]
        
        await update.message.reply_text(
            f"🚀 **Batch Processing Mode Enabled**\n\n"
            f"📦 **Processing {len(batches)} batches of {batch_size} accounts each**\n"
            f"⚡ **Max concurrent workers:** {bot_config.MAX_CONCURRENT_WORKERS}\n"
            f"⏱️ **Batch delay:** {bot_config.BATCH_DELAY}s",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Collect all results for batch database saving
        all_batch_results = []
        
        for batch_num, batch in enumerate(batches, 1):
            await update.message.reply_text(
                f"📦 **Processing Batch {batch_num}/{len(batches)}** ({len(batch)} accounts)\n"
                f"⚡ Starting concurrent processing...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Process batch concurrently
            batch_results = await self.process_batch_concurrent(batch)
            
            # Add results and send individual notifications
            for result in batch_results:
                results.add_result(result)
                processed_count += 1
                all_batch_results.append(result)
                
                await self.send_account_result(update, result, processed_count, total_accounts)
            
            # Delay between batches (except for the last batch)
            if batch_num < len(batches):
                await update.message.reply_text(
                    f"⏸️ **Batch {batch_num} completed!** Waiting {bot_config.BATCH_DELAY}s before next batch...",
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(bot_config.BATCH_DELAY)
        
        # Save all results to database in batches for better performance
        if all_batch_results:
            await update.message.reply_text(
                "💾 **Saving results to database...**",
                parse_mode=ParseMode.MARKDOWN
            )
            db_manager.save_account_results_batch(request_id, all_batch_results)
            db_manager.save_transaction_results_batch(transaction_id, all_batch_results, request_id)
    
    async def process_batch_concurrent(self, batch: List[AccountCredentials]) -> List[AccountData]:
        """Process a batch of accounts concurrently."""
        # Create async tasks for all accounts in the batch
        tasks = [process_account(account) for account in batch]
        
        # Wait for all tasks to complete
        batch_results = []
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing account {batch[i].username}: {result}")
                    error_result = AccountData(
                        username=batch[i].username,
                        status="Error",
                        error_details=f"Processing failed: {str(result)}"
                    )
                    batch_results.append(error_result)
                else:
                    batch_results.append(result)
                    
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Create error results for all accounts in the batch
            for account in batch:
                error_result = AccountData(
                    username=account.username,
                    status="Error",
                    error_details=f"Batch processing failed: {str(e)}"
                )
                batch_results.append(error_result)
        
        return batch_results
    
    async def process_accounts_sequential(self, update: Update, accounts: List[AccountCredentials], 
                                        results: ProcessingResult, processed_count: int, request_id: int, transaction_id: str):
        """Process accounts sequentially (fallback method)."""
        total_accounts = len(accounts)
        all_results = []
        
        for account in accounts:
            try:
                # Process single account
                result = await process_account(account)
                results.add_result(result)
                processed_count += 1
                all_results.append(result)
                
                # Send individual result
                await self.send_account_result(update, result, processed_count, total_accounts)
                
                # Small delay between accounts
                await asyncio.sleep(bot_config.PROCESSING_DELAY_SECONDS)
                
            except Exception as e:
                logger.error(f"Error processing account {account.username}: {e}")
                # Create error result
                error_result = AccountData(
                    username=account.username,
                    status="Error",
                    error_details=f"Processing failed: {str(e)}" if str(e) else "Unknown processing error occurred"
                )
                results.add_result(error_result)
                processed_count += 1
                all_results.append(error_result)
                
                await self.send_account_result(update, error_result, processed_count, total_accounts)
        
        # Save all results to database in batches for better performance
        if all_results:
            await update.message.reply_text(
                "💾 **Saving results to database...**",
                parse_mode=ParseMode.MARKDOWN
            )
            db_manager.save_account_results_batch(request_id, all_results)
            db_manager.save_transaction_results_batch(transaction_id, all_results, request_id)
    
    async def send_account_result(self, update: Update, result: AccountData, current: int, total: int):
        """Send individual account result."""
        # Format result message
        status_emoji = "[✅]" if result.status == "Success" else "[⚠️]" if result.status == "Partial Success" else "[❌]"
        
        message = (
            f"{status_emoji} **Account {current}/{total}: {result.username}**\n"
            f"**Status:** {result.status}\n"
        )
        
        if result.status == "Success" or result.status == "Partial Success":
            message += (
                f"**Balance:** ${result.current_balance}\n"
                f"**Validity:** {result.validity_days_remaining} days\n"
                f"**Activation:** {result.activation_date}\n"
                f"**Last Recharge:** ${result.last_recharge_amount} on {result.last_recharge_date}\n"
                f"**Services:** {result.service_details}\n"
                f"**Subscription Date:** {result.subscription_date or 'N/A'}\n"
                f"**Service Validity Date:** {result.validity_date or 'N/A'}\n"
                f"**Secondary Numbers:** {result.secondary_numbers}\n"
                f"**Main Consumption:** {result.main_consumption}\n"
                f"**Mobile Internet:** {result.mobile_internet_consumption}\n"
                f"**Secondary Usage:** {result.secondary_consumption}\n"
            )
        
        if result.error_details:
            message += f"**Errors:** {result.error_details}\n"
        
        message += "\n" + "─" * 15
        
        try:
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            # Fallback without markdown if formatting fails
            await update.message.reply_text(message.replace("**", "").replace("```", ""))
    
    async def send_final_results(self, update: Update, results: ProcessingResult, transaction_id: str = None):
        """Send final results file and summary with customer page link."""
        try:
            # Create temporary CSV file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as temp_file:
                temp_path = temp_file.name
                
                # Write results to temporary file
                import csv
                from config import REQUIRED_FIELDS
                
                writer = csv.DictWriter(temp_file, fieldnames=REQUIRED_FIELDS)
                writer.writeheader()
                
                # Sort results by username for consistent output
                sorted_results = sorted(results.results, key=lambda x: x.username)
                writer.writerows(result.to_dict() for result in sorted_results)
            
            # Get or create customer page for this user
            user_id = update.effective_user.id
            customer_page_id = db_manager.get_or_create_customer_page(user_id)
            
            # Send summary message with customer dashboard link
            summary_message = (
                f"**Total Accounts:** {results.total_accounts}\n"
                f"**Successful:** {results.successful}\n"
                f"**Partial Success:** {results.partial}\n"
                f"**Failed:** {results.failed}\n"
                f"**Success Rate:** {results.success_rate:.1f}%\n"
                f"**Processing Time:** {results.processing_time:.1f} seconds\n\n"
            )
            
            # Add customer dashboard link
            if customer_page_id:
                customer_dashboard_url = f"http://192.168.10.115:5000/customer/{customer_page_id}"
                summary_message += (
                    f"\n\n[DASHBOARD]\n"
                    f"[View All Your Results]({customer_dashboard_url})\n\n"
                    
                    
                )
            
            # Add transaction reference if provided
            if transaction_id:
                transaction_dashboard_url = f"http://192.168.10.115:5000/transaction/{transaction_id}"
                summary_message += f"\n\n[TRANSACTION]\n[View Transaction Details]({transaction_dashboard_url})"
            
            await update.message.reply_text(summary_message, parse_mode=ParseMode.MARKDOWN)
            
            # Send CSV file
            with open(temp_path, 'rb') as file:
                await update.message.reply_document(
                    document=file,
                    filename=f"alfa_results_{update.effective_user.id}_{int(results.start_time.timestamp())}.csv",
                    caption="[CSV] Complete results in CSV format"
                )
            
            # Clean up temporary file
            os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Error sending final results: {e}")
            await update.message.reply_text(
                f"[ERROR] **Error sending results file.** Processing completed but file delivery failed.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def run(self):
        """Start the bot."""
        logger.info("Starting Telegram Alfa Bot...")
        # Use more aggressive polling settings to resolve conflicts
        self.application.run_polling(
            drop_pending_updates=True,
            close_loop=False,
            stop_signals=None
        )

def main():
    """Main function to run the bot."""
    # Validate configuration
    is_valid, message = bot_config.validate_config()
    if not is_valid:
        print(f"[ERROR] Configuration Error: {message}")
        print("\n[SETUP] Setup Instructions:")
        print("1. Get your bot token from @BotFather on Telegram")
        print("2. Edit bot_config.py and set BOT_TOKEN = 'your_token_here'")
        print("3. Or set environment variable: TELEGRAM_BOT_TOKEN=your_token_here")
        return
    
    # Initialize database
    try:
        db_manager.init_db()
        print("[SUCCESS] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        return
    
    token = bot_config.get_bot_token()
    print(f"[SUCCESS] Configuration valid. Starting bot...")
    print(f"[INFO] Max accounts per request: {bot_config.MAX_ACCOUNTS_PER_REQUEST}")
    
    if bot_config.ENABLE_BATCH_PROCESSING:
        print(f"[INFO] Batch processing: ENABLED")
        print(f"[INFO] Batch size: {bot_config.BATCH_SIZE} accounts")
        print(f"[INFO] Max concurrent workers: {bot_config.MAX_CONCURRENT_WORKERS}")
        print(f"[INFO] Batch delay: {bot_config.BATCH_DELAY}s")
        print(f"[INFO] Request delay: {bot_config.REQUEST_DELAY}s")
    else:
        print(f"[WARNING] Batch processing: DISABLED (Sequential mode)")
        print(f"[INFO] Processing delay: {bot_config.PROCESSING_DELAY_SECONDS}s")
    
    print("[INFO] Bot is running. Press Ctrl+C to stop.")
    
    bot = TelegramAlfaBot(token)
    bot.run()

if __name__ == "__main__":
    main()