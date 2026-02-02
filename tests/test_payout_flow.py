from fastapi import status
from instalive_live_app.finance.models.payout import PayoutConfigModel, PayoutStatus

# Note: This is a conceptual test structure. 
# As the project uses Beanie/Motor (Async MongoDB), full integration tests require a running DB instance.

def test_payout_config_defaults():
    config = PayoutConfigModel()
    assert config.token_rate_usd == 0.01
    assert config.platform_fee_percent == 30.0

# Manual Verification Steps for User:
# 1. Start Server: uvicorn instalive_live_app.main:app --reload
# 2. Login as User -> Get Token
# 3. Add Beneficiary: POST /api/v1/finance/beneficiaries
# 4. Request Payout: POST /api/v1/finance/payout/request
# 5. Login as Admin -> Get Token
# 6. Check Requests: GET /api/v1/finance/admin/payouts
# 7. Approve/Decline: POST /api/v1/finance/admin/payouts/{id}/action
