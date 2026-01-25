
from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile
from uuid import UUID
import shutil
import os
from pathlib import Path
from typing import List
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.schemas.user_schemas import UserResponse, ProfileResponse, ModeratorProfileResponse, ProfileUpdateRequest, KYCResponse, ModeratorResponse, PendingKYCStatsResponse, KYCUpdate
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.streaming.models.streaming import LiveStreamModel
from erron_live_app.users.models.kyc_models import KYCModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.users.utils.populate_kyc import populate_user_kyc
from typing import Union
from datetime import datetime
from erron_live_app.users.utils.user_role import UserRole

# Define the router for User Management
user_router = APIRouter(prefix="/users", tags=["Users"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB

@user_router.get("/", response_model=List[UserResponse], status_code=status.HTTP_200_OK)
async def get_all_users(skip: int = 0, limit: int = 20):
    """
    Retrieve a list of all users with pagination.

    - **skip**: Number of records to skip (default is 0)
    - **limit**: Maximum number of records to return (default is 20)
    """
    # Fetch users sorted by creation date (newest first)
    users = await UserModel.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
    
    # Populate KYC data for each user
    users_with_kyc = []
    for user in users:
        user_data = await populate_user_kyc(user)
        users_with_kyc.append(user_data)
    
    return users_with_kyc


@user_router.get("/search", response_model=List[UserResponse], status_code=status.HTTP_200_OK)
async def search_users(query: str, skip: int = 0, limit: int = 20):
    """
    Search users by name or email.
    """
    search_filter = {
        "$or": [
            {"first_name": {"$regex": query, "$options": "i"}},
            {"last_name": {"$regex": query, "$options": "i"}},
            {"email": {"$regex": query, "$options": "i"}}
        ]
    }
    users = await UserModel.find(search_filter).skip(skip).limit(limit).to_list()
    
    # Populate KYC data for each user
    users_with_kyc = []
    for user in users:
        user_data = await populate_user_kyc(user)
        users_with_kyc.append(user_data)
    
    return users_with_kyc


@user_router.get("/my_profile", response_model=Union[ProfileResponse, ModeratorProfileResponse])
async def my_profile(current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)):
    if isinstance(current_user, ModeratorModel):
        return current_user

    # Fetch all past streams by this user (including ones with status 'ended' or similar)
    past_streams = await LiveStreamModel.find(LiveStreamModel.host.id == current_user.id).sort("-created_at").to_list()
    
    # Populate KYC data for the user
    user_data = await populate_user_kyc(current_user)
    
    # We return a dict that matches ProfileResponse for regular users
    return {
        **user_data,
        "past_streams": past_streams
    }


@user_router.patch("/my_profile/update", response_model=UserResponse)
async def update_my_profile(
    data: ProfileUpdateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update the current user's profile information.
    """
    if not isinstance(current_user, UserModel):
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only regular users can update their profile here")

    update_dict = data.model_dump(exclude_unset=True)
    
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    # Update user object
    for key, value in update_dict.items():
        setattr(current_user, key, value)
    
    await current_user.save()
    return current_user


@user_router.post("/my_profile/upload-profile-image", status_code=status.HTTP_200_OK)
async def upload_profile_image(
    image: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Upload a profile image and return the URL.
    """


    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG or WEBP images are allowed",
        )

        # Size validation
    contents = await image.read()

    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image size must be under 5MB",
        )

    extension = Path(image.filename).suffix

    profile_dir = os.path.join("uploads", "profiles")
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    filename = f"profile{current_user.id}{datetime.now().timestamp()}{extension}"
    file_path = os.path.join(profile_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    image_url = f"/uploads/profiles/{filename}"
    
    # Update user profile
    current_user.profile_image = image_url
    await current_user.save()
    
    return {"image_url": image_url}


@user_router.post("/my_profile/upload/cover-image", status_code=status.HTTP_200_OK)
async def upload_cover_image(
    image: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Upload a cover image and return the URL.
    """

    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG or WEBP images are allowed",
        )

        # Size validation
    contents = await image.read()

    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image size must be under 5MB",
        )

    extension = Path(image.filename).suffix

    cover_dir = os.path.join("uploads", "covers")
    if not os.path.exists(cover_dir):
        os.makedirs(cover_dir)

    filename = f"cover{current_user.id}{datetime.now().timestamp()}{extension}"
    file_path = os.path.join(cover_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    image_url = f"/uploads/covers/{filename}"
    
    # Update user profile
    current_user.cover_image = image_url
    await current_user.save()

    return {"image_url": image_url}


@user_router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(user_id: str):
    """
    Get detailed information about a specific user by their unique ID.
    """
    # Search for the user in the database by ID
    user = await UserModel.get(user_id)

    # Check if user exists; if not, raise a 404 error
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Populate KYC data
    user_data = await populate_user_kyc(user)
    return user_data


@user_router.post("/kyc/submit", status_code=status.HTTP_201_CREATED)
async def kyc_submit(
    id_front: UploadFile = File(...),
    id_back: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):


    # Robust check for id_front
    is_front_valid = id_front.content_type in ALLOWED_TYPES
    if not is_front_valid and id_front.content_type == "application/octet-stream":
        if Path(id_front.filename).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
             is_front_valid = True

    if not is_front_valid:
        raise HTTPException(
            status_code=400,
            detail="ID Front: Only JPG, PNG or WEBP images are allowed",
        )

    # Robust check for id_back
    is_back_valid = id_back.content_type in ALLOWED_TYPES
    if not is_back_valid and id_back.content_type == "application/octet-stream":
        if Path(id_back.filename).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
             is_back_valid = True

    if not is_back_valid:
        raise HTTPException(
            status_code=400,
            detail="ID Back: Only JPG, PNG or WEBP images are allowed",
        )

        # Size validation
    contents_id_font = await id_front.read()

    if len(contents_id_font) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image size must be under 5MB",
        )

    extension_id_front = Path(id_front.filename).suffix



    if id_back.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG or WEBP images are allowed",
        )

        # Size validation
    contents_id_back = await id_back.read()

    if len(contents_id_back) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image size must be under 5MB",
        )

    extension_id_back = Path(contents_id_back.filename).suffix




    # Create KYC directory if not exists
    kyc_dir = os.path.join("uploads", "kyc")
    if not os.path.exists(kyc_dir):
        os.makedirs(kyc_dir)

    # Save Front ID
    front_filename = f"front{current_user.id}{datetime.now().timestamp()}{extension_id_front}"
    front_path = os.path.join(kyc_dir, front_filename)
    with open(front_path, "wb") as buffer:
        shutil.copyfileobj(id_front.file, buffer)

    # Save Back ID
    back_filename = f"back{current_user.id}{datetime.now().timestamp()}{extension_id_back}"
    back_path = os.path.join(kyc_dir, back_filename)
    with open(back_path, "wb") as buffer:
        shutil.copyfileobj(id_back.file, buffer)

    # Create model entry
    # Note: Using absolute URL or relative web path. Frontend likely needs web path.
    front_url = f"/uploads/kyc/{front_filename}"
    back_url = f"/uploads/kyc/{back_filename}"

    # Check if a KYC already exists for this user
    existing_kyc = await KYCModel.find_one(KYCModel.user.id == current_user.id)
    if existing_kyc:
        existing_kyc.id_front = front_url
        existing_kyc.id_back = back_url
        existing_kyc.status = "pending"
        await existing_kyc.save()
        return {"message": "KYC updated successfully", "status": "pending"}
    
    new_kyc = KYCModel(
        user=current_user.to_ref(),
        id_front=front_url,
        id_back=back_url
    )
    await new_kyc.insert()

    return {"message": "KYC submitted successfully", "status": "pending"}


@user_router.get("/kyc/view", response_model=Union[KYCResponse, dict], status_code=status.HTTP_200_OK)
async def kyc_status(current_user: UserModel = Depends(get_current_user)):
    kyc = await KYCModel.find_one(KYCModel.user.id == current_user.id,fetch_links=True)
    if not kyc:
        return {"status": "none"}
    return kyc


@user_router.get("/kyc/{user_id}", response_model=KYCResponse, status_code=status.HTTP_200_OK)
async def get_kyc_by_user_id(user_id: UUID):
    kyc = await KYCModel.find_one(KYCModel.user.id == user_id, fetch_links=True)
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC not found for this user")
    return kyc


@user_router.get("/kyc/stats/pending", response_model=PendingKYCStatsResponse, status_code=status.HTTP_200_OK)
async def get_pending_kyc_stats():
    """
    Get statistics for pending KYC requests.
    Returns total count of pending KYC verifications.
    """
    total = await KYCModel.find(KYCModel.status == "pending").count()
    
    return {
        "total": total
    }


# @user_router.patch("/kyc-verifications/{kyc_id}", response_model=KYCResponse, status_code=status.HTTP_200_OK)
# async def update_kyc_status(
#     kyc_id: UUID,
#     data: KYCUpdate,
#     current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
# ):
#     """
#     Update KYC status. Only Admin or Moderators can perform this action.
#     """
#     # Permission Check
#     is_admin = isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN
#     is_mod = isinstance(current_user, ModeratorModel)
#
#     if not is_admin and not is_mod:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
#
#     kyc = await KYCModel.get(kyc_id, fetch_links=True)
#     if not kyc:
#         raise HTTPException(status_code=404, detail="KYC request not found")
#
#     kyc.status = data.status
#     if data.rejection_reason:
#         kyc.rejection_reason = data.rejection_reason
#
#     await kyc.save()
#
#     # Update User Verification Status
#     if kyc.user:
#         user = kyc.user
#         if hasattr(user, "fetch"):
#              user = await user.fetch()
#
#         if user:
#             if data.status == "approved":
#                 user.is_verified = True
#             elif data.status == "rejected":
#                 user.is_verified = False
#
#             await user.save()
#
#     return kyc


@user_router.patch("/kyc-verifications/{user_id}", response_model=KYCResponse, status_code=status.HTTP_200_OK)
async def update_kyc_status_by_user_id(
        user_id: UUID,
        data: KYCUpdate,
        current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
):
    """
    Update KYC status. Only Admin or Moderators can perform this action.
    """
    # Permission Check
    is_admin = isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN
    is_mod = isinstance(current_user, ModeratorModel)

    if not is_admin and not is_mod:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    kyc = await KYCModel.find_one(KYCModel.user.id == user_id, fetch_links=True)


    if not kyc:
        raise HTTPException(status_code=404, detail="KYC request not found")

    kyc.status = data.status
    if data.rejection_reason:
        kyc.rejection_reason = data.rejection_reason

    await kyc.save()
    return kyc




@user_router.get("/all/moderators", response_model=List[ModeratorResponse], status_code=status.HTTP_200_OK)
async def get_all_moderators(skip: int = 0, limit: int = 20):
    """
    Retrieve a list of all moderators with pagination.
    
    - **skip**: Number of records to skip (default is 0)
    - **limit**: Maximum number of records to return (default is 20)
    """
    # Fetch moderators sorted by creation date (newest first)
    moderators = await ModeratorModel.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
    return moderators


@user_router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(user_id: str):
    """
    Permanently delete a user from the database using their ID.
    """
    # First, verify if the user exists before attempting deletion
    user = await UserModel.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Execute the delete command via Beanie
    await user.delete()

    return {"message": "User deleted successfully"}