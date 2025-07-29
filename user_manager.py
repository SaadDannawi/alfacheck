"""User management system for Telegram Bot."""

import time
import asyncio
import threading
from typing import Dict, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from language_manager import Language
from database import db_manager, User, UserSession as DBUserSession

logger = logging.getLogger(__name__)

@dataclass
class UserSession:
    """User session information (legacy compatibility)."""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language: Language = Language.ENGLISH
    is_processing: bool = False
    last_request_time: Optional[datetime] = None
    request_count_hour: int = 0
    hour_reset_time: datetime = field(default_factory=datetime.now)
    total_requests: int = 0
    total_accounts: int = 0
    
    @classmethod
    def from_db_user(cls, db_user: User, db_session: DBUserSession = None):
        """Create UserSession from database User and UserSession."""
        language = Language.ENGLISH
        try:
            language = Language(db_user.language)
        except ValueError:
            pass
        
        return cls(
            user_id=db_user.user_id,
            username=db_user.username,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            language=language,
            is_processing=db_session.is_processing if db_session else False,
            last_request_time=db_session.last_request_time if db_session else None,
            request_count_hour=db_session.request_count_hour if db_session else 0,
            hour_reset_time=db_session.hour_reset_time if db_session else datetime.now(),
            total_requests=db_user.total_requests,
            total_accounts=db_user.total_accounts_processed
        )
    
