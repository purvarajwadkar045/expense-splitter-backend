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
    
    from app.services.activity_service import log_activity
    log_activity(db, group.id, current_user.id, "GROUP_CREATED", f"{current_user.username} created group '{group.name}'")
    
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

    from app.services.activity_service import log_activity
    log_activity(db, group.id, current_user.id, "MEMBER_ADDED", f"{current_user.username} added {user.username} to the group")

    from app.services.notification_service import create_notification
    create_notification(
        db,
        user_id=user.id,
        title="Added to Group",
        message=f"You have been added to the group '{group.name}' by {current_user.username}."
    )

    return {"message": "Member added"}


def get_user_groups(current_user, db):
    # Query all groups where the user is a member
    memberships = db.query(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    groups_list = []
    for m in memberships:
        group = m.group
        # Get members usernames
        group_members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
        members_usernames = []
        for gm in group_members:
            if gm.user_id == current_user.id:
                members_usernames.append("You")
            else:
                members_usernames.append(gm.user.username)
        
        groups_list.append({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "created_by": group.created_by,
            "created_at": group.created_at,
            "members": members_usernames
        })
    return groups_list


def get_group_by_id(group_id, current_user, db):
    # Verify group exists and current user is a member
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Group not found or access denied")
    
    group = membership.group
    group_members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    members_usernames = []
    for gm in group_members:
        if gm.user_id == current_user.id:
            members_usernames.append("You")
        else:
            members_usernames.append(gm.user.username)
            
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "members": members_usernames
    }


def update_group(group_id, group_data, current_user, db):
    group = check_group_creator(db, group_id, current_user.id, detail="Only creator can modify this group")
    if group_data.name:
        group.name = group_data.name
    if group_data.description is not None:
        group.description = group_data.description
        
    db.commit()
    db.refresh(group)
    
    from app.services.activity_service import log_activity
    log_activity(db, group.id, current_user.id, "GROUP_UPDATED", f"{current_user.username} updated group details")
    
    return group


def delete_group(group_id, current_user, db):
    group = check_group_creator(db, group_id, current_user.id, detail="Only creator can delete this group")
    db.delete(group)
    db.commit()
    return {"message": "Group deleted successfully"}