from fastapi import HTTPException

from app.models.user import User
from app.models.group import Group
from app.models.group_member import GroupMember
from app.services.authorization import check_group_creator

def create_group(group_data, current_user, db):
    group = Group(
        name=group_data.name,
        description=group_data.description,
        created_by=current_user.id
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    
    # Automatically add creator as a member of the group
    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        is_admin=True
    )
    db.add(member)
    db.commit()
    db.refresh(group)
    
    return group


def add_member(
    group_id,
    email,
    current_user,
    db
):

    group = check_group_creator(db, group_id, current_user.id, detail="Only creator can add members")

    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group.id,
        GroupMember.user_id == user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="User already in group"
        )

    member = GroupMember(
        group_id=group.id,
        user_id=user.id
    )

    db.add(member)
    db.commit()

    return {"message": "Member added"}