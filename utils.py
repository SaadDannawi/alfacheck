"""Utility functions for the Alfa Account Data Extraction Script."""

import logging
import json
import re
from typing import Optional, Dict, Any
from pathlib import Path
from bs4 import BeautifulSoup
from config import file_config

def setup_logging() -> None:
    """Configure logging with file and console handlers."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
        handlers=[
            logging.FileHandler(file_config.LOG_FILE, mode='w'),
            logging.StreamHandler()
        ]
    )

def save_debug_file(username: str, filename: str, content: str) -> None:
    """Save debug files if debug mode is enabled.
    
    Creates a debug folder for each username and stores files there.
    """
    if not file_config.DEBUG_MODE:
        return

    try:
        # Create debug directory with username
        debug_dir = Path.cwd() / "debug" / username
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
        filepath = debug_dir / safe_filename
        
        filepath.write_text(content, encoding="utf-8")
        logging.debug(f"[{username}] Saved debug file: {filepath}")
    except Exception as e:
        logging.error(f"[{username}] Failed to save debug file {filename}: {e}")

def parse_json_safely(json_text: str, username: str, field_name: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON with error handling and JSON extraction from HTML."""
    if not json_text:
        logging.warning(f"[{username}] Empty response received for {field_name}.")
        return None

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        logging.warning(
            f"[{username}] Failed to parse JSON for {field_name}. "
            f"Raw content: {json_text[:200]}..."
        )
        
        # Try to extract JSON from HTML if embedded
        json_match = re.search(r'{s*"\w+".*}s*$', json_text, re.DOTALL | re.MULTILINE)
        if json_match:
            try:
                extracted_json = json_match.group(0)
                logging.debug(
                    f"[{username}] Attempting to parse extracted JSON: "
                    f"{extracted_json[:100]}..."
                )
                return json.loads(extracted_json)
            except json.JSONDecodeError:
                logging.warning(f"[{username}] Failed to parse extracted JSON for {field_name}.")
                
        return None

def extract_html_field(
    soup: BeautifulSoup,
    field_name: str,
    class_name: str,
    pattern: Optional[str] = None
) -> str:
    """Extract field from HTML using class name and optional pattern."""
    try:
        element = soup.find(class_=class_name)
        if not element:
            return "Not Found"
            
        text = element.get_text(strip=True)
        if not text:
            return "Not Found"
            
        if pattern:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
                
        return text
        
    except Exception as e:
        logging.warning(f"Error extracting {field_name} from HTML: {e}")
        return "Not Found"

def parse_quota_info(name_en: str, content_en: str, username: str = '') -> Optional[str]:
    """Parse quota information from service name and content.
    
    Handles decimal values and unit conversions (MB to GB if needed).
    Logs transformations for debugging.
    """
    if not name_en and not content_en:
        return None
        
    # Try to match quota in both name and content
    quota_pattern = r'(\d+(?:\.\d+)?)\s*(GB|MB|gb|mb)'
    
    def format_quota(value: str, unit: str, source: str) -> str:
        """Format quota value with appropriate unit."""
        try:
            num_val = float(value)
            unit = unit.upper()
            original = f"{value} {unit}"
            
            # Convert MB to GB if >= 1024 MB
            if unit == 'MB' and num_val >= 1024:
                num_val /= 1024
                unit = 'GB'
                if username:
                    logging.debug(
                        f"[{username}] Converting quota: "
                        f"{original} -> {num_val:.2f} {unit}"
                    )
                
            # Format with appropriate decimal places
            if num_val.is_integer():
                value = str(int(num_val))
            else:
                value = f"{num_val:.2f}".rstrip('0').rstrip('.')
                
            if username:
                logging.debug(
                    f"[{username}] Found quota in {source}: "
                    f"{value} {unit}"
                )
            return f"({value} {unit})"
            
        except ValueError:
            if username:
                logging.warning(
                    f"[{username}] Invalid quota value in {source}: "
                    f"{value} {unit}"
                )
            return f"({value} {unit.upper()})"
    
    # First try name as it's usually more reliable
    name_match = re.search(quota_pattern, name_en or '', re.IGNORECASE)
    if name_match:
        return format_quota(*name_match.groups(), source='name')

    # Then try content
    content_match = re.search(quota_pattern, content_en or '', re.IGNORECASE)
    if content_match:
        return format_quota(*content_match.groups(), source='content')
        
    return None

