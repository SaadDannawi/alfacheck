"""Main script for the Alfa Account Data Extraction Script."""

import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from config import (
    api_endpoints,
    file_config,
    network_config,
    REQUIRED_FIELDS,
    HTML_ACCEPT_HEADERS,
    input_file_path,
    output_file_path
)
from models import AccountCredentials, AccountData, ProcessingResult, ServiceInfo
from utils import setup_logging, extract_html_field, parse_quota_info, format_service_detail, sanitize_phone_number, save_debug_file
from api_client import APIClient
from session_manager import session_manager

def load_accounts() -> List[AccountCredentials]:
    """Load account credentials from CSV file."""
    accounts = []
    try:
        with open(input_file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            logging.info(f"CSV fieldnames detected: {reader.fieldnames}")
            if 'username' not in reader.fieldnames or 'password' not in reader.fieldnames:
                logging.error(
                    f"Input CSV '{file_config.INPUT_CSV}' must contain "
                    "'username' and 'password' columns. Found fields: {reader.fieldnames}"
                )
                return accounts
                
            for row in reader:
                if row.get('username') and row.get('password'):
                    # Format username to ensure 8 digits with leading zeros
                    username = row['username'].strip()
                    if username.isdigit() and len(username) <= 8:
                        username = username.zfill(8)  # Add leading zeros if needed
                    accounts.append(AccountCredentials(
                        username=username,
                        password=row['password']
                    ))
                else:
                    logging.warning(f"Skipping row due to missing username or password: {row}")
                    
        logging.info(f"Read {len(accounts)} valid accounts from {file_config.INPUT_CSV}")
        return accounts
        
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file_path}")
        return accounts
    except Exception as e:
        logging.error(f"Error reading input CSV: {e}")
        return accounts

