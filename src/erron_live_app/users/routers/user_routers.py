
from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile
import shutil
import os
from typing import List
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.schemas.user_schemas import UserResponse, ProfileResponse
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.streaming.models.streaming import LiveStreamModel
from erron_live_app.users.models.kyc_models import KYCModel

# Define the router for User Management
user_router = APIRouter(prefix="/users", tags=["Users"])


@user_router.get("/", response_model=List[UserResponse], status_code=status.HTTP_200_OK)
async def get_all_users(skip: int = 0, limit: int = 20):
    """
    Retrieve a list of all users with pagination.

    - **skip**: Number of records to skip (default is 0)
    - **limit**: Maximum number of records to return (default is 20)
    """
    # Fetch users sorted by creation date (newest first)
    users = await UserModel.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
    return users


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
    return users


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
    return user


@user_router.get("/users/my_profile", response_model=ProfileResponse)
async def my_profile(current_user: UserModel = Depends(get_current_user)):
    # Fetch all past streams by this user (including ones with status 'ended' or similar)
    # Actually, usually you want all streams they've done.
    past_streams = await LiveStreamModel.find(LiveStreamModel.host.id == current_user.id).sort("-created_at").to_list()
    
    # We return a dict that matches ProfileResponse
    return {
        **current_user.model_dump(),
        "past_streams": past_streams
    }


@user_router.post("/kyc/submit", status_code=status.HTTP_201_CREATED)
async def kyc_submit(
    id_front: UploadFile = File(...),
    id_back: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    # Create KYC directory if not exists
    kyc_dir = os.path.join("uploads", "kyc")
    if not os.path.exists(kyc_dir):
        os.makedirs(kyc_dir)

    # Save Front ID
    front_filename = f"front_{current_user.id}_{id_front.filename}"
    front_path = os.path.join(kyc_dir, front_filename)
    with open(front_path, "wb") as buffer:
        shutil.copyfileobj(id_front.file, buffer)

    # Save Back ID
    back_filename = f"back_{current_user.id}_{id_back.filename}"
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


@user_router.get("/kyc/view", status_code=status.HTTP_200_OK)
async def kyc_status(current_user: UserModel = Depends(get_current_user)):
    kyc = await KYCModel.find_one(KYCModel.user.id == current_user.id)
    if not kyc:
        return {"status": "none"}
    return kyc




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