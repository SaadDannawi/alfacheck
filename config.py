"""Configuration settings for the Alfa Account Data Extraction Script."""

from typing import Dict, Final
from dataclasses import dataclass
from pathlib import Path

@dataclass
class APIEndpoints:
    """API endpoints configuration."""
    BASE_URL: str = "https://www.alfa.com.lb"
    LOGIN: str = f"{BASE_URL}/en/account/login?returnUrl=%2Fen%2Faccount"
    ACCOUNT: str = f"{BASE_URL}/en/account"
    CONSUMPTION: str = f"{BASE_URL}/en/account/getconsumption"
    EXPIRY: str = f"{BASE_URL}/en/account/getexpirydate"
    LAST_RECHARGE: str = f"{BASE_URL}/en/account/getlastrecharge"
    SERVICES: str = f"{BASE_URL}/en/account/manage-services/getmyservices"
    MY_LINE: str = f"{BASE_URL}/en/account/my-line"
    DASHBOARD: str = f"{BASE_URL}/en/account/dashboard"
    MANAGE_SERVICES: str = f"{BASE_URL}/en/account/manage-services"
    
    def get_consumption_url(self, timestamp: int = None) -> str:
        """Generate consumption URL with optional timestamp parameter.
        
        Args:
            timestamp: Unix timestamp in milliseconds. If None, uses current time.
            
        Returns:
            str: Complete consumption URL with timestamp parameter
        """
        import time
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        return f"{self.BASE_URL}/en/account/getconsumption?_={timestamp}"

@dataclass
class FileConfig:
    """File-related configuration."""
    INPUT_CSV: str = "accounts.csv"
    OUTPUT_CSV: str = "results.csv"
    LOG_FILE: str = "scraper.log"
    DEBUG_MODE: bool = True

@dataclass
class NetworkConfig:
    """Network-related configuration."""
    MAX_WORKERS: int = 50  # Increased for very high speed processing
    REQUEST_TIMEOUT: int = 60  # Increased timeout to handle slow server responses
    RETRY_ATTEMPTS: int = 3  # Reduced retry attempts for speed
    RETRY_DELAY: int = 1  # Reduced delay between retries
    VERIFY_SSL: bool = True
    REQUEST_DELAY: float = 0.2  # Optimized delay between API requests (seconds)
    SESSION_REFRESH_ATTEMPTS: int = 2  # Number of session refresh attempts
    
    def get_request_delay(self) -> float:
        """Get request delay, with bot config override if available."""
        try:
            from bot_config import bot_config
            if hasattr(bot_config, 'REQUEST_DELAY'):
                return bot_config.REQUEST_DELAY
        except ImportError:
            pass
        return self.REQUEST_DELAY
    
    def get_max_workers(self) -> int:
        """Get max workers, with bot config override if available."""
        try:
            from bot_config import bot_config
            if hasattr(bot_config, 'MAX_CONCURRENT_WORKERS'):
                return bot_config.MAX_CONCURRENT_WORKERS
        except ImportError:
            pass
        return self.MAX_WORKERS

# HTTP Headers
DEFAULT_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.5",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}

HTML_ACCEPT_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": DEFAULT_HEADERS["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Required fields for output
REQUIRED_FIELDS: Final[tuple] = (
    "username", "status", "activation_date", "validity_days_remaining",
    "current_balance", "last_recharge_amount", "last_recharge_date",
    "service_details", "secondary_numbers", 
    "main_consumption", "mobile_internet_consumption", "secondary_consumption",
    "subscription_date", "validity_date",
    "error_details"
)

# Initialize configuration objects
api_endpoints = APIEndpoints()
file_config = FileConfig()
network_config = NetworkConfig()

# Get absolute paths
current_dir = Path.cwd()
input_file_path = current_dir / file_config.INPUT_CSV
output_file_path = current_dir / file_config.OUTPUT_CSV
log_file_path = current_dir / file_config.LOG_FILE