def format_service_detail(
    service_name: str,
    bundle_name: Optional[str] = None,
    quota_info: Optional[str] = None,
    username: str = ''
) -> str:
    """Format service detail string with bundle and quota information.
    
    Args:
        service_name: Name of the service
        bundle_name: Optional bundle name
        quota_info: Optional quota information (e.g. "20 GB")
        username: Optional username for logging
    
    Returns:
        Formatted service detail string
    """
    detail_parts = []
    
    # Always include service name
    detail_parts.append(service_name)
    
    # Add bundle info if different from service name
    if bundle_name and bundle_name.strip() != service_name.strip():
        detail_parts.append(f"[{bundle_name}]")
        if username:
            logging.debug(
                f"[{username}] Adding bundle info to service {service_name}: "
                f"{bundle_name}"
            )
    
    # Add quota if available
    if quota_info:
        detail_parts.append(quota_info)
        if username:
            logging.debug(
                f"[{username}] Adding quota info to service {service_name}: "
                f"{quota_info}"
            )
    
    formatted = " ".join(part.strip() for part in detail_parts if part and part.strip())
    if username:
        logging.debug(
            f"[{username}] Formatted service detail: {formatted}"
        )
    return formatted

def sanitize_phone_number(number: str, username: str) -> bool:
    """Validate and sanitize Lebanese phone number.
    
    Args:
        number: The phone number to validate
        username: The main account number to compare against
        
    Returns:
        bool: True if number is valid and not the main account number
    """
    if not number:
        logging.debug(f"[{username}] Empty phone number provided")
        return False
        
    # Clean input by removing non-digits and common prefixes
    clean_number = ''.join(c for c in str(number) if c.isdigit())
    clean_username = ''.join(c for c in str(username) if c.isdigit())
    
    if not clean_number:
        logging.debug(f"[{username}] No digits found in number: {number}")
        return False
        
    original_number = clean_number
        
    # Handle country code variations
    prefixes = ['961', '00961', '+961']
    for prefix in prefixes:
        prefix = prefix.replace('+', '')
        if clean_number.startswith(prefix):
            clean_number = clean_number[len(prefix):]
            logging.debug(
                f"[{username}] Removed prefix {prefix} from {original_number} -> {clean_number}"
            )
        if clean_username.startswith(prefix):
            clean_username = clean_username[len(prefix):]
    
    # Lebanese mobile numbers should:
    # - Be 8 digits long with leading zeros if needed
    # - Start with 3, 7, 8 (Alfa) or 71 (Touch)
    # - Not be the main number
    valid_starts = ['3', '7', '8']
    
    # Pad with leading zeros if needed
    if len(clean_number) < 8:
        clean_number = clean_number.zfill(8)
        logging.debug(
            f"[{username}] Added leading zeros: {original_number} -> {clean_number}"
        )
    elif len(clean_number) > 8:
        logging.debug(
            f"[{username}] Invalid length for {original_number} -> {clean_number}: "
            f"got {len(clean_number)}, expected 8"
        )
        return False
        
    if not (clean_number[0] in valid_starts or clean_number.startswith('71')):
        logging.debug(
            f"[{username}] Invalid prefix for {original_number} -> {clean_number}: "
            f"must start with {valid_starts} or 71"
        )
        return False
        
    if not clean_number.isdigit():
        logging.debug(
            f"[{username}] Non-digit characters in {original_number} -> {clean_number}"
        )
        return False
        
    if clean_number == clean_username:
        logging.debug(
            f"[{username}] Secondary number matches main number: {clean_number}"
        )
        return False
        
    logging.debug(
        f"[{username}] Valid secondary number: {original_number} -> {clean_number}"
    )
    return True
