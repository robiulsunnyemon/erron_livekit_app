from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.models.kyc_models import KYCModel


async def populate_user_kyc(user: UserModel) -> dict:
    """
    Populate user dict with KYC information.
    
    Args:
        user: UserModel instance
        
    Returns:
        dict: User data with KYC information included
    """
    user_dict = user.model_dump()
    kyc = await KYCModel.find_one(KYCModel.user.id == user.id)
    if kyc:
        user_dict["kyc"] = kyc.model_dump(exclude={"user", "id"})
    else:
        user_dict["kyc"] = None
    return user_dict
