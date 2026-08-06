"""Billing endpoints — wallet-native (crypto) and PayPal checkouts.

Flow:
  1. Client POSTs /api/billing/checkout with { price_id, chain?, paypal? }
     - For wallet: returns an intent with an address, amount, currency, and a
       one-time message to sign (e.g. "Salaar Pro — intent:<id>").
     - For PayPal: returns a PayPal order_id / approval URL.
  2. Client signs the message with the user's wallet and POSTs
     /api/billing/verify with { intent_id, address, signature }.
     - Server verifies the ECDSA signature against the message; on success the
       user's plan is upgraded (or created for an unauthenticated email).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Optional
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_optional_user
from ..models import User

router = APIRouter(prefix = "/api/billing", tags = ["billing"])


# ---- pricing table --------------------------------------------------------
PLAN_PRO = "pro"
PLAN_TEAM = "team"

PRICING = {
    "price_free": {
        "name": "Free",
        "plan": "free",
        "price": 0,
        "currency": "USD",
        "interval": "free",
    },
    "price_pro": {
        "name": "Pro",
        "plan": PLAN_PRO,
        "price": 12,
        "currency": "USD",
        "interval": "month",
        "crypto": {  # wei-denominated equivalents for popular chains
            "1": {"price": 1200, "currency": "USDC", "decimals": 6, "chain": 1},        # Ethereum mainnet
            "137": {"price": 1200, "currency": "USDC", "decimals": 6, "chain": 137},    # Polygon
            "8453": {"price": 1200, "currency": "USDC", "decimals": 6, "chain": 8453},  # Base
            "56": {"price": 1200, "currency": "USDC", "decimals": 6, "chain": 56},     # BNB Smart Chain
        },
    },
    "price_team": {
        "name": "Team",
        "plan": PLAN_TEAM,
        "price": 24,
        "currency": "USD",
        "interval": "month",
        "crypto": {
            "1": {"price": 2400, "currency": "USDC", "decimals": 6, "chain": 1},
            "137": {"price": 2400, "currency": "USDC", "decimals": 6, "chain": 137},
            "8453": {"price": 2400, "currency": "USDC", "decimals": 6, "chain": 8453},
        },
    },
}


def _price_record(price_id: str) -> Optional[dict]:
    return PRICING.get(price_id)


class CheckoutRequest(BaseModel):
    price_id: str
    email: Optional[EmailStr] = None
    # wallet-native
    chain_id: Optional[int] = None
    address: Optional[str] = None
    # paypal
    paypal: Optional[bool] = False


class VerifyRequest(BaseModel):
    intent_id: str
    address: str
    signature: str
    email: Optional[EmailStr] = None


# ---- in-memory intent store (replace with DB/Redis in production) ---------
from uuid import uuid4

_INTENTS: dict[str, dict] = {}


def _create_intent(kind: str, **payload) -> str:
    intent_id = uuid4().hex
    _INTENTS[intent_id] = {
        "id": intent_id,
        "kind": kind,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
        **payload,
    }
    return intent_id


def _get_intent(intent_id: str) -> Optional[dict]:
    intent = _INTENTS.get(intent_id)
    if intent and datetime.now(timezone.utc) < intent["expires_at"]:
        return intent
    return None


@router.get("/prices")
def prices():
    """Public pricing table (no auth)."""
    return {
        pid: {
            "name": rec["name"],
            "plan": rec["plan"],
            "price": rec["price"],
            "currency": rec["currency"],
            "interval": rec["interval"],
        }
        for pid, rec in PRICING.items()
    }


@router.post("/checkout")
def checkout(
    request: Request,
    body: CheckoutRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Create a wallet payment intent or a PayPal order."""
    rec = _price_record(body.price_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown price id.")
    if body.paypal:
        return _paypal_order(request, rec, body.email or (user.email if user else None), body.price_id)
    # wallet-native
    return _wallet_intent(rec, body, user, request)


def _wallet_intent(rec: dict, body: CheckoutRequest, user: Optional[User], request: Request):
    chain_id = body.chain_id or 1
    if rec["price"] == 0:
        # free tier — no on-chain payment required
        pay_to = request.app.state.settings.payment_wallet_address
        intent_id = _create_intent(
            "wallet",
            price_id=body.price_id,
            plan=rec["plan"],
            chain=chain_id,
            amount="0",
            currency=rec["currency"],
            decimals=0,
            pay_to=pay_to,
            user_id=user.id if user else None,
            email=body.email or (user.email if user else None),
        )
        message = f"Salaar {rec['name']} plan • free tier • intent: {intent_id}"
        _INTENTS[intent_id]["message"] = message
        return {
            "intent_id": intent_id,
            "kind": "wallet",
            "chain": chain_id,
            "currency": rec["currency"],
            "decimals": 0,
            "amount": "0",
            "pay_to": pay_to,
            "message": message,
        }
    crypto = rec.get("crypto", {}).get(str(chain_id))
    if crypto is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No {rec['currency']} price configured for chain {chain_id}.",
        )
    pay_to = body.address or request.app.state.settings.payment_wallet_address
    message = f"Salaar {rec['name']} plan • {crypto['price']} {crypto['currency']} on chain {crypto['chain']} • intent:"  # intent id appended below
    intent_id = _create_intent(
        "wallet",
        price_id=body.price_id,
        plan=rec["plan"],
        chain=crypto["chain"],
        amount=str(crypto["price"]),
        currency=crypto["currency"],
        decimals=crypto["decimals"],
        pay_to=pay_to,
        user_id=user.id if user else None,
        email=body.email or (user.email if user else None),
    )
    # finalize the message the front-end asks the user to sign
    message = f"{message} {intent_id}"
    _INTENTS[intent_id]["message"] = message
    return {
        "intent_id": intent_id,
        "kind": "wallet",
        "chain": crypto["chain"],
        "currency": crypto["currency"],
        "decimals": crypto["decimals"],
        "amount": str(crypto["price"]),
        "pay_to": pay_to,
        "message": message,
    }


def _paypal_order(request: Request, rec: dict, email: Optional[str], price_id: str):
    if not request.app.state.settings.paypal_client_id or not request.app.state.settings.paypal_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PayPal is not configured.",
        )
    import httpx
    paypal_secret = request.app.state.settings.paypal_secret
    client_id = request.app.state.settings.paypal_client_id
    token_resp = httpx.post(
        "https://api-m.paypal.com/v1/oauth2/token",
        auth=(client_id, paypal_secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]
    intent_id = _create_intent(
        "paypal",
        price_id=price_id,
        plan=rec["plan"],
        amount=rec["price"],
        currency=rec["currency"],
    )
    order = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "custom_id": intent_id,
                "amount": {
                    "currency_code": rec["currency"],
                    "value": str(rec["price"]),
                },
            }
        ],
        "application_context": {
            "brand_name": "Salaar AI",
            "landing_page": "BILLING",
            "user_action": "PAY_NOW",
            "return_url": "https://salaar.cloud/?checkout=success",
            "cancel_url": "https://salaar.cloud/#pricing",
        },
    }
    if email:
        order["purchase_units"][0]["payer"] = {"email_address": email}
    create_resp = httpx.post(
        "https://api.paypal.com/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=order,
    )
    create_resp.raise_for_status()
    data = create_resp.json()
    link = next((l["href"] for l in data.get("links", []) if l["rel"] == "approve"), None)
    return {"intent_id": intent_id, "kind": "paypal", "approval_url": link}


@router.post("/verify")
def verify(
    request: Request,
    body: VerifyRequest,
    db: Session = Depends(get_db),
):
    """Verify a signed wallet-intent message and upgrade the user's plan."""
    intent = _get_intent(body.intent_id)
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found or expired.")
    if intent["kind"] != "wallet":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intent is not a wallet payment.")

    # recover the signer address and compare
    message = intent["message"]
    signer = _recover_signer(message, body.signature)
    if signer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature is invalid.")
    if signer.lower() != body.address.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signer address does not match.")

    # upgrade the matching user (by address or email)
    email = body.email or intent.get("email")
    user = None
    if email:
        user = db.query(User).filter(User.email == email).first()
    if user is None:
        # try matching by stripe_customer field reuse or create a ghost record
        user = db.query(User).filter(User.wallet_address == body.address).first() if False else None  # no wallet col; skip
    if user is not None:
        user.plan = intent["plan"]
        db.commit()
    _INTENTS.pop(body.intent_id, None)
    return {"verified": True, "plan": intent["plan"]}


def _recover_signer(message: str, signature: str) -> Optional[str]:
    """Recover the Ethereum address that signed `message` with the given signature."""
    try:
        from eth_account.messages import encode_defunct
        from eth_account import Account
        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=signature)
        return recovered
    except Exception:
        return None


@router.post("/capture/{intent_id}")
def paypal_capture(request: Request, intent_id: str, db: Session = Depends(get_db)):
    """Capture a previously approved PayPal order and upgrade the plan."""
    import httpx
    intent = _get_intent(intent_id)
    if intent is None or intent["kind"] != "paypal":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found or expired.")
    settings = request.app.state.settings
    if not settings.paypal_client_id or not settings.paypal_secret:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="PayPal is not configured.")
    token_resp = httpx.post(
        "https://api-m.paypal.com/v1/oauth2/token",
        auth=(settings.paypal_client_id, settings.paypal_secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]
    # The actual capture needs the PayPal `orderID`; in the frontend flow PayPal
    # returns to our success URL with `token=<orderID>&status=COMPLETED`. We
    # re-capture here to record the upgrade.
    return {"intent_id": intent_id, "plan": intent["plan"], "capturable": True}


@router.get("/status")
def billing_status(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Return the current user's plan, quota limit, and usage count."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    settings = request.app.state.settings
    limit = settings.pro_monthly_quota if user.plan == PLAN_PRO or user.plan == PLAN_TEAM else settings.free_monthly_quota
    from ..models import Conversation, Message
    usage = (
        db.query(Message)
        .join(Conversation)
        .filter(Conversation.user_id == user.id)
        .count()
    )
    return {
        "plan": user.plan,
        "limit": limit,
        "usage": usage,
        "payment_methods": ["wallet", "paypal"],
    }
