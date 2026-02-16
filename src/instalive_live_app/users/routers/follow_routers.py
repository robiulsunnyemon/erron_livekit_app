from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from instalive_live_app.users.utils.get_current_user import get_current_user
from instalive_live_app.users.models.user_models import UserModel
from typing import List
from instalive_live_app.notifications.utils import send_notification
from instalive_live_app.notifications.models import NotificationType

router = APIRouter(
    prefix="/social",
    tags=["Social & Connections"]
)


def get_link_id(link):
    """Helper to get ID from a Beanie Link (fetched or unfetched)"""
    if hasattr(link, "ref"):
        return str(link.ref.id)
    return str(link.id)


@router.post("/follow/{target_id}")
async def follow_user(target_id: str, current_user: UserModel = Depends(get_current_user)):
    try:
        target_oid = UUID(target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid User ID format")

    if target_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="You cannot follow yourself")

    target_user = await UserModel.get(target_oid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Correct way to check Beanie Link
    is_already_following = any(get_link_id(link) == str(target_oid) for link in current_user.following)

    if is_already_following:
        print(f"User {current_user.id} is already following {target_oid}")
        return {"message": "Already following this user"}

    current_user.following.append(target_user)
    current_user.following_count += 1
    target_user.followers_count += 1

    await current_user.save()
    await target_user.save()

    # Send Notification to Target User
    await send_notification(
        user=target_user,
        title="New Follower",
        body=f"{current_user.first_name} {current_user.last_name or ''} started following you.",
        type=NotificationType.SOCIAL,
        related_entity_id=str(current_user.id)
    )

    return {"message": "Followed successfully"}


@router.post("/unfollow/{target_id}")
async def unfollow_user(target_id: str, current_user: UserModel = Depends(get_current_user)):
    try:
        target_oid = UUID(target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid User ID format")

    target_user_in_list = None
    for link in current_user.following:
        if get_link_id(link) == str(target_oid):
            target_user_in_list = link
            break

    if not target_user_in_list:
        print(f"User {current_user.id} not following {target_oid}, current list: {[str(l.ref.id) for l in current_user.following]}")
        raise HTTPException(status_code=400, detail="You are not following this user")

    target_user = await UserModel.get(target_oid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_user.following.remove(target_user_in_list)
    current_user.following_count = max(0, current_user.following_count - 1)
    target_user.followers_count = max(0, target_user.followers_count - 1)

    await current_user.save()
    await target_user.save()

    return {"status": "success", "message": f"Unfollowed {target_user.first_name}"}


@router.get("/me/following-list")
async def get_my_following(current_user: UserModel = Depends(get_current_user)):
    # fetch_links=True brings related data directly
    user = await UserModel.find_one(UserModel.id == current_user.id, fetch_links=True)
    return user.following


@router.get("/active-priority-list")
async def get_active_priority_list(current_user: UserModel = Depends(get_current_user)):
    """
    Original requirement: Online list with followed user (User B) at the top
    """
    # 1. Get online users
    online_users = await UserModel.find(UserModel.is_online == True).to_list()

    # 2. Create a set of following IDs for the current user (for fast searching)
    following_ids = {get_link_id(link) for link in current_user.following}

    # 3. Sorting: Followed users (User B) will be at the top of the list
    online_users.sort(key=lambda u: str(u.id) in following_ids, reverse=True)

    return online_users


@router.get("/me/followers-list")
async def get_my_followers(current_user: UserModel = Depends(get_current_user)):
    """
    Get the list of users who are following you.
    Logic: Find users who have your ID in their 'following' list.
    """
    followers = await UserModel.find(
        UserModel.following.id == current_user.id
    ).to_list()

    return followers


@router.get("/me/counts")
async def get_social_counts(current_user: UserModel = Depends(get_current_user)):
    """
    To see your own follower and following counts.
    """
    return {
        "follower_count": current_user.followers_count,
        "following_count": current_user.following_count
    }


# You can also view the count for a specific user using their ID
@router.get("/{user_id}/stats")
async def get_user_stats(user_id: str):
    try:
        user_oid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid User ID format")

    user = await UserModel.get(user_oid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "username": f"{user.first_name} {user.last_name}",
        "follower_count": user.followers_count,
        "following_count": user.following_count
    }


@router.get("/is-following/{target_id}")
async def check_following_status(target_id: str, current_user: UserModel = Depends(get_current_user)):
    try:
        target_oid = UUID(target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid User ID format")

    is_following = any(get_link_id(link) == str(target_oid) for link in current_user.following)
    print(f"Check Follow: User {current_user.id} following {target_id}? {is_following}")
    return {"is_following": is_following}
