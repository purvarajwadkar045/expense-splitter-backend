from sqlalchemy.orm import Session
from app.services.balance_service import get_group_balances
from app.models.user import User

def simplify_debts(group_id: int, current_user: User, db: Session):
    # 1. Fetch group balances (this verifies group existence, handles membership authorization, and returns all members' balances)
    balances = get_group_balances(group_id, current_user, db)

    # 2. Separate into debtors and creditors
    debtors = []
    creditors = []

    for entry in balances:
        balance_val = round(entry["balance"], 2)
        if balance_val < 0:
            debtors.append({
                "user_id": entry["user_id"],
                "username": entry["username"],
                "amount": abs(balance_val)
            })
        elif balance_val > 0:
            creditors.append({
                "user_id": entry["user_id"],
                "username": entry["username"],
                "amount": balance_val
            })

    transactions = []

    # 3. Greedy algorithm matching the largest debtor with the largest creditor
    while debtors and creditors:
        # Keep lists sorted by amount descending to get the largest debtor and creditor
        debtors.sort(key=lambda x: x["amount"], reverse=True)
        creditors.sort(key=lambda x: x["amount"], reverse=True)

        debtor = debtors[0]
        creditor = creditors[0]

        # Calculate transaction amount
        min_amount = round(min(debtor["amount"], creditor["amount"]), 2)

        if min_amount > 0:
            transactions.append({
                "from_user_id": debtor["user_id"],
                "from_username": debtor["username"],
                "to_user_id": creditor["user_id"],
                "to_username": creditor["username"],
                "amount": min_amount
            })

        # Update remaining amounts
        debtor["amount"] = round(debtor["amount"] - min_amount, 2)
        creditor["amount"] = round(creditor["amount"] - min_amount, 2)

        # Remove from lists if fully settled
        if debtor["amount"] <= 0:
            debtors.pop(0)
        if creditor["amount"] <= 0:
            creditors.pop(0)

    return transactions
