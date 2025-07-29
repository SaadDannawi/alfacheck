from database import db_manager
from database import User, AccountResult, Transaction

with db_manager.get_session() as session:
    # Get all users with customer pages
    users = session.query(User).filter(User.customer_page_id.isnot(None)).all()
    print(f"Users with customer pages: {len(users)}")
    
    for user in users:
        print(f"\nUser ID: {user.user_id}, Customer Page: {user.customer_page_id}")
        
        # Test get_customer_results for this user
        results = db_manager.get_customer_results(user.user_id, 10)
        print(f"Customer results count: {len(results)}")
        
        if results:
            print("Sample result:")
            result = results[0]
            print(f"  Username: {result['account_username']}")
            print(f"  Status: {result['status']}")
            print(f"  Error details: {result['error_details']}")
            print(f"  Transaction ID: {result['transaction_id']}")
            print(f"  Activation date: {result['activation_date']}")
            print(f"  Current balance: {result['current_balance']}")
        else:
            print("  No results found")
            
            # Check raw data for this user
            raw_results = session.query(AccountResult).join(Transaction).filter(
                Transaction.user_id == user.user_id
            ).all()
            print(f"  Raw AccountResults with transactions: {len(raw_results)}")
            
            # Check AccountResults without transactions
            all_results = session.query(AccountResult).all()
            print(f"  All AccountResults in DB: {len(all_results)}")