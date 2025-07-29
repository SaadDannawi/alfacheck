"""Session manager for maintaining login sessions across multiple verifications."""

import logging
import time
from typing import Dict, Optional, Tuple
from threading import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta

from api_client import APIClient

@dataclass
class SessionInfo:
    """Information about a login session."""
    client: APIClient
    username: str
    password: str
    login_time: datetime
    last_used: datetime
    is_valid: bool = True
    
    def is_expired(self, max_age_minutes: int = 30) -> bool:
        """Check if session is expired based on age."""
        return datetime.now() - self.login_time > timedelta(minutes=max_age_minutes)
    
    def is_idle(self, max_idle_minutes: int = 10) -> bool:
        """Check if session has been idle too long."""
        return datetime.now() - self.last_used > timedelta(minutes=max_idle_minutes)

class SessionManager:
    """Manages login sessions for account numbers to avoid repeated logins."""
    
    def __init__(self, max_age_minutes: int = 30, max_idle_minutes: int = 10):
        """Initialize session manager.
        
        Args:
            max_age_minutes: Maximum age of a session before it's considered expired
            max_idle_minutes: Maximum idle time before session is cleaned up
        """
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = Lock()
        self._max_age_minutes = max_age_minutes
        self._max_idle_minutes = max_idle_minutes
        self._logger = logging.getLogger(__name__)
    
    def get_or_create_session(self, username: str, password: str) -> Tuple[APIClient, bool]:
        """Get existing session or create new one.
        
        Args:
            username: Account username
            password: Account password
            
        Returns:
            Tuple of (APIClient, is_new_session)
        """
        with self._lock:
            # Clean up expired/idle sessions first
            self._cleanup_sessions()
            
            # Check if we have a valid session for this username
            if username in self._sessions:
                session_info = self._sessions[username]
                
                # Verify session is still valid
                if (not session_info.is_expired(self._max_age_minutes) and 
                    session_info.is_valid and 
                    session_info.password == password):
                    
                    # Update last used time
                    session_info.last_used = datetime.now()
                    self._logger.info(f"[{username}] Reusing existing session (age: {datetime.now() - session_info.login_time})")
                    return session_info.client, False
                else:
                    # Session expired or invalid, remove it
                    self._logger.info(f"[{username}] Session expired or invalid, creating new session")
                    del self._sessions[username]
            
            # Create new session
            client = APIClient()
            success, error = client.login(username, password)
            
            if success:
                session_info = SessionInfo(
                    client=client,
                    username=username,
                    password=password,
                    login_time=datetime.now(),
                    last_used=datetime.now(),
                    is_valid=True
                )
                self._sessions[username] = session_info
                self._logger.info(f"[{username}] Created new session successfully")
                return client, True
            else:
                self._logger.error(f"[{username}] Failed to create session: {error}")
                raise Exception(f"Login failed: {error}")
    
    def invalidate_session(self, username: str) -> None:
        """Mark a session as invalid (e.g., when login fails)."""
        with self._lock:
            if username in self._sessions:
                self._sessions[username].is_valid = False
                self._logger.info(f"[{username}] Session marked as invalid")
    
    def remove_session(self, username: str) -> None:
        """Remove a session completely."""
        with self._lock:
            if username in self._sessions:
                del self._sessions[username]
                self._logger.info(f"[{username}] Session removed")
    
    def _cleanup_sessions(self) -> None:
        """Clean up expired and idle sessions."""
        current_time = datetime.now()
        to_remove = []
        
        for username, session_info in self._sessions.items():
            if (session_info.is_expired(self._max_age_minutes) or 
                session_info.is_idle(self._max_idle_minutes) or 
                not session_info.is_valid):
                to_remove.append(username)
        
        for username in to_remove:
            self._logger.info(f"[{username}] Cleaning up expired/idle session")
            del self._sessions[username]
    
    def get_session_stats(self) -> Dict[str, any]:
        """Get statistics about current sessions."""
        with self._lock:
            self._cleanup_sessions()
            return {
                'active_sessions': len(self._sessions),
                'sessions': {
                    username: {
                        'age_minutes': (datetime.now() - info.login_time).total_seconds() / 60,
                        'idle_minutes': (datetime.now() - info.last_used).total_seconds() / 60,
                        'is_valid': info.is_valid
                    }
                    for username, info in self._sessions.items()
                }
            }
    
    def clear_all_sessions(self) -> None:
        """Clear all sessions (useful for testing or reset)."""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            self._logger.info(f"Cleared {count} sessions")

# Global session manager instance
session_manager = SessionManager()