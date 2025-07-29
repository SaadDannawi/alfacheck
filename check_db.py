from database import db_manager
from database import AccountResult, Transaction

with db_manager.get_session() as session:
    # Count total records
    total_results = session.query(AccountResult).count()
    total_transactions = session.query(Transaction).count()
    
    print(f"Total AccountResults: {total_results}")
    print(f"Total Transactions: {total_transactions}")
    
    # Get sample results
    results = session.query(AccountResult).limit(5).all()
    print("\nSample AccountResults:")
    for r in results:
        error_preview = r.error_details[:50] if r.error_details else "None"
        print(f"ID: {r.id}, Username: {r.account_username}, Status: {r.status}, Error: {error_preview}")
    
    # Check if there are results with transactions
    results_with_trans = session.query(AccountResult).join(Transaction).limit(5).all()
    print(f"\nAccountResults with Transactions: {len(results_with_trans)}")
    
    # Check for results without transaction_id
    results_no_trans = session.query(AccountResult).filter(AccountResult.transaction_id.is_(None)).count()
    print(f"AccountResults without transaction_id: {results_no_trans}")
    
    # Check recent transactions
    recent_trans = session.query(Transaction).order_by(Transaction.created_at.desc()).limit(3).all()
    print("\nRecent Transactions:")
    for t in recent_trans:
        print(f"ID: {t.transaction_id}, User: {t.user_id}, Status: {t.status}, Numbers: {t.total_numbers}")