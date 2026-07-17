from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.settlement import Settlement
from app.models.group_member import GroupMember
from app.schemas.settlement import SettlementCreate
from app.models.user import User
from app.services.authorization import check_group_membership

def create_settlement(group_id: int, settlement_data: SettlementCreate, current_user: User, db: Session) -> Settlement:
    # 1. Verify group exists and current_user is a member
    check_group_membership(db, group_id, current_user.id)

    # 2. Amount must be greater than zero
    if settlement_data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    # 3. Verify payer is a member of the group
    is_payer_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == settlement_data.payer_id
    ).first()
    if not is_payer_member:
        raise HTTPException(status_code=403, detail="Payer is not a member of this group")

    # 4. Verify receiver is a member of the group
    is_receiver_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == settlement_data.receiver_id
    ).first()
    if not is_receiver_member:
        raise HTTPException(status_code=403, detail="Receiver is not a member of this group")

    # 5. Create Settlement
    settlement = Settlement(
        group_id=group_id,
        payer_id=settlement_data.payer_id,
        receiver_id=settlement_data.receiver_id,
        amount=settlement_data.amount
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    payer = db.query(User).filter(User.id == settlement.payer_id).first()
    receiver = db.query(User).filter(User.id == settlement.receiver_id).first()
    payer_username = payer.username if payer else "Unknown"
    receiver_username = receiver.username if receiver else "Unknown"

    from app.services.activity_service import log_activity
    amount_str = f"₹{int(settlement.amount)}" if settlement.amount.is_integer() else f"₹{settlement.amount:.2f}"
    log_activity(db, group_id, current_user.id, "SETTLEMENT_CREATED", f"{payer_username} paid {receiver_username} {amount_str}")

    return settlement

def get_settlement_history(group_id: int, current_user: User, db: Session):
    # Verify group exists and current_user is a member
    check_group_membership(db, group_id, current_user.id)

    return db.query(Settlement).filter(
        Settlement.group_id == group_id
    ).order_by(Settlement.settled_at.desc()).all()
