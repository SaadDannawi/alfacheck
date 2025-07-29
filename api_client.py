"""API client for the Alfa Account Data Extraction Script."""

import logging
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

from config import (
    api_endpoints,
    network_config,
    DEFAULT_HEADERS,
    HTML_ACCEPT_HEADERS
)
from models import APIResponse, AccountData
from utils import save_debug_file, parse_json_safely

class APIClient:
    """Client for making API requests with retry and error handling."""
    
    def __init__(self) -> None:
        """Initialize the API client with a session and retry configuration."""
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create and configure a requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy with more robust retry conditions
        retry_strategy = Retry(
            total=network_config.RETRY_ATTEMPTS,
            backoff_factor=network_config.RETRY_DELAY,
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True,
            # Add connection errors and read timeouts to retry list
            connect=3,
            read=3,
            # Include more status codes that might benefit from retry
            status_forcelist=[408, 429, 500, 502, 503, 504, 401, 403]
        )
        
        # Mount adapter with retry strategy for both HTTP and HTTPS
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
        
    def login(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Authenticate with the Alfa website.
        
        Returns:
            Tuple[bool, Optional[str]]: Success status and error message if failed
        """
        headers = HTML_ACCEPT_HEADERS.copy()
        headers["Referer"] = api_endpoints.BASE_URL
        
        try:
            # Load login page
            response = self.session.get(
                api_endpoints.LOGIN,
                headers=headers,
                timeout=network_config.REQUEST_TIMEOUT,
                verify=network_config.VERIFY_SSL
            )
            response.raise_for_status()
            save_debug_file(username, "01_login_page.html", response.text)
            
            # Extract hidden form fields
            soup = BeautifulSoup(response.text, 'html.parser')
            hidden_inputs = {
                inp.get('name'): inp.get('value', '')
                for inp in soup.find_all("input", type="hidden")
                if inp.get('name')
            }
            
            # Prepare login data
            login_data = {
                "UserName": username,
                "Password": password,
                "RememberMe": "false"
            }
            login_data.update(hidden_inputs)
            
            # Set headers for login request
            login_headers = HTML_ACCEPT_HEADERS.copy()
            login_headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": api_endpoints.BASE_URL,
                "Referer": api_endpoints.LOGIN
            })
            
            # Perform login
            response = self.session.post(
                api_endpoints.LOGIN,
                data=login_data,
                headers=login_headers,
                allow_redirects=True,
                timeout=network_config.REQUEST_TIMEOUT,
                verify=network_config.VERIFY_SSL
            )
            response.raise_for_status()
            save_debug_file(username, "02_login_response.html", response.text)
            
            # Verify login success
            if (api_endpoints.ACCOUNT in response.url or
                "Dashboard" in response.text or
                username in response.text):
                
                # Verify dashboard access
                dash_resp = self.session.get(
                    api_endpoints.ACCOUNT,
                    headers=HTML_ACCEPT_HEADERS,
                    timeout=network_config.REQUEST_TIMEOUT,
                    verify=network_config.VERIFY_SSL
                )
                save_debug_file(username, "03_dashboard_page.html", dash_resp.text)
                
                if username in dash_resp.text or "Current Balance" in dash_resp.text:
                    logging.info(f"[{username}] Login successful")
                    # Extreme minimal delay after login for maximum speed
                    time.sleep(0.02)  # Extreme minimal delay for maximum concurrency
                    logging.debug(f"[{username}] Post-login delay completed")
                    return True, None
                    
                return False, "Dashboard verification failed"
                
            if "Invalid username or password" in response.text:
                return False, "Invalid credentials"
                
            return False, f"Login failed. Final URL: {response.url}"
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Login request failed: {str(e)}"
            logging.error(f"[{username}] {error_msg}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error during login: {str(e)}"
            logging.error(f"[{username}] {error_msg}")
            return False, error_msg

    def _refresh_session(self, username: str, password: str) -> bool:
        """Refresh the session by logging in again."""
        logging.info(f"[{username}] Refreshing session...")
        self.session = self._create_session()
        success, _ = self.login(username, password)
        return success

    def make_api_request(
        self,
        url: str,
        username: str,
        description: str,
        method: str = 'GET',
        data: Optional[Dict[str, Any]] = None,
        password: Optional[str] = None,  # Added for session refresh
        retry_count: int = 0,
        headers: Optional[Dict[str, str]] = None  # Added for custom headers
    ) -> APIResponse:
        """Make an API request with error handling.
        
        Returns:
            APIResponse: Object containing response data and status
        """
        request_headers = DEFAULT_HEADERS.copy()
        request_headers["Referer"] = api_endpoints.ACCOUNT
        if headers:
            request_headers.update(headers)
        
        try:
            logging.debug(f"[{username}] Fetching {description} from API: {url}")
            
            if method == 'POST':
                response = self.session.post(
                    url,
                    headers=request_headers,
                    data=data,
                    timeout=network_config.REQUEST_TIMEOUT,
                    verify=network_config.VERIFY_SSL
                )
            else:
                response = self.session.get(
                    url,
                    headers=request_headers,
                    timeout=network_config.REQUEST_TIMEOUT,
                    verify=network_config.VERIFY_SSL
                )
                
            # Save numbered API responses (starting from 04 after login/dashboard files)
            file_number = len(list(Path('debug', username).glob('*.txt'))) + 4
            save_debug_file(
                username,
                f"{file_number:02d}_{description.replace(' ', '_')}_response.txt",
                response.text
            )
            response.raise_for_status()
            
            # Check if we got HTML instead of JSON (session might be expired)
            content_type = response.headers.get('Content-Type', '').lower()
            is_html = 'text/html' in content_type or '<html' in response.text[:1000].lower()
            
            if is_html and password and retry_count < 2:
                logging.warning(f"[{username}] Received HTML response for {description}, session might be expired")
                # Don't refresh session here - let session manager handle it
                # Just return error to indicate session issue
                return APIResponse(
                    success=False,
                    error="Session expired - HTML response received",
                    status_code=response.status_code,
                    raw_response=response.text
                )
                    
            # Try to parse as JSON regardless of content type
            parsed_data = parse_json_safely(response.text, username, description)
            if parsed_data:
                return APIResponse(
                    success=True,
                    data=parsed_data,
                    status_code=response.status_code,
                    raw_response=response.text
                )
            
            # If we got HTML and couldn't parse as JSON, include HTML parsing error
            if is_html:
                soup = BeautifulSoup(response.text, 'html.parser')
                error_elem = soup.find(class_=['error', 'alert', 'message'])
                error_msg = error_elem.get_text().strip() if error_elem else "Received HTML instead of JSON"
                return APIResponse(
                    success=False,
                    error=f"HTML Error: {error_msg}",
                    status_code=response.status_code,
                    raw_response=response.text
                )
                
            return APIResponse(
                success=False,
                error=f"Unexpected content type: {content_type}",
                status_code=response.status_code,
                raw_response=response.text
            )
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout fetching {description} from API: {url}"
            logging.error(f"[{username}] {error_msg}")
            return APIResponse(success=False, error=error_msg)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching {description} from API: {url} - {str(e)}"
            logging.error(f"[{username}] {error_msg}")
            return APIResponse(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error fetching {description} from API: {url} - {str(e)}"
            logging.error(f"[{username}] {error_msg}")
            return APIResponse(success=False, error=error_msg)