class UserManager:
    """Manages user sessions, authorization, and rate limiting."""
    
    def __init__(self):
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        # Cache for active processing users to avoid frequent DB queries
        self._processing_users_cache: Set[int] = set()
        self._cache_last_update = datetime.now()
        
    async def get_or_create_session(self, user_id: int, username: str = None, 
                             first_name: str = None, last_name: str = None) -> UserSession:
        """Get existing session or create new one."""
        async with self._async_lock:
            def _get_or_create_session_db():
                # Get or create user in database
                db_user = db_manager.get_or_create_user(user_id, username, first_name, last_name)
                
                # Get or create active session
                db_session = db_manager.get_active_session(user_id)
                if not db_session:
                    db_session = db_manager.create_session(user_id)
                
                # Update activity
                db_manager.update_session_activity(user_id)
                
                # Access user data within session context to avoid DetachedInstanceError
                with db_manager.get_session() as session:
                    fresh_user = session.query(User).filter(User.user_id == user_id).first()
                    user_language = fresh_user.language if fresh_user else 'en'
                    user_username = fresh_user.username if fresh_user else username
                    user_first_name = fresh_user.first_name if fresh_user else first_name
                    user_last_name = fresh_user.last_name if fresh_user else last_name
                    user_total_requests = fresh_user.total_requests if fresh_user else 0
                    user_total_accounts = fresh_user.total_accounts_processed if fresh_user else 0
                
                # Get session data within database context to avoid DetachedInstanceError
                session_is_processing = False
                session_last_request_time = None
                session_request_count_hour = 0
                session_hour_reset_time = datetime.now()
                
                if db_session:
                    with db_manager.get_session() as session:
                        fresh_session = session.query(DBUserSession).filter(
                            DBUserSession.user_id == user_id,
                            DBUserSession.is_active == True
                        ).first()
                        if fresh_session:
                            session_is_processing = fresh_session.is_processing
                            session_last_request_time = fresh_session.last_request_time
                            session_request_count_hour = fresh_session.request_count_hour
                            session_hour_reset_time = fresh_session.hour_reset_time
                
                return {
                    'user_language': user_language,
                    'user_username': user_username,
                    'user_first_name': user_first_name,
                    'user_last_name': user_last_name,
                    'user_total_requests': user_total_requests,
                    'user_total_accounts': user_total_accounts,
                    'session_is_processing': session_is_processing,
                    'session_last_request_time': session_last_request_time,
                    'session_request_count_hour': session_request_count_hour,
                    'session_hour_reset_time': session_hour_reset_time
                }
            
            # Run database operations in thread pool
            data = await asyncio.to_thread(_get_or_create_session_db)
            
            # Create UserSession with fresh data
            try:
                language = Language(data['user_language'])
            except ValueError:
                language = Language.ENGLISH
            
            return UserSession(
                user_id=user_id,
                username=data['user_username'],
                first_name=data['user_first_name'],
                last_name=data['user_last_name'],
                language=language,
                is_processing=data['session_is_processing'],
                last_request_time=data['session_last_request_time'],
                request_count_hour=data['session_request_count_hour'],
                hour_reset_time=data['session_hour_reset_time'],
                total_requests=data['user_total_requests'],
                total_accounts=data['user_total_accounts']
            )
    
    async def can_process_request(self, user_id: int, max_concurrent: int, 
                           rate_limit_minutes: int, max_requests_per_hour: int) -> tuple[bool, str]:
        """Check if user can process a request based on limits."""
        async with self._async_lock:
            # Run database operations in thread pool to avoid blocking
            def _check_user_limits():
                with db_manager.get_session() as session:
                    db_session = session.query(DBUserSession).filter(
                        DBUserSession.user_id == user_id,
                        DBUserSession.is_active == True
                    ).first()
                    
                    if not db_session:
                        return False, "Session not found"
                    
                    # Check if user is already processing
                    if db_session.is_processing:
                        return False, "You already have a request being processed. Please wait for it to complete."
                    
                    # Check rate limiting (time between requests)
                    if db_session.last_request_time:
                        time_since_last = datetime.now() - db_session.last_request_time
                        if time_since_last.total_seconds() < (rate_limit_minutes * 60):
                            remaining_time = (rate_limit_minutes * 60) - time_since_last.total_seconds()
                            return False, f"Please wait {remaining_time:.0f} seconds before making another request."
                    
                    # Check hourly request limit
                    now = datetime.now()
                    if now - db_session.hour_reset_time >= timedelta(hours=1):
                        # Reset hourly counter
                        db_session.request_count_hour = 0
                        db_session.hour_reset_time = now
                        session.commit()
                    
                    if db_session.request_count_hour >= max_requests_per_hour:
                        reset_time = db_session.hour_reset_time + timedelta(hours=1)
                        remaining_time = (reset_time - now).total_seconds()
                        return False, f"Hourly request limit ({max_requests_per_hour}) reached. Try again in {remaining_time/60:.0f} minutes."
                    
                    return True, "OK"
            
            # Update processing users cache if needed
            await asyncio.to_thread(self._update_processing_cache)
            
            # Run database check in thread pool
            return await asyncio.to_thread(_check_user_limits)
    
    def _update_processing_cache(self):
        """Update the processing users cache from database."""
        # Update cache every 30 seconds to avoid frequent DB queries
        if (datetime.now() - self._cache_last_update).total_seconds() > 30:
            with db_manager.get_session() as session:
                processing_sessions = session.query(DBUserSession).filter(
                    DBUserSession.is_active == True,
                    DBUserSession.is_processing == True
                ).all()
                self._processing_users_cache = {s.user_id for s in processing_sessions}
                self._cache_last_update = datetime.now()
    
    async def start_processing(self, user_id: int) -> bool:
        """Mark user as processing and update counters."""
        async with self._async_lock:
            def _start_processing_db():
                with db_manager.get_session() as session:
                    # Update user session
                    db_session = session.query(DBUserSession).filter(
                        DBUserSession.user_id == user_id,
                        DBUserSession.is_active == True
                    ).first()
                    
                    if not db_session:
                        return False
                    
                    db_session.is_processing = True
                    db_session.last_request_time = datetime.now()
                    db_session.request_count_hour += 1
                    db_session.last_activity = datetime.now()
                    
                    session.commit()
                    return True
            
            # Run database operation in thread pool
            result = await asyncio.to_thread(_start_processing_db)
            
            if result:
                # Update cache
                self._processing_users_cache.add(user_id)
                logger.info(f"User {user_id} started processing (total processing: {len(self._processing_users_cache)})")
            
            return result
    
    async def finish_processing(self, user_id: int) -> bool:
        """Mark user as finished processing."""
        async with self._async_lock:
            def _finish_processing_db():
                with db_manager.get_session() as session:
                    # Update user session
                    db_session = session.query(DBUserSession).filter(
                        DBUserSession.user_id == user_id,
                        DBUserSession.is_active == True
                    ).first()
                    
                    if db_session:
                        db_session.is_processing = False
                        db_session.last_activity = datetime.now()
                        session.commit()
                        return True
                    return False
            
            # Run database operation in thread pool
            db_result = await asyncio.to_thread(_finish_processing_db)
            
            # Update cache
            if user_id in self._processing_users_cache:
                self._processing_users_cache.remove(user_id)
                logger.info(f"User {user_id} finished processing (total processing: {len(self._processing_users_cache)})")
                return True
            return False
    
    async def add_processed_accounts(self, user_id: int, account_count: int) -> bool:
        """Add processed account count to user session."""
        async with self._async_lock:
            def _add_processed_accounts_db():
                with db_manager.get_session() as session:
                    # Update user total accounts
                    db_user = session.query(User).filter(User.user_id == user_id).first()
                    if db_user:
                        db_user.total_accounts_processed += account_count
                        session.commit()
                        total_accounts = db_user.total_accounts_processed
                        logger.info(f"User {user_id} processed {account_count} accounts (total: {total_accounts})")
                        return True
                return False
            
            # Run database operation in thread pool
            return await asyncio.to_thread(_add_processed_accounts_db)
    
    def set_user_language(self, user_id: int, language: Language) -> bool:
        """Set user's preferred language."""
        with self._sync_lock:
            with db_manager.get_session() as session:
                # Update user language
                db_user = session.query(User).filter(User.user_id == user_id).first()
                if db_user:
                    db_user.language = language.value
                    session.commit()
                    logger.info(f"User {user_id} language set to {language.value}")
                    return True
            return False
    
    def get_user_language(self, user_id: int) -> Language:
        """Get user's preferred language."""
        with self._sync_lock:
            with db_manager.get_session() as session:
                db_user = session.query(User).filter(User.user_id == user_id).first()
                if db_user:
                    try:
                        return Language(db_user.language)
                    except ValueError:
                        return Language.ENGLISH
                return Language.ENGLISH
    
    def set_user_default_password(self, user_id: int, password: str) -> bool:
        """Set default password for a user."""
        with self._sync_lock:
            return db_manager.set_user_default_password(user_id, password)
    
    def get_user_default_password(self, user_id: int) -> Optional[str]:
        """Get default password for a user."""
        with self._sync_lock:
            return db_manager.get_user_default_password(user_id)
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Get user statistics."""
        with self._sync_lock:
            # Use database manager's get_user_stats method
            return db_manager.get_user_stats(user_id)
    
    def get_system_stats(self) -> Dict:
        """Get system-wide statistics."""
        with self._sync_lock:
            # Update processing cache
            self._update_processing_cache()
            
            # Get system stats from database
            db_stats = db_manager.get_system_stats()
            
            # Add current processing info
            db_stats['processing_users'] = len(self._processing_users_cache)
            db_stats['active_sessions'] = list(self._processing_users_cache)
            
            return db_stats
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Remove old inactive sessions."""
        with self._sync_lock:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            with db_manager.get_session() as session:
                # Find old inactive sessions
                old_sessions = session.query(DBUserSession).filter(
                    DBUserSession.is_active == True,
                    DBUserSession.is_processing == False,
                    DBUserSession.last_activity < cutoff_time
                ).all()
                
                # Mark them as inactive
                count = 0
                for old_session in old_sessions:
                    old_session.is_active = False
                    old_session.session_end = datetime.now()
                    count += 1
                    logger.info(f"Cleaned up old session for user {old_session.user_id}")
                
                session.commit()
                
                # Update cache
                self._update_processing_cache()
                
                return count

# Global user manager instance
user_manager = UserManager()