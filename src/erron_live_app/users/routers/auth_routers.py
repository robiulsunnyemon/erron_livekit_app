from fastapi import APIRouter, HTTPException, Depends,status
from fastapi.security import OAuth2PasswordRequestForm
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.users.schemas.user_schemas import UserResponse, UserCreate, VerifyOTP, ResendOTPRequest, ResetPasswordRequest, ModeratorCreate, ModeratorResponse, ModeratorUpdate, ModeratorManageUserStatus
from erron_live_app.users.utils.account_status import AccountStatus
from erron_live_app.users.utils.email_config import SendOtpModel
from erron_live_app.users.utils.otp_generate import generate_otp
from erron_live_app.users.utils.password import hash_password, verify_password
from erron_live_app.users.utils.token_generate import create_access_token
from erron_live_app.users.utils.user_role import UserRole
from erron_live_app.users.utils.get_current_user import get_current_user
import requests
from uuid import UUID
from typing import Union
from erron_live_app.notifications.utils import send_notification
from erron_live_app.notifications.models import NotificationType
from erron_live_app.users.utils.email_config import send_otp


router = APIRouter(prefix="/auth", tags=["Auth"])


from erron_live_app.admin.utils import check_feature_access, log_admin_action

@router.post("/signup" ,response_model=UserResponse,status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    await check_feature_access("registration")
    hashed_password = hash_password(user.password)
    db_user = await UserModel.find_one(UserModel.email == user.email)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    otp = generate_otp()
    new_user = UserModel(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        password=hashed_password,
        otp=otp
    )
    await new_user.create()
    send_otp_data = SendOtpModel(email=new_user.email, otp=new_user.otp)
    await send_otp(send_otp_data)
    
    # Notification: Account Created
    await send_notification(
        user=new_user,
        title="Welcome to Erron Live!",
        body="Thank you for creating an account. Please verify your email.",
        type=NotificationType.ACCOUNT
    )
    
    return new_user




# POST create new user
@router.post("/signup/admin" ,response_model=UserResponse,status_code=status.HTTP_201_CREATED)
async def create_admin(user: UserCreate):
    # Admin creation might still be allowed or should it also be blocked? 
    # Usually admin creation is manual/scripted, but if exposed via API, let's respect the switch or explicit override.
    # Assuming restricted to registration switch for consistency unless specific "Admin Registration" switch exists.
    # For safety, let's require it OR assume this endpoint is highly protected (it has no auth dependency though? Dangerous!)
    # The original code has no auth on /signup/admin. That is a security risk but out of scope for *this* task.
    # I will add the check.
    await check_feature_access("registration")

    hashed_password = hash_password(user.password)
    db_user = await UserModel.find_one(UserModel.email == user.email)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    otp = generate_otp()
    new_user = UserModel(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        password=hashed_password,
        otp=otp,
        role=UserRole.ADMIN
    )
    await new_user.create()
    send_otp_data = SendOtpModel(email=new_user.email, otp=new_user.otp)
    from erron_live_app.users.utils.email_config import send_otp
    await send_otp(send_otp_data)
    return new_user


# POST create moderator (Admin only)
@router.post("/create-moderator", response_model=ModeratorResponse, status_code=status.HTTP_201_CREATED)
async def create_moderator(data: ModeratorCreate, current_user: UserModel = Depends(get_current_user)):
    # Check if current user is ADMIN
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create moderators")

    # Check if email already exists in users or moderators
    db_user = await UserModel.find_one(UserModel.email == data.email)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered as a user")
    
    db_mod = await ModeratorModel.find_one(ModeratorModel.email == data.email)
    if db_mod:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered as a moderator")

    # Check if username exists
    db_mod_user = await ModeratorModel.find_one(ModeratorModel.username == data.username)
    if db_mod_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    hashed_password = hash_password(data.password)
    new_mod = ModeratorModel(
        full_name=data.full_name,
        username=data.username,
        email=data.email,
        password=hashed_password,
        can_view_reports=data.can_view_reports,
        can_review_appeals=data.can_review_appeals,
        can_access_live_monitor=data.can_access_live_monitor,
        can_system_config=data.can_system_config,
        can_issue_bans=data.can_issue_bans,
        can_manage_users=data.can_manage_users,
        can_approve_payouts=data.can_approve_payouts,
        created_by=current_user
    )
    await new_mod.insert()

    # Log password for "email" sending (In real app, trigger email sending service here)
    print(f"📧 Sending credentials to {data.email}: Username: {data.username}, Password: {data.password}")

    await log_admin_action(
        actor=current_user,
        action="Created Moderator",
        target=new_mod.username,
        severity="High",
        details=f"Created moderator with email {new_mod.email}"
    )

    return new_mod


# PATCH update moderator (Admin only)
@router.patch("/update-moderator/{moderator_id}", response_model=ModeratorResponse)
async def update_moderator(
    moderator_id: UUID, 
    update_data: ModeratorUpdate, 
    current_user: UserModel = Depends(get_current_user)
):
    # Check if current user is ADMIN
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update moderators")

    # Find the moderator
    moderator = await ModeratorModel.get(moderator_id)
    if not moderator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moderator not found")

    # Update fields if provided
    update_dict = update_data.model_dump(exclude_unset=True)
    
    if not update_dict:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    # Update moderator object
    for key, value in update_dict.items():
        setattr(moderator, key, value)
    
    await moderator.save()
    
    await log_admin_action(
        actor=current_user,
        action="Updated Moderator",
        target=moderator.username,
        severity="Medium",
        details=f"Updated fields: {', '.join(update_dict.keys())}"
    )
    
    return moderator


# PATCH moderator manage user status (Moderator/Admin only)
@router.patch("/moderator/update-user-status/{user_id}", response_model=UserResponse)
async def update_user_status_by_moderator(
    user_id: UUID,
    data: ModeratorManageUserStatus,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
):
    # Permission Check
    is_admin = False
    if isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN:
        is_admin = True
    
    if not is_admin:
        if not isinstance(current_user, ModeratorModel) or not current_user.can_manage_users:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    # Find the user to update
    target_user = await UserModel.get(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update status
    old_status = target_user.account_status
    target_user.account_status = data.status
    await target_user.save()

    # Increment moderator counters if it's a moderator acting
    if isinstance(current_user, ModeratorModel):
        if data.status == AccountStatus.SUSPEND:
            current_user.suspended_count += 1
        elif data.status == AccountStatus.ACTIVE:
            current_user.activated_count += 1
        elif data.status == AccountStatus.INACTIVE:
            current_user.inactivated_count += 1
            
        await current_user.save()

    # Log the action
    actor_identifier = current_user.email if isinstance(current_user, UserModel) else current_user.username
    await log_admin_action(
        actor=current_user,
        action="Updated User Status",
        target=target_user.email,
        severity="High" if data.status == AccountStatus.SUSPEND else "Medium",
        details=f"Changed status from {old_status} to {data.status}"
    )

    return target_user



@router.post("/otp-verify", status_code=status.HTTP_200_OK)
async def verify_otp(user:VerifyOTP):
    db_user =await UserModel.find_one(UserModel.email == user.email)
    if db_user is None :
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    if user.otp != db_user.otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Wrong OTP")

    db_user.is_verified = True
    await db_user.save()
    
    # Notification: Verified
    await send_notification(
        user=db_user,
        title="Account Verified",
        body="Your account has been successfully verified!",
        type=NotificationType.ACCOUNT
    )
    
    return {"message":"You have  verified","data":db_user}



# Login logic update
@router.post("/login", status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Flexible query for email or phone
    db_user = await UserModel.find_one(UserModel.email == form_data.username)
    
    # If not found in UserModel, check ModeratorModel
    is_moderator = False
    if not db_user:
        db_user = await ModeratorModel.find_one(ModeratorModel.username == form_data.username)
        if not db_user:
             db_user = await ModeratorModel.find_one(ModeratorModel.email == form_data.username)
        is_moderator = True if db_user else False

    if not db_user or not verify_password(form_data.password, db_user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not is_moderator and not db_user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified")

    # str() conversion for ID is safer
    token = create_access_token(data={
        "sub": str(db_user.id),
        "email": db_user.email,
        "role": db_user.role.value
    })
    return {"access_token": token, "token_type": "bearer"}



@router.post("/resend-otp", status_code=status.HTTP_200_OK)
async def resend_otp(request: ResendOTPRequest):
    db_user = await UserModel.find_one(UserModel.email == request.email)
    if db_user is None :
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    db_user.otp = generate_otp()
    await db_user.save()
    send_otp_data = SendOtpModel(email=db_user.email, otp=db_user.otp)
    from erron_live_app.users.utils.email_config import send_otp
    await send_otp(send_otp_data)


    return {
        "message": "User registered successfully.Please check your email.A 6 digit otp has been sent.",
        "data":db_user,
        "otp":db_user.otp
    }



@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(request: ResetPasswordRequest):
    db_user = await UserModel.find_one(UserModel.email == request.email)
    if db_user is None :
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")

    if not db_user.is_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Your account is not verified with otp")

    hashed_password = hash_password(request.new_password)


    db_user.password = hash_password(request.new_password)
    await db_user.save()
    
    # Notification: Security Alert
    await send_notification(
        user=db_user,
        title="Password Changed",
        body="Your password was reset successfully.",
        type=NotificationType.ACCOUNT
    )
    
    return {"message":"successfully reset password"}




@router.post("/google-login",status_code=status.HTTP_201_CREATED)
async def google_login_token(access_token: str):

    if access_token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="please give me token")


    response = requests.get(
        f'https://www.googleapis.com/oauth2/v2/userinfo?access_token={access_token}'
    )
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google token")

    user_info = response.json()
    email = user_info["email"]
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    db_user = await UserModel.find_one(UserModel.email == email)
    if db_user is None :
        new_user = UserModel(
            first_name=name.split(" ")[0] if name else "",
            last_name=" ".join(name.split(" ")[1:]) if len(name.split(" ")) > 1 else "",
            email=email,
            phone_number="",
            password=None,
            is_verified=True,
            profile_image=picture,
            auth_provider="google",
        )
        await new_user.create()
        token = create_access_token(data={
            "sub": str(new_user.id),
            "email": new_user.email,
            "role": new_user.role.value
        })
        return {"access_token": token, "token_type": "bearer"}


    # Generate JWT token

    token = create_access_token(data={
        "sub": str(db_user.id),
        "email": db_user.email,
        "role": db_user.role.value
    })
    return {"access_token": token, "token_type": "bearer"}