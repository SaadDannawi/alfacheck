"""Data models for the Alfa Account Data Extraction Script."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class AccountCredentials:
    """Account credentials model."""
    username: str
    password: str

@dataclass
class ServiceInfo:
    """Service information model."""
    name: str
    status: int
    bundle_name: Optional[str] = None
    quota_info: Optional[str] = None

@dataclass
class AccountData:
    """Account data model."""
    username: str
    status: str = "Error"
    error_details: str = ""
    activation_date: str = "Not Found"
    validity_days_remaining: Any = "Not Found"
    current_balance: Any = "Not Found"
    last_recharge_amount: Any = "Not Found"
    last_recharge_date: str = "Not Found"
    service_details: str = "None"
    secondary_numbers: str = "None"
    # Detailed consumption data
    main_consumption: str = "Not Found"
    mobile_internet_consumption: str = "Not Found"
    secondary_consumption: str = "Not Found"
    # Manage-services page data
    subscription_date: str = "Not Found"
    validity_date: str = "Not Found"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the account data to a dictionary."""
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }

@dataclass
class APIResponse:
    """API response model."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    raw_response: Optional[str] = None

@dataclass
class ProcessingResult:
    """Processing result model with statistics."""
    total_accounts: int = 0
    successful: int = 0
    partial: int = 0
    failed: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: List[AccountData] = field(default_factory=list)

    def add_result(self, result: AccountData) -> None:
        """Add a processed account result and update statistics."""
        self.results.append(result)
        if result.status == "Success":
            self.successful += 1
        elif result.status == "Partial Success":
            self.partial += 1
        else:
            self.failed += 1

    def complete(self) -> None:
        """Mark processing as complete and set end time."""
        self.end_time = datetime.now()

    @property
    def processing_time(self) -> float:
        """Calculate total processing time in seconds."""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if not self.total_accounts:
            return 0.0
        return (self.successful / self.total_accounts) * 100
