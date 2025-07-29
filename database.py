"""Database models and management for Telegram Bot."""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, JSON, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///telegram_bot.db')

# Create database engine
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """User model for storing user information."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language = Column(String(10), default='en')
    is_authorized = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # Statistics
    total_requests = Column(Integer, default=0)
    total_accounts_processed = Column(Integer, default=0)
    
    # Default password for account processing
    default_password = Column(String(255), nullable=True)
    
    # Customer dashboard
    customer_page_id = Column(String(36), unique=True, nullable=True, index=True)  # UUID for customer page
    customer_page_created = Column(DateTime, nullable=True)
    customer_page_last_accessed = Column(DateTime, nullable=True)
    
    # Relationships
    sessions = relationship('UserSession', back_populates='user', cascade='all, delete-orphan')
    requests = relationship('ProcessingRequest', back_populates='user', cascade='all, delete-orphan')

class UserSession(Base):
    """User session model for tracking active sessions."""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    session_start = Column(DateTime, default=datetime.utcnow)
    session_end = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_processing = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Rate limiting
    last_request_time = Column(DateTime, nullable=True)
    request_count_hour = Column(Integer, default=0)
    hour_reset_time = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='sessions')

class ProcessingRequest(Base):
    """Processing request model for tracking account processing requests."""
    __tablename__ = 'processing_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    request_time = Column(DateTime, default=datetime.utcnow)
    total_accounts = Column(Integer, nullable=False)
    processing_mode = Column(String(50), nullable=False)  # 'batch' or 'sequential'
    
    # Processing status
    status = Column(String(50), default='pending')  # pending, processing, completed, failed
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    
    # Results summary
    successful_accounts = Column(Integer, default=0)
    partial_accounts = Column(Integer, default=0)
    failed_accounts = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    
    # Error information
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='requests')
    account_results = relationship('AccountResult', back_populates='request', cascade='all, delete-orphan')

class AccountResult(Base):
    """Account result model for storing individual account processing results."""
    __tablename__ = 'account_results'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('processing_requests.id'), nullable=True)
    transaction_id = Column(String(36), ForeignKey('transactions.transaction_id'), nullable=True)
    account_username = Column(String(255), nullable=False)
    
    # Processing info
    processed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), nullable=False)  # Success, Partial Success, Error
    error_details = Column(Text, nullable=True)
    
    # Account data
    activation_date = Column(String(255), nullable=True)
    validity_days_remaining = Column(String(255), nullable=True)
    current_balance = Column(String(255), nullable=True)
    last_recharge_amount = Column(String(255), nullable=True)
    last_recharge_date = Column(String(255), nullable=True)
    service_details = Column(Text, nullable=True)
    secondary_numbers = Column(Text, nullable=True)
    
    # Consumption data
    main_consumption = Column(String(255), nullable=True)
    mobile_internet_consumption = Column(String(255), nullable=True)
    secondary_consumption = Column(String(255), nullable=True)
    
    # Service dates
    subscription_date = Column(String(255), nullable=True)
    validity_date = Column(String(255), nullable=True)
    
    # Raw data (for debugging)
    raw_data = Column(JSON, nullable=True)
    
    # Relationships
    request = relationship('ProcessingRequest', back_populates='account_results')
    transaction = relationship('Transaction', back_populates='account_results')

class Transaction(Base):
    """Transaction model for tracking individual scan operations with unique IDs."""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    
    # Transaction details
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default='pending')  # pending, processing, completed, failed
    
    # Scan details
    total_numbers = Column(Integer, nullable=False)
    successful_numbers = Column(Integer, default=0)
    failed_numbers = Column(Integer, default=0)
    
    # Processing info
    processing_time_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Dashboard access
    dashboard_accessed = Column(Boolean, default=False)
    last_dashboard_access = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship('User', backref='transactions')
    account_results = relationship('AccountResult', back_populates='transaction', cascade='all, delete-orphan')

class SystemStats(Base):
    """System statistics model for tracking bot performance."""
    __tablename__ = 'system_stats'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    
    # Daily statistics
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    total_accounts_processed = Column(Integer, default=0)
    
    # Performance metrics
    average_processing_time = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    
    # Error tracking
    total_errors = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)

class DatabaseManager:
    """Database manager for handling database operations."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def init_db(self):
        """Initialize database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_or_create_user(self, user_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> User:
        """Get existing user or create new one."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                session.commit()
                logger.info(f"Created new user: {user_id} ({username})")
            else:
                # Update user info if provided
                updated = False
                if username and user.username != username:
                    user.username = username
                    updated = True
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    user.updated_at = datetime.utcnow()
                
                user.last_seen = datetime.utcnow()
                session.commit()
            
            return user
    
    def create_session(self, user_id: int) -> UserSession:
        """Create new user session."""
        with self.get_session() as session:
            # End any existing active sessions
            existing_sessions = session.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            ).all()
            
            for existing_session in existing_sessions:
                existing_session.is_active = False
                existing_session.session_end = datetime.utcnow()
            
            # Create new session
            new_session = UserSession(user_id=user_id)
            session.add(new_session)
            session.commit()
            
            return new_session
    
    def get_active_session(self, user_id: int) -> Optional[UserSession]:
        """Get active session for user."""
        with self.get_session() as session:
            return session.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            ).first()
    
    def update_session_activity(self, user_id: int):
        """Update last activity time for user session."""
        with self.get_session() as session:
            user_session = session.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            ).first()
            
            if user_session:
                user_session.last_activity = datetime.utcnow()
                session.commit()
    
    def start_processing_request(self, user_id: int, total_accounts: int, 
                               processing_mode: str) -> int:
        """Start new processing request and return request ID."""
        with self.get_session() as session:
            request = ProcessingRequest(
                user_id=user_id,
                total_accounts=total_accounts,
                processing_mode=processing_mode,
                status='processing',
                start_time=datetime.utcnow()
            )
            session.add(request)
            session.commit()
            
            # Store the ID before session closes
            request_id = request.id
            
            # Update user session processing status
            user_session = session.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            ).first()
            
            if user_session:
                user_session.is_processing = True
                session.commit()
            
            return request_id
    
    def complete_processing_request(self, request_id: int, successful: int, 
                                  partial: int, failed: int, error_message: str = None):
        """Complete processing request with results."""
        with self.get_session() as session:
            request = session.query(ProcessingRequest).filter(
                ProcessingRequest.id == request_id
            ).first()
            
            if request:
                request.end_time = datetime.utcnow()
                request.successful_accounts = successful
                request.partial_accounts = partial
                request.failed_accounts = failed
                request.success_rate = (successful / request.total_accounts) * 100 if request.total_accounts > 0 else 0
                request.processing_time_seconds = (request.end_time - request.start_time).total_seconds()
                request.status = 'completed' if not error_message else 'failed'
                request.error_message = error_message
                
                # Update user statistics
                user = session.query(User).filter(User.user_id == request.user_id).first()
                if user:
                    user.total_requests += 1
                    user.total_accounts_processed += request.total_accounts
                
                # Update user session processing status
                user_session = session.query(UserSession).filter(
                    UserSession.user_id == request.user_id,
                    UserSession.is_active == True
                ).first()
                
                if user_session:
                    user_session.is_processing = False
                    user_session.last_request_time = datetime.utcnow()
                    user_session.request_count_hour += 1
                
                session.commit()
    
    def save_account_result(self, request_id: int, account_data: 'AccountData'):
        """Save individual account result."""
        with self.get_session() as session:
            result = AccountResult(
                request_id=request_id,
                account_username=account_data.username,
                status=account_data.status,
                error_details=account_data.error_details,
                activation_date=account_data.activation_date,
                validity_days_remaining=str(account_data.validity_days_remaining),
                current_balance=str(account_data.current_balance),
                last_recharge_amount=str(account_data.last_recharge_amount),
                last_recharge_date=account_data.last_recharge_date,
                service_details=account_data.service_details,
                secondary_numbers=account_data.secondary_numbers,
                main_consumption=account_data.main_consumption,
                mobile_internet_consumption=account_data.mobile_internet_consumption,
                secondary_consumption=account_data.secondary_consumption,
                subscription_date=account_data.subscription_date,
                validity_date=account_data.validity_date,
                raw_data=account_data.to_dict()
            )
            session.add(result)
            session.commit()
    
    def save_account_results_batch(self, request_id: int, account_data_list: List['AccountData']):
        """Save multiple account results in a single transaction for better performance."""
        if not account_data_list:
            return
            
        with self.get_session() as session:
            results = []
            for account_data in account_data_list:
                result = AccountResult(
                    request_id=request_id,
                    account_username=account_data.username,
                    status=account_data.status,
                    error_details=account_data.error_details,
                    activation_date=account_data.activation_date,
                    validity_days_remaining=str(account_data.validity_days_remaining),
                    current_balance=str(account_data.current_balance),
                    last_recharge_amount=str(account_data.last_recharge_amount),
                    last_recharge_date=account_data.last_recharge_date,
                    service_details=account_data.service_details,
                    secondary_numbers=account_data.secondary_numbers,
                    main_consumption=account_data.main_consumption,
                    mobile_internet_consumption=account_data.mobile_internet_consumption,
                    secondary_consumption=account_data.secondary_consumption,
                    subscription_date=account_data.subscription_date,
                    validity_date=account_data.validity_date,
                    raw_data=account_data.to_dict()
                )
                results.append(result)
            
            session.add_all(results)
            session.commit()
            logger.info(f"Batch saved {len(results)} account results for request {request_id}")
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                return {}
            
            # Get recent requests (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_requests = session.query(ProcessingRequest).filter(
                ProcessingRequest.user_id == user_id,
                ProcessingRequest.request_time >= thirty_days_ago
            ).all()
            
            total_recent_accounts = sum(req.total_accounts for req in recent_requests)
            total_recent_successful = sum(req.successful_accounts for req in recent_requests)
            
            return {
                'user_id': user.user_id,
                'username': user.username,
                'total_requests': user.total_requests,
                'total_accounts_processed': user.total_accounts_processed,
                'recent_requests_30d': len(recent_requests),
                'recent_accounts_30d': total_recent_accounts,
                'recent_success_rate_30d': (total_recent_successful / total_recent_accounts * 100) if total_recent_accounts > 0 else 0,
                'member_since': user.created_at,
                'last_seen': user.last_seen
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics."""
        with self.get_session() as session:
            # Total users
            total_users = session.query(User).count()
            
            # Active users (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            active_users = session.query(User).filter(User.last_seen >= yesterday).count()
            
            # Total requests
            total_requests = session.query(ProcessingRequest).count()
            
            # Total accounts processed
            total_accounts = session.query(func.sum(ProcessingRequest.total_accounts)).scalar() or 0
            
            # Success rate
            total_successful = session.query(func.sum(ProcessingRequest.successful_accounts)).scalar() or 0
            success_rate = (total_successful / total_accounts * 100) if total_accounts > 0 else 0
            
            # Average processing time
            avg_processing_time = session.query(func.avg(ProcessingRequest.processing_time_seconds)).scalar() or 0
            
            return {
                'total_users': total_users,
                'active_users_24h': active_users,
                'total_requests': total_requests,
                'total_accounts_processed': total_accounts,
                'overall_success_rate': success_rate,
                'average_processing_time': avg_processing_time,
                'database_size': self._get_database_size()
            }
    
    def _get_database_size(self) -> str:
        """Get database file size."""
        try:
            if 'sqlite' in DATABASE_URL:
                db_path = DATABASE_URL.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    if size_bytes < 1024:
                        return f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        return f"{size_bytes / 1024:.1f} KB"
                    else:
                        return f"{size_bytes / (1024 * 1024):.1f} MB"
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def cleanup_old_data(self, days: int = 90):
        """Clean up old data older than specified days."""
        with self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old processing requests and their results
            old_requests = session.query(ProcessingRequest).filter(
                ProcessingRequest.request_time < cutoff_date
            ).all()
            
            for request in old_requests:
                session.delete(request)
            
            # Delete old inactive sessions
            old_sessions = session.query(UserSession).filter(
                UserSession.session_start < cutoff_date,
                UserSession.is_active == False
            ).all()
            
            for session_obj in old_sessions:
                session.delete(session_obj)
            
            session.commit()
            logger.info(f"Cleaned up data older than {days} days")
    
    def authorize_user(self, user_id: int) -> bool:
        """Authorize a user in the database."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.is_authorized = True
                user.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"User {user_id} authorized in database")
                return True
            return False
    
    def revoke_user_authorization(self, user_id: int) -> bool:
        """Revoke user authorization in the database."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.is_authorized = False
                user.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"User {user_id} authorization revoked in database")
                return True
            return False
    
    def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized in the database."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            return user.is_authorized if user else False
    
    def get_authorized_users(self) -> List[int]:
        """Get list of all authorized user IDs from database."""
        with self.get_session() as session:
            authorized_users = session.query(User).filter(User.is_authorized == True).all()
            return [user.user_id for user in authorized_users]
    
    def set_user_default_password(self, user_id: int, password: str) -> bool:
        """Set default password for a user."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.default_password = password
                user.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"Default password set for user {user_id}")
                return True
            return False
    
    def get_user_default_password(self, user_id: int) -> Optional[str]:
        """Get default password for a user."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            return user.default_password if user else None
    
    def get_or_create_customer_page(self, user_id: int) -> str:
        """Get existing customer page ID or create new one."""
        import uuid
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                return None
            
            if not user.customer_page_id:
                # Create new customer page ID
                user.customer_page_id = str(uuid.uuid4())
                user.customer_page_created = datetime.utcnow()
                session.commit()
                logger.info(f"Created customer page {user.customer_page_id} for user {user_id}")
            
            return user.customer_page_id
    
    def update_customer_page_access(self, user_id: int) -> bool:
        """Update last access time for customer page."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and user.customer_page_id:
                user.customer_page_last_accessed = datetime.utcnow()
                session.commit()
                return True
            return False
    
    def get_customer_page_user(self, customer_page_id: str) -> Optional[int]:
        """Get user ID from customer page ID."""
        with self.get_session() as session:
            user = session.query(User).filter(User.customer_page_id == customer_page_id).first()
            return user.user_id if user else None
    
    def get_customer_results(self, user_id: int, limit: int = 1000) -> List[Dict]:
        """Get the most recent account result for each phone number for a customer."""
        with self.get_session() as session:
            # Use a subquery to get the most recent result for each account_username
            subquery = session.query(
                AccountResult.account_username,
                func.max(AccountResult.processed_at).label('max_processed_at')
            ).join(Transaction).filter(
                Transaction.user_id == user_id
            ).group_by(AccountResult.account_username).subquery()
            
            # Get the full results for the most recent entries
            results = session.query(AccountResult).join(Transaction).join(
                subquery,
                and_(
                    AccountResult.account_username == subquery.c.account_username,
                    AccountResult.processed_at == subquery.c.max_processed_at
                )
            ).filter(
                Transaction.user_id == user_id
            ).order_by(AccountResult.processed_at.desc()).limit(limit).all()
            
            # Convert to dictionaries with transaction info
            customer_results = []
            for result in results:
                # Get transaction info
                transaction = session.query(Transaction).filter(
                    Transaction.transaction_id == result.transaction_id
                ).first()
                
                # Ensure error_details is never null/empty for failed results
                error_details = result.error_details
                if result.status in ['error', 'failed'] and not error_details:
                    error_details = "Processing failed - no specific error details available"
                
                result_dict = {
                    'id': result.id,
                    'account_username': result.account_username,
                    'status': result.status,
                    'processed_at': result.processed_at,
                    'transaction_id': result.transaction_id,
                    'transaction_date': transaction.created_at if transaction else None,
                    'activation_date': result.activation_date,
                    'validity_days_remaining': result.validity_days_remaining,
                    'current_balance': result.current_balance,
                    'last_recharge_amount': result.last_recharge_amount,
                    'last_recharge_date': result.last_recharge_date,
                    'service_details': result.service_details,
                    'secondary_numbers': result.secondary_numbers,
                    'main_consumption': result.main_consumption,
                    'mobile_internet_consumption': result.mobile_internet_consumption,
                    'secondary_consumption': result.secondary_consumption,
                    'subscription_date': result.subscription_date,
                    'validity_date': result.validity_date,
                    'error_details': error_details
                }
                customer_results.append(result_dict)
            
            return customer_results
    
    def get_customer_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a customer."""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                return {}
            
            # Get transaction count
            transaction_count = session.query(Transaction).filter(
                Transaction.user_id == user_id
            ).count()
            
            # Get total accounts processed
            total_accounts = session.query(func.sum(Transaction.total_numbers)).filter(
                Transaction.user_id == user_id
            ).scalar() or 0
            
            # Get success statistics
            successful_accounts = session.query(func.sum(Transaction.successful_numbers)).filter(
                Transaction.user_id == user_id
            ).scalar() or 0
            
            failed_accounts = session.query(func.sum(Transaction.failed_numbers)).filter(
                Transaction.user_id == user_id
            ).scalar() or 0
            
            # Get recent activity (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_transactions = session.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= thirty_days_ago
            ).count()
            
            recent_accounts = session.query(func.sum(Transaction.total_numbers)).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= thirty_days_ago
            ).scalar() or 0
            
            # Get last transaction date
            last_transaction = session.query(Transaction).filter(
                Transaction.user_id == user_id
            ).order_by(Transaction.created_at.desc()).first()
            
            success_rate = (successful_accounts / total_accounts * 100) if total_accounts > 0 else 0
            
            return {
                'user_id': user.user_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'member_since': user.created_at,
                'customer_page_created': user.customer_page_created,
                'last_seen': user.last_seen,
                'total_transactions': transaction_count,
                'total_accounts_processed': total_accounts,
                'successful_accounts': successful_accounts,
                'failed_accounts': failed_accounts,
                'success_rate': success_rate,
                'recent_transactions_30d': recent_transactions,
                'recent_accounts_30d': recent_accounts,
                'last_transaction_date': last_transaction.created_at if last_transaction else None
            }
    
    def create_transaction(self, user_id: int, transaction_id: str, total_numbers: int) -> bool:
        """Create a new transaction."""
        with self.get_session() as session:
            transaction = Transaction(
                transaction_id=transaction_id,
                user_id=user_id,
                total_numbers=total_numbers
            )
            session.add(transaction)
            session.commit()
            logger.info(f"Transaction {transaction_id} created for user {user_id}")
            return True
    
    def start_transaction(self, transaction_id: str) -> bool:
        """Mark transaction as started."""
        with self.get_session() as session:
            transaction = session.query(Transaction).filter(
                Transaction.transaction_id == transaction_id
            ).first()
            if transaction:
                transaction.status = 'processing'
                transaction.started_at = datetime.utcnow()
                session.commit()
                return True
            return False
    
    def complete_transaction(self, transaction_id: str, successful_numbers: int, 
                           failed_numbers: int, processing_time: float, 
                           error_message: str = None) -> bool:
        """Mark transaction as completed."""
        with self.get_session() as session:
            transaction = session.query(Transaction).filter(
                Transaction.transaction_id == transaction_id
            ).first()
            if transaction:
                transaction.status = 'completed' if not error_message else 'failed'
                transaction.completed_at = datetime.utcnow()
                transaction.successful_numbers = successful_numbers
                transaction.failed_numbers = failed_numbers
                transaction.processing_time_seconds = processing_time
                transaction.error_message = error_message
                session.commit()
                return True
            return False
    
    def save_transaction_result(self, transaction_id: str, account_data: 'AccountData', request_id: int = None):
        """Save individual account result for a transaction."""
        with self.get_session() as session:
            # If no request_id provided, try to find an existing one or use None
            # The database schema should allow nullable request_id for transaction-only results
            result = AccountResult(
                request_id=request_id,  # This can be None for transaction-only results
                transaction_id=transaction_id,
                account_username=account_data.username,
                status=account_data.status,
                error_details=account_data.error_details,
                activation_date=account_data.activation_date,
                validity_days_remaining=str(account_data.validity_days_remaining),
                current_balance=str(account_data.current_balance),
                last_recharge_amount=str(account_data.last_recharge_amount),
                last_recharge_date=account_data.last_recharge_date,
                service_details=account_data.service_details,
                secondary_numbers=account_data.secondary_numbers,
                main_consumption=account_data.main_consumption,
                mobile_internet_consumption=account_data.mobile_internet_consumption,
                secondary_consumption=account_data.secondary_consumption,
                subscription_date=account_data.subscription_date,
                validity_date=account_data.validity_date,
                raw_data=account_data.to_dict()
            )
            session.add(result)
            session.commit()
    
    def save_transaction_results_batch(self, transaction_id: str, account_data_list: List['AccountData'], request_id: int = None):
        """Save multiple transaction results in a single transaction for better performance."""
        if not account_data_list:
            return
            
        with self.get_session() as session:
            results = []
            for account_data in account_data_list:
                result = AccountResult(
                    request_id=request_id,
                    transaction_id=transaction_id,
                    account_username=account_data.username,
                    status=account_data.status,
                    error_details=account_data.error_details,
                    activation_date=account_data.activation_date,
                    validity_days_remaining=str(account_data.validity_days_remaining),
                    current_balance=str(account_data.current_balance),
                    last_recharge_amount=str(account_data.last_recharge_amount),
                    last_recharge_date=account_data.last_recharge_date,
                    service_details=account_data.service_details,
                    secondary_numbers=account_data.secondary_numbers,
                    main_consumption=account_data.main_consumption,
                    mobile_internet_consumption=account_data.mobile_internet_consumption,
                    secondary_consumption=account_data.secondary_consumption,
                    subscription_date=account_data.subscription_date,
                    validity_date=account_data.validity_date,
                    raw_data=account_data.to_dict()
                )
                results.append(result)
            
            session.add_all(results)
            session.commit()
            logger.info(f"Batch saved {len(results)} transaction results for transaction {transaction_id}")
    
    def get_transaction(self, transaction_id: str, user_id: int = None) -> Optional['Transaction']:
        """Get transaction by ID, optionally filtered by user."""
        with self.get_session() as session:
            query = session.query(Transaction).filter(
                Transaction.transaction_id == transaction_id
            )
            if user_id:
                query = query.filter(Transaction.user_id == user_id)
            transaction = query.first()
            if transaction:
                # Refresh all attributes to avoid DetachedInstanceError
                session.refresh(transaction)
                # Create a detached copy with all attributes loaded
                transaction_copy = Transaction(
                    transaction_id=transaction.transaction_id,
                    user_id=transaction.user_id,
                    total_numbers=transaction.total_numbers,
                    successful_numbers=transaction.successful_numbers,
                    failed_numbers=transaction.failed_numbers,
                    processing_time_seconds=transaction.processing_time_seconds,
                    status=transaction.status,
                    error_message=transaction.error_message,
                    dashboard_accessed=transaction.dashboard_accessed
                )
                transaction_copy.created_at = transaction.created_at
                transaction_copy.started_at = transaction.started_at
                transaction_copy.completed_at = transaction.completed_at
                transaction_copy.last_dashboard_access = transaction.last_dashboard_access
                return transaction_copy
            return None
    
    def get_user_transactions(self, user_id: int, limit: int = 50) -> List['Transaction']:
        """Get user's transactions ordered by creation date."""
        with self.get_session() as session:
            return session.query(Transaction).filter(
                Transaction.user_id == user_id
            ).order_by(Transaction.created_at.desc()).limit(limit).all()
    
    def mark_dashboard_accessed(self, transaction_id: str) -> bool:
        """Mark that the dashboard was accessed for this transaction."""
        with self.get_session() as session:
            transaction = session.query(Transaction).filter(
                Transaction.transaction_id == transaction_id
            ).first()
            if transaction:
                transaction.dashboard_accessed = True
                transaction.last_dashboard_access = datetime.utcnow()
                session.commit()
                return True
            return False

# Global database manager instance
db_manager = DatabaseManager()

# Initialize database on import
try:
    db_manager.init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise