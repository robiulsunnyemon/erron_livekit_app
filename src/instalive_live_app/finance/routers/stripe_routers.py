import stripe
import os
from fastapi import APIRouter, Depends, HTTPException, Request, status
from instalive_live_app.users.utils.get_current_user import get_current_user
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.finance.schemas.finance import StripePaymentRequest, StripePaymentResponse
from instalive_live_app.finance.models.transaction import TransactionModel, TransactionType, TransactionReason
from instalive_live_app.notifications.utils import send_notification
from instalive_live_app.notifications.models import NotificationModel
from instalive_live_app.finance.models.stripe_models import ProcessedStripeEvent

router = APIRouter(prefix="/finance/stripe", tags=["Stripe Payment"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/create-payment-intent", response_model=StripePaymentResponse)
async def create_payment_intent(
    data: StripePaymentRequest,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        # Create a PaymentIntent with the order amount and currency
        # Stripe expects amount in cents
        intent = stripe.PaymentIntent.create(
            amount=int(data.amount * 100),
            currency='usd',
            metadata={
                'user_id': str(current_user.id),
                'tokens': str(data.tokens)
            }
        )
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # Handle the event
    print(f"🔔 Stripe Webhook received event: {event['type']}")
    
    # Check for Idempotency: Store processed Stripe event.id
    existing_event = await ProcessedStripeEvent.find_one(ProcessedStripeEvent.event_id == event['id'])
    if existing_event:
        print(f"Duplicate Stripe event detected: {event['id']}")
        return {"status": "already_processed"}

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        
        # Verify status
        if payment_intent['status'] != 'succeeded':
             print(f"⚠️ PaymentIntent status is {payment_intent['status']}, not succeeded. Skipping.")
             return {"status": "ignored"}

        # Record event as processed
        await ProcessedStripeEvent(event_id=event['id'], type=event['type']).insert()

        user_id = payment_intent['metadata'].get('user_id')
        tokens = payment_intent['metadata'].get('tokens')

        print(f"💳 PaymentIntent succeeded. UserID: {user_id}, Tokens: {tokens}")

        if user_id and tokens:
            user = await UserModel.get(user_id)
            if user:
                # Atomic increment
                await user.update({"$inc": {UserModel.coins: int(tokens)}})
                await user.fetch()

                # Record transaction
                await TransactionModel(
                    user=user,
                    amount=int(tokens),
                    transaction_type=TransactionType.CREDIT,
                    reason=TransactionReason.TOPUP,
                    description=f"Stripe Topup: ${payment_intent['amount'] / 100}"
                ).insert()


                print(f"💰 User {user.email} topped up with {tokens} tokens via Stripe successfully.")
                
                # Send Notification
                await send_notification(
                    user=user,
                    title="Token Top-up Successful",
                    body=f"You have successfully purchased {tokens} tokens via Stripe.",
                    type=NotificationType.FINANCE,
                    related_entity_id=payment_intent['id']
                )
            else:
                print(f"❌ User not found for ID: {user_id}")
        else:
            print(f"⚠️ Missing metadata in PaymentIntent: user_id={user_id}, tokens={tokens}")

    return {"status": "success"}