def extract_api_data(client: APIClient, account_data: AccountData, password: str) -> None:
    """Extract data from API endpoints."""
    username = account_data.username
    errors = []
    session_expired = False
    
    # Add delay between requests to avoid rate limiting
    request_delay = network_config.get_request_delay()

    # Optimized delay for maximum speed
    import time
    time.sleep(0.01)  # Extreme minimal delay for maximum speed
    logging.debug(f"[{username}] Pre-consumption API delay completed")

    # 1. Get Consumption (Balance, Secondary Numbers)
    consumption_resp = client.make_api_request(
        api_endpoints.get_consumption_url(),
        username,
        "Consumption",
        password=password
    )
    time.sleep(0.02)  # Extreme minimal delay for maximum speed
    
    # Check for session expiration
    if not consumption_resp.success and "session" in consumption_resp.error.lower():
        session_expired = True
        logging.warning(f"[{username}] Session expired during consumption API call")
    
    if consumption_resp.success and consumption_resp.data:
        try:
            # Parse balance (remove $ and spaces)
            balance_str = consumption_resp.data.get('CurrentBalanceValue', '').replace('$', '').strip()
            account_data.current_balance = float(balance_str) if balance_str else "API Error"
            
            # Extract secondary numbers and detailed consumption data from services
            secondary_numbers = set()
            secondary_consumptions = []
            services = consumption_resp.data.get('ServiceInformationValue', [])
            
            for service in services:
                service_name = service.get('ServiceNameValue', '')
                details = service.get('ServiceDetailsInformationValue', [])
                
                for detail in details:
                    # Extract main consumption data from any service (U-share Main or Mobile Internet)
                    if service_name in ['U-share Main', 'Mobile Internet']:
                        consumption_mb = detail.get('ConsumptionValue', '0')
                        package_gb = detail.get('PackageValue', '0')
                        description = detail.get('DescriptionValue', '')
                        
                        try:
                            consumption_gb = float(consumption_mb) / 1024 if consumption_mb else 0
                            # Set main consumption if not already set or if this is the primary service
                            if not hasattr(account_data, 'main_consumption') or account_data.main_consumption == "Not Found":
                                account_data.main_consumption = f"{consumption_gb:.2f} GB/{package_gb} GB"
                            # For Mobile Internet service, also set mobile_internet_consumption
                            if service_name == 'Mobile Internet' or description == 'Mobile Internet':
                                account_data.mobile_internet_consumption = f"{consumption_gb:.2f} GB/{package_gb} GB"
                        except (ValueError, TypeError):
                            if not hasattr(account_data, 'main_consumption') or account_data.main_consumption == "Not Found":
                                account_data.main_consumption = "API Error"
                    
                    # Handle secondary numbers from U-share service
                    if service_name == 'U-share Main':
                        secondaries = detail.get('SecondaryValue', [])
                        if secondaries:
                            for secondary in secondaries:
                                number = secondary.get('SecondaryNumberValue')
                                consumption_val = secondary.get('ConsumptionValue', '0')
                                quota_val = secondary.get('QuotaValue', '0')
                                consumption_unit = secondary.get('ConsumptionUnitValue', 'MB')
                                quota_unit = secondary.get('QuotaUnitValue', 'GB')
                                
                                try:
                                    # Convert consumption to GB if needed
                                    if consumption_unit == 'MB':
                                        consumption_gb = float(consumption_val) / 1024 if consumption_val else 0
                                    else:
                                        consumption_gb = float(consumption_val) if consumption_val else 0
                                    
                                    consumption_str = f"{consumption_gb:.2f} GB/{quota_val} {quota_unit}"
                                    
                                    # Handle Mobile Internet separately
                                    if number == 'Mobile Internet':
                                        account_data.mobile_internet_consumption = consumption_str
                                        logging.debug(f"[{username}] Found Mobile Internet consumption: {consumption_str}")
                                    # Handle regular secondary numbers (remove strict validation to capture all numbers)
                                    elif number and number != username:
                                        # Add all numbers that are not the main username
                                        secondary_numbers.add(number)
                                        secondary_consumptions.append(f"{number}: {consumption_str}")
                                        logging.debug(f"[{username}] Added secondary number: {number}")
                                except (ValueError, TypeError):
                                    if number == 'Mobile Internet':
                                        account_data.mobile_internet_consumption = "API Error"
                                    elif number and number != username:
                                        secondary_consumptions.append(f"{number}: API Error")
                                    
            account_data.secondary_numbers = ", ".join(sorted(secondary_numbers)) or "None"
            account_data.secondary_consumption = ", ".join(secondary_consumptions) or "None"
            
        except Exception as e:
            logging.error(f"[{username}] Error parsing Consumption API data: {e}")
            errors.append("Consumption API Parse Error")
            account_data.current_balance = "API Error"
            account_data.secondary_numbers = "API Error"
            account_data.main_consumption = "API Error"
            account_data.mobile_internet_consumption = "API Error"
            account_data.secondary_consumption = "API Error"
    else:
        errors.append("Consumption API Fetch Error")
        account_data.current_balance = "API Error"
        account_data.secondary_numbers = "API Error"
        account_data.main_consumption = "API Error"
        account_data.mobile_internet_consumption = "API Error"
        account_data.secondary_consumption = "API Error"

    # 2. Get Expiry Date
    expiry_resp = client.make_api_request(
        api_endpoints.EXPIRY,
        username,
        "Expiry Date",
        password=password
    )
    time.sleep(0.1)  # Optimized delay for speed
    
    # Check for session expiration
    if not expiry_resp.success and "session" in expiry_resp.error.lower():
        session_expired = True
        logging.warning(f"[{username}] Session expired during expiry API call")
    
    if expiry_resp.success and expiry_resp.data is not None:
        try:
            # Parse expiry date response
            expiry_data = expiry_resp.data
            if isinstance(expiry_data, (int, str)):
                # Direct days value
                days = str(expiry_data).split(' ')[0]
                account_data.validity_days_remaining = int(days) if days.isdigit() else "API Error"
            elif isinstance(expiry_data, dict):
                # Object with ExpiryDateValue
                days = str(expiry_data.get('ExpiryDateValue', '')).split(' ')[0]
                account_data.validity_days_remaining = int(days) if days.isdigit() else "API Error"
            else:
                account_data.validity_days_remaining = "API Error"
        except Exception as e:
            logging.error(f"[{username}] Error parsing Expiry API data: {e}")
            errors.append("Expiry API Parse Error")
            account_data.validity_days_remaining = "API Error"
    else:
        errors.append("Expiry API Fetch Error")
        account_data.validity_days_remaining = "API Error"

    # 3. Get Last Recharge
    recharge_resp = client.make_api_request(
        api_endpoints.LAST_RECHARGE,
        username,
        "Last Recharge",
        password=password
    )
    time.sleep(0.1)  # Optimized delay for speed
    
    # Check for session expiration
    if not recharge_resp.success and "session" in recharge_resp.error.lower():
        session_expired = True
        logging.warning(f"[{username}] Session expired during recharge API call")
    
    if recharge_resp.success and recharge_resp.data:
        try:
            # Handle numeric Amount field and date string
            amount = recharge_resp.data.get('Amount')
            account_data.last_recharge_amount = float(amount) if amount else "API Error"
            account_data.last_recharge_date = recharge_resp.data.get('Date', "API Error")
        except Exception as e:
            logging.error(f"[{username}] Error parsing Recharge API data: {e}")
            errors.append("Recharge API Parse Error")
            account_data.last_recharge_amount = "API Error"
            account_data.last_recharge_date = "API Error"
    else:
        errors.append("Recharge API Fetch Error")
        account_data.last_recharge_amount = "API Error"
        account_data.last_recharge_date = "API Error"

    # 4. Get Services (with additional headers for AJAX request)
    services_resp = client.make_api_request(
        api_endpoints.SERVICES,
        username,
        "My Services",
        password=password,
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/json'
        }
    )
    
    # Check for session expiration
    if not services_resp.success and "session" in services_resp.error.lower():
        session_expired = True
        logging.warning(f"[{username}] Session expired during services API call")
    
    if services_resp.success and services_resp.data:
        try:
            # Extract USHARE service details with main consumption package
            ushare_details = []
            
            if isinstance(services_resp.data, list):
                for service in services_resp.data:
                    # Skip if service is None or not a dictionary
                    if service is None or not isinstance(service, dict):
                        continue
                    service_name = service.get('Name', '')
                    
                    # Look for USHARE service
                    if service_name and 'ushare' in service_name.lower():
                        # Try to extract package size from ActiveBundle first
                        package_size = None
                        if 'ActiveBundle' in service:
                            bundle = service['ActiveBundle']
                            if bundle and isinstance(bundle, dict):
                                bundle_info = bundle.get('Service', {}).get('ServiceInfo', {})
                                if bundle_info:
                                    # Try to extract package size from various fields
                                    content_en = bundle_info.get('ContentEn', '')
                                    name_en = bundle_info.get('NameEn', '')
                                    description = bundle_info.get('Description', '')
                                    
                                    # Look for GB package size in the content
                                    import re
                                    for content in [content_en, name_en, description]:
                                        if content:
                                            gb_match = re.search(r'(\d+)\s*GB', content, re.IGNORECASE)
                                            if gb_match:
                                                package_size = gb_match.group(1)
                                                break
                        
                        # If no package size found in ActiveBundle, try to extract from main_consumption
                        if not package_size and hasattr(account_data, 'main_consumption') and account_data.main_consumption != "Not Found":
                            import re
                            consumption_match = re.search(r'/(\d+)\s*GB', account_data.main_consumption)
                            if consumption_match:
                                package_size = consumption_match.group(1)
                        
                        # Add USHARE with or without package size
                        if package_size:
                            ushare_details.append(f"USHARE: {package_size}GB")
                        else:
                            ushare_details.append("USHARE")
                            
            account_data.service_details = ", ".join(ushare_details) or "None"
                
        except Exception as e:
            logging.error(f"[{username}] Error parsing Services API data: {e}")
            errors.append("Services API Parse Error")
            account_data.service_details = "API Error"
    else:
        errors.append("Services API Fetch Error")
        account_data.service_details = "API Error"

    # Update error details if any errors occurred
    if errors:
        if account_data.error_details:
            account_data.error_details += ", " + ", ".join(errors)
        else:
            account_data.error_details = ", ".join(errors)
    
    # Invalidate session if session expiration was detected
    if session_expired:
        session_manager.invalidate_session(username)
        logging.info(f"[{username}] Session invalidated due to expiration during API calls")

def extract_manage_services_data(client: APIClient, account_data: AccountData) -> None:
    """Extract subscription and validity dates from manage-services page."""
    username = account_data.username
    
    try:
        # Navigate to manage-services page
        response = client.session.get(
            api_endpoints.MANAGE_SERVICES,
            headers=HTML_ACCEPT_HEADERS,
            timeout=network_config.REQUEST_TIMEOUT,
            verify=network_config.VERIFY_SSL
        )
        response.raise_for_status()
        
        # Save debug file for manage-services page
        save_debug_file(username, "manage_services_page.html", response.text)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract data from the specified CSS selector
        # body > div.container-fluid.bglightgrey.services > div:nth-child(3) > div > div > div:nth-child(3) > div > div.text-center.desc > div.links
        target_element = soup.select_one('body > div.container-fluid.bglightgrey.services > div:nth-child(3) > div > div > div:nth-child(3) > div > div.text-center.desc > div.links')
        
        if target_element:
            element_text = target_element.get_text(strip=True)
            logging.debug(f"[{username}] Found manage-services element text: {element_text}")
            
            # Extract subscription date and validity date using regex patterns
            import re
            
            # Look for subscription date pattern
            subscription_match = re.search(r'Subscription\s*date:\s*([\d/\-\.]+)', element_text, re.IGNORECASE)
            if subscription_match:
                account_data.subscription_date = subscription_match.group(1).strip()
                logging.info(f"[{username}] Found subscription date: {account_data.subscription_date}")
            
            # Look for validity date pattern
            validity_match = re.search(r'Validity\s*date:\s*([\d/\-\.]+)', element_text, re.IGNORECASE)
            if validity_match:
                account_data.validity_date = validity_match.group(1).strip()
                logging.info(f"[{username}] Found validity date: {account_data.validity_date}")
                
            # If no specific patterns found, try to extract any dates from the text
            if account_data.subscription_date == "Not Found" or account_data.validity_date == "Not Found":
                date_matches = re.findall(r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b', element_text)
                if len(date_matches) >= 2:
                    if account_data.subscription_date == "Not Found":
                        account_data.subscription_date = date_matches[0]
                    if account_data.validity_date == "Not Found":
                        account_data.validity_date = date_matches[1]
                elif len(date_matches) == 1:
                    if account_data.subscription_date == "Not Found":
                        account_data.subscription_date = date_matches[0]
        else:
            logging.warning(f"[{username}] Could not find manage-services target element")
            
    except Exception as e:
        logging.error(f"[{username}] Error extracting manage-services data: {e}")
        if account_data.error_details:
            account_data.error_details += ", Manage-Services Extraction Error"
        else:
            account_data.error_details = "Manage-Services Extraction Error"

def extract_html_data(client: APIClient, account_data: AccountData) -> None:
    """Extract data from HTML pages."""
    username = account_data.username
    
    try:
        # Get Account page HTML
        response = client.session.get(
            api_endpoints.ACCOUNT,
            headers=HTML_ACCEPT_HEADERS,
            timeout=network_config.REQUEST_TIMEOUT,
            verify=network_config.VERIFY_SSL
        )
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract activation date
        activation_date = extract_html_field(
            soup,
            "activation_date",
            "activation-date",
            pattern=r'(\d{2}/\d{2}/\d{4})'
        )
        if activation_date != "Not Found":
            account_data.activation_date = activation_date
            
    except Exception as e:
        logging.error(f"[{username}] Error extracting HTML data: {e}")
        if account_data.error_details:
            account_data.error_details += ", HTML Extraction Error"
        else:
            account_data.error_details = "HTML Extraction Error"
        
    # Extract manage-services data
    extract_manage_services_data(client, account_data)

async def process_account(credentials: AccountCredentials) -> AccountData:
    """Process a single account asynchronously."""
    account_data = AccountData(username=credentials.username)
    
    try:
        # Get or create session for this account
        client, is_new_session = session_manager.get_or_create_session(
            credentials.username, 
            credentials.password
        )
        
        if is_new_session:
            # Only add delay for new sessions
            import asyncio
            await asyncio.sleep(0.02)  # Minimal delay for new logins
            logging.debug(f"[{credentials.username}] Post-login delay completed for new session")
        else:
            logging.debug(f"[{credentials.username}] Reusing existing session, no delay needed")
            
        # Extract data from APIs and HTML
        extract_api_data(client, account_data, credentials.password)
        extract_html_data(client, account_data)
        
        # Determine final status
        if any(val == "API Error" or val == "Not Found" 
               for key, val in account_data.to_dict().items()
               if key not in ["error_details", "status", "username"]):
            account_data.status = "Partial Success"
            # Ensure error_details is set for partial success
            if not account_data.error_details:
                account_data.error_details = "Some data could not be retrieved"
        else:
            account_data.status = "Success"
            account_data.error_details = ""
            
    except Exception as e:
        logging.error(
            f"[{credentials.username}] Unhandled exception during processing: {e}",
            exc_info=True
        )
        account_data.status = "Error"
        account_data.error_details = f"Unhandled Exception: {str(e)}" if str(e) else "Unknown processing error occurred"
        
        # Invalidate session on error to force fresh login next time
        session_manager.invalidate_session(credentials.username)
        
    return account_data

def write_results(results: ProcessingResult) -> None:
    """Write results to CSV file."""
    try:
        with open(output_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=REQUIRED_FIELDS)
            writer.writeheader()
            
            # Sort results by username for consistent output
            sorted_results = sorted(results.results, key=lambda x: x.username)
            writer.writerows(result.to_dict() for result in sorted_results)
            
        logging.info(f"Results written to {file_config.OUTPUT_CSV}")
        print(f"Processing complete. Results saved to {file_config.OUTPUT_CSV}")
        
    except Exception as e:
        logging.error(f"Error writing results to CSV: {e}")
        print(f"Error writing results to CSV: {e}")

def main() -> None:
    """Main execution function."""
    setup_logging()
    accounts = load_accounts()
    
    if not accounts:
        logging.warning("No accounts found in the input file.")
        print("No accounts to process.")
        return
        
    results = ProcessingResult(total_accounts=len(accounts))
    
    with ThreadPoolExecutor(max_workers=network_config.get_max_workers()) as executor:
        future_to_account = {
            executor.submit(process_account, account): account
            for account in accounts
        }
        
        for future in as_completed(future_to_account):
            account = future_to_account[future]
            try:
                result = future.result()
                results.add_result(result)
            except Exception as e:
                logging.error(
                    f"[{account.username}] Error processing future: {e}",
                    exc_info=True
                )
                results.add_result(AccountData(
                    username=account.username,
                    status="Error",
                    error_details=f"Future execution failed: {str(e)}"
                ))
                
    results.complete()
    write_results(results)
    
    logging.info(
        f"Processing completed in {results.processing_time:.2f} seconds. "
        f"Success rate: {results.success_rate:.1f}%"
    )
    print(f"Log file saved to {file_config.LOG_FILE}")

if __name__ == "__main__":
    main()
