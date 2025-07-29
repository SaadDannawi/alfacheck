from flask import Flask, render_template, request, jsonify, abort
from flask_cors import CORS
from sqlalchemy import true
from database import db_manager
from datetime import datetime
import logging
import os
from functools import lru_cache
import time

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory cache for transaction data
transaction_cache = {}
CACHE_TIMEOUT = 300  # 5 minutes

def get_cached_transaction_data(transaction_id):
    """Get cached transaction data if available and not expired."""
    if transaction_id in transaction_cache:
        cached_data, timestamp = transaction_cache[transaction_id]
        if time.time() - timestamp < CACHE_TIMEOUT:
            return cached_data
        else:
            # Remove expired cache
            del transaction_cache[transaction_id]
    return None

def cache_transaction_data(transaction_id, data):
    """Cache transaction data with timestamp."""
    transaction_cache[transaction_id] = (data, time.time())

def parse_validity_date(validity_date_str):
    """Parse validity date and calculate remaining days efficiently."""
    if not validity_date_str or validity_date_str == 'N/A':
        return None
    
    try:
        # Try multiple date formats
        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']
        for fmt in date_formats:
            try:
                validity_date = datetime.strptime(validity_date_str.split()[0], fmt)
                current_date = datetime.now()
                days_diff = (validity_date - current_date).days
                return max(0, days_diff)
            except ValueError:
                continue
        return None
    except Exception:
        return None

@app.route('/')
def index():
    """Dashboard home page."""
    return render_template('dashboard_home.html')

@app.route('/transaction/<transaction_id>')
def view_transaction(transaction_id):
    """View specific transaction results with caching for improved performance."""
    try:
        # Check cache first
        cached_data = get_cached_transaction_data(transaction_id)
        if cached_data:
            logger.info(f"Serving cached data for transaction {transaction_id}")
            return render_template('transaction_dashboard.html', 
                                 transaction=cached_data['transaction'], 
                                 results=cached_data['results'])
        
        # Get transaction from database
        transaction = db_manager.get_transaction(transaction_id)
        
        if not transaction:
            abort(404)
        
        # Mark dashboard as accessed
        db_manager.mark_dashboard_accessed(transaction_id)
        
        # Get account results for this transaction and prepare data within session
        with db_manager.get_session() as session:
            from database import AccountResult
            results = session.query(AccountResult).filter(
                AccountResult.transaction_id == transaction_id
            ).all()
            
            # Prepare results data within session to avoid DetachedInstanceError
            results_data = []
            for result in results:
                # Use number validity days (not service validity)
                # Prioritize validity_days_remaining (number validity) over validity_date (service validity)
                try:
                    if result.validity_days_remaining and str(result.validity_days_remaining).isdigit():
                        service_days_remaining = int(result.validity_days_remaining)
                    elif result.validity_days_remaining and result.validity_days_remaining != 'API Error':
                        service_days_remaining = result.validity_days_remaining
                    else:
                        # Only fallback to service validity if number validity is not available
                        service_days_remaining = parse_validity_date(result.validity_date)
                except:
                    service_days_remaining = result.validity_days_remaining
                
                # Ensure validity_days is always a proper value for display
                if service_days_remaining is None or service_days_remaining == 'N/A' or service_days_remaining == '':
                    validity_days_display = 'N/A'
                    validity_expiry_date = 'N/A'
                else:
                    try:
                        # Convert to integer if it's a valid number
                        validity_days_display = int(service_days_remaining)
                        # Calculate future date based on validity days
                        from datetime import timedelta
                        future_date = datetime.now() + timedelta(days=validity_days_display)
                        validity_expiry_date = future_date.strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        validity_days_display = service_days_remaining
                        validity_expiry_date = 'N/A'
                
                # Process mobile internet consumption to handle N/A cases
                mobile_internet = result.mobile_internet_consumption
                if not mobile_internet or mobile_internet in ['N/A', 'None', '']:
                    mobile_internet = '0 GB / 0 GB'
                
                results_data.append({
                    'username': result.account_username,
                    'status': result.status,
                    'activation_date': result.activation_date,
                    'validity_days': validity_days_display,
                    'validity_expiry_date': validity_expiry_date,
                    'balance': result.current_balance,
                    'last_recharge': result.last_recharge_amount,
                    'last_recharge_date': result.last_recharge_date,
                    'service_details': result.service_details,
                    'secondary_numbers': result.secondary_numbers,
                    'main_consumption': result.main_consumption,
                    'mobile_internet': mobile_internet,  # Fixed mapping and N/A handling
                    'secondary_consumption': result.secondary_consumption,
                    'subscription_date': result.subscription_date,
                    'validity_date': result.validity_date,
                    'error_details': result.error_details
                })
        
        # Prepare transaction data
        transaction_data = {
            'transaction_id': transaction.transaction_id,
            'created_at': transaction.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'started_at': transaction.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if transaction.started_at else 'N/A',
            'completed_at': transaction.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if transaction.completed_at else 'N/A',
            'status': transaction.status,
            'total_numbers': transaction.total_numbers,
            'successful_numbers': transaction.successful_numbers or 0,
            'failed_numbers': transaction.failed_numbers or 0,
            'processing_time': f"{transaction.processing_time_seconds:.2f}s" if transaction.processing_time_seconds else 'N/A',
            'error_message': transaction.error_message
        }
        
        # Cache the data for future requests
        cache_data = {
            'transaction': transaction_data,
            'results': results_data
        }
        cache_transaction_data(transaction_id, cache_data)
        logger.info(f"Cached data for transaction {transaction_id}")
        
        return render_template('transaction_dashboard.html', 
                             transaction=transaction_data, 
                             results=results_data)
    
    except Exception as e:
        logger.error(f"Error viewing transaction {transaction_id}: {str(e)}")
        abort(500)

@app.route('/api/transaction/<transaction_id>')
def api_transaction(transaction_id):
    """API endpoint for transaction data."""
    try:
        transaction = db_manager.get_transaction(transaction_id)
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Get account results and count within session
        with db_manager.get_session() as session:
            from database import AccountResult
            results = session.query(AccountResult).filter(
                AccountResult.transaction_id == transaction_id
            ).all()
            results_count = len(results)
        
        return jsonify({
            'transaction': {
                'id': transaction.transaction_id,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat(),
                'total_numbers': transaction.total_numbers,
                'successful_numbers': transaction.successful_numbers or 0,
                'failed_numbers': transaction.failed_numbers or 0
            },
            'results_count': results_count
        })
    
    except Exception as e:
        logger.error(f"API error for transaction {transaction_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/sw.js')
def service_worker():
    """Service worker file - return empty response to prevent 404."""
    return '', 204

@app.route('/@vite/client')
def vite_client():
    """Vite client file - return empty response to prevent 404."""
    return '', 204

@app.route('/favicon.ico')
def favicon():
    """Favicon - return empty response to prevent 404."""
    return '', 204

@app.route('/api/transactions/<transaction_id>')
def get_transaction_api(transaction_id):
    """API endpoint to get transaction data."""
    try:
        # Get transaction data from database
        transaction_data = db_manager.get_transaction_results(transaction_id)
        
        if not transaction_data:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Convert datetime objects to strings for JSON serialization
        for result in transaction_data.get('results', []):
            for key, value in result.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
        
        return jsonify(transaction_data)
    
    except Exception as e:
        logger.error(f"Error getting transaction data: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/customer/<customer_page_id>')
def customer_page(customer_page_id):
    """Customer-specific page showing all their results."""
    try:
        # Validate customer page ID and get user
        user_id = db_manager.get_customer_page_user(customer_page_id)
        if not user_id:
            return render_template('error.html', 
                                 error_message="Customer page not found",
                                 error_code=404), 404
        
        # Update last access time
        db_manager.update_customer_page_access(user_id)
        
        # Get customer statistics
        customer_stats = db_manager.get_customer_stats(user_id)
        
        return render_template('customer_page.html', 
                             customer_page_id=customer_page_id,
                             customer_stats=customer_stats)
    
    except Exception as e:
        logger.error(f"Error loading customer page {customer_page_id}: {e}")
        return render_template('error.html', 
                             error_message="Error loading customer page",
                             error_code=500), 500

@app.route('/api/customer/<customer_page_id>/results')
def get_customer_results_api(customer_page_id):
    """API endpoint to get all results for a customer."""
    try:
        # Validate customer page ID and get user
        user_id = db_manager.get_customer_page_user(customer_page_id)
        if not user_id:
            return jsonify({'error': 'Customer page not found'}), 404
        
        # Get limit from query parameters
        limit = request.args.get('limit', 1000, type=int)
        
        # Get customer results
        results = db_manager.get_customer_results(user_id, limit)
        
        # Convert datetime objects to strings for JSON serialization
        for result in results:
            for key, value in result.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
        
        return jsonify({
            'customer_page_id': customer_page_id,
            'total_results': len(results),
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Error getting customer results for {customer_page_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/customer/<customer_page_id>/stats')
def get_customer_stats_api(customer_page_id):
    """API endpoint to get customer statistics."""
    try:
        # Validate customer page ID and get user
        user_id = db_manager.get_customer_page_user(customer_page_id)
        if not user_id:
            return jsonify({'error': 'Customer page not found'}), 404
        
        # Get customer statistics
        stats = db_manager.get_customer_stats(user_id)
        
        # Convert datetime objects to strings for JSON serialization
        for key, value in stats.items():
            if isinstance(value, datetime):
                stats[key] = value.isoformat()
        
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"Error getting customer stats for {customer_page_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/customer/<customer_page_id>/refresh/<account_number>', methods=['POST'])
def refresh_account_api(customer_page_id, account_number):
    """API endpoint to refresh a specific account number."""
    try:
        # Validate customer page ID and get user
        user_id = db_manager.get_customer_page_user(customer_page_id)
        if not user_id:
            return jsonify({'error': 'Customer page not found'}), 404
        
        # Import required modules for processing
        import asyncio
        import uuid
        from models import AccountCredentials
        from scraper import process_account
        
        # Get the user's default password
        password = db_manager.get_user_default_password(user_id)
        if not password:
            return jsonify({'error': 'No default password set for this user'}), 400
        
        # Verify the account exists in user's history
        with db_manager.get_session() as session:
            from database import Transaction, AccountResult
            recent_result = session.query(AccountResult).join(Transaction).filter(
                Transaction.user_id == user_id,
                AccountResult.account_username == account_number
            ).order_by(Transaction.created_at.desc()).first()
            
            if not recent_result:
                return jsonify({'error': 'Account not found in your history'}), 404
        
        # Create account credentials
        account_creds = AccountCredentials(username=account_number, password=password)
        
        # Process the account asynchronously
        async def process_single_account():
            try:
                result = await process_account(account_creds)
                
                # Generate a new transaction ID for this refresh
                transaction_id = str(uuid.uuid4())
                
                # Create a new transaction record
                db_manager.create_transaction(user_id, transaction_id, 1)
                db_manager.start_transaction(transaction_id)
                
                # Create a processing request
                request_id = db_manager.start_processing_request(
                    user_id=user_id,
                    total_accounts=1,
                    processing_mode='refresh'
                )
                
                # Save the result
                db_manager.save_account_result(request_id, result)
                db_manager.save_transaction_result(transaction_id, result, request_id)
                
                # Complete the transaction
                db_manager.complete_transaction(
                    transaction_id=transaction_id,
                    successful_numbers=1 if result.status == 'Success' else 0,
                    failed_numbers=0 if result.status == 'Success' else 1,
                    processing_time=1.0
                )
                
                # Complete the processing request
                db_manager.complete_processing_request(
                    request_id=request_id,
                    successful=1 if result.status == 'Success' else 0,
                    partial=0,
                    failed=0 if result.status == 'Success' else 1
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Error refreshing account {account_number}: {e}")
                return None
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(process_single_account())
        finally:
            loop.close()
        
        if result:
            # Convert result to dict for JSON response
            result_dict = {
                'account_username': result.username,
                'status': result.status,
                'current_balance': result.current_balance,
                'validity_days_remaining': result.validity_days_remaining,
                'activation_date': result.activation_date,
                'last_recharge_amount': result.last_recharge_amount,
                'last_recharge_date': result.last_recharge_date,
                'service_details': result.service_details,
                'subscription_date': result.subscription_date,
                'validity_date': result.validity_date,
                'secondary_numbers': result.secondary_numbers,
                'main_consumption': result.main_consumption,
                'mobile_internet_consumption': result.mobile_internet_consumption,
                'secondary_consumption': result.secondary_consumption,
                'error_details': result.error_details
            }
            
            return jsonify({
                'success': True,
                'message': f'Account {account_number} refreshed successfully',
                'result': result_dict
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to refresh account {account_number}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error refreshing account {account_number} for customer {customer_page_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/customer/<customer_page_id>/auto-login/<account_number>', methods=['POST'])
def auto_login_api(customer_page_id, account_number):
    """API endpoint to generate auto-login URL for Alfa website."""
    try:
        # Validate customer page ID and get user
        user_id = db_manager.get_customer_page_user(customer_page_id)
        if not user_id:
            return jsonify({'error': 'Customer page not found'}), 404
        
        # Get the user's default password
        password = db_manager.get_user_default_password(user_id)
        if not password:
            return jsonify({'error': 'No default password set for this user'}), 400
        
        # Verify the account exists in user's history
        with db_manager.get_session() as session:
            from database import Transaction, AccountResult
            recent_result = session.query(AccountResult).join(Transaction).filter(
                Transaction.user_id == user_id,
                AccountResult.account_username == account_number
            ).order_by(Transaction.created_at.desc()).first()
            
            if not recent_result:
                return jsonify({'error': 'Account not found in your history'}), 404
        
        # Generate auto-login URL for Alfa website
        # This is a placeholder - you would need to implement the actual auto-login mechanism
        # based on how Alfa's authentication system works
        base_url = "https://www.alfa.com.lb/en/account/login"
        
        # For now, we'll return the base login URL
        # In a real implementation, you might need to:
        # 1. Create a temporary token
        # 2. Use OAuth or similar authentication flow
        # 3. Generate a pre-authenticated URL
        
        return jsonify({
            'success': True,
            'login_url': base_url,
            'account_number': account_number,
            'message': f'Auto-login URL generated for account {account_number}'
        })
    
    except Exception as e:
        logger.error(f"Error generating auto-login for account {account_number}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/customer/<customer_page_id>/delete/<account_number>', methods=['DELETE'])
def delete_account_api(customer_page_id, account_number):
    """API endpoint to delete an account from user's history."""
    try:
        # Validate customer page ID and get user
        user_id = db_manager.get_customer_page_user(customer_page_id)
        if not user_id:
            return jsonify({'error': 'Customer page not found'}), 404
        
        # Delete account results from user's history
        with db_manager.get_session() as session:
            from database import Transaction, AccountResult
            
            # Find all account results for this user and account number
            account_results = session.query(AccountResult).join(Transaction).filter(
                Transaction.user_id == user_id,
                AccountResult.account_username == account_number
            ).all()
            
            if not account_results:
                return jsonify({'error': 'Account not found in your history'}), 404
            
            # Delete all account results
            deleted_count = 0
            for result in account_results:
                session.delete(result)
                deleted_count += 1
            
            session.commit()
            
            logger.info(f"Deleted {deleted_count} records for account {account_number} (user {user_id})")
            
            return jsonify({
                'success': True,
                'message': f'Account {account_number} deleted successfully',
                'deleted_records': deleted_count
            })
    
    except Exception as e:
        logger.error(f"Error deleting account {account_number} for customer {customer_page_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_code=404, 
                         error_message='Transaction not found'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', 
                         error_code=500, 
                         error_message='Internal server error'), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)