from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.group import Group
from app.models.group_member import GroupMember

def check_group_membership(db: Session, group_id: int, user_id: int) -> Group:
    """
    Verifies that the group exists and the user is a member of the group.
    Raises HTTP 404 if the group is not found.
    Raises HTTP 403 if the user is not a member of the group.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
        
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="User is not a member of this group")
        
    return group

def check_group_creator(db: Session, group_id: int, user_id: int, detail: str = "Only creator can perform this action") -> Group:
    """
    Verifies that the group exists and the user is the creator of the group.
    Raises HTTP 404 if the group is not found.
    Raises HTTP 403 if the user is not the group creator.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
        
    if group.created_by != user_id:
        raise HTTPException(status_code=403, detail=detail)
        
    return group
