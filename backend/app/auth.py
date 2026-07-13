"""Authentication & authorization for the invoice-processing API.

Adds role-based login on top of the existing pipeline **without** changing any
business logic. A successful login mints a short-lived HS256 JWT whose ``role``
claim drives:

  * which agents the caller may use (``ALLOWED_AGENTS``), and
  * the pipeline :class:`~app.schemas.Channel` (customer portal vs CS console).

The user store is an in-memory placeholder (seeded below) that mirrors the
``users`` BigQuery table in the design. Swap :func:`get_user_by_username` for a
real BigQuery/Firestore read later — every caller depends only on that function.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings
from .schemas import Channel, PublicUser, Role, UserContext

# Bearer extractor. ``auto_error=False`` lets us support BOTH authenticated and
# anonymous (legacy) callers so existing flows are never disturbed.
_bearer = HTTPBearer(auto_error=False)

# Agents each role may invoke. Customers never see Prevent.
ALLOWED_AGENTS: dict[Role, set[str]] = {
    Role.CUSTOMER: {"explain", "resolve", "simulate"},
    Role.CUSTOMER_SUPPORT: {"explain", "resolve", "simulate", "prevent"},
}


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# In-memory user store (placeholder for the BigQuery `users` table)
# --------------------------------------------------------------------------- #
# Demo password for every seeded account. Change / remove for real deployments.
_DEMO_PASSWORD = "Passw0rd!"


def _seed_users() -> dict[str, dict[str, Any]]:
    pw = hash_password(_DEMO_PASSWORD)
    rows = [
        # 5 customers
        ("u-cust-001", "acme", "Acme Corp", Role.CUSTOMER, ["CTR-1001"]),
        ("u-cust-002", "globex", "Globex Ltd", Role.CUSTOMER, ["CTR-1002", "CTR-1006"]),
        ("u-cust-003", "initech", "Initech", Role.CUSTOMER, ["CTR-1003"]),
        ("u-cust-004", "umbrella", "Umbrella Co", Role.CUSTOMER, ["CTR-1004"]),
        ("u-cust-005", "hooli", "Hooli Inc", Role.CUSTOMER, ["CTR-1005"]),
        # 3 customer-support users
        ("u-sup-001", "ssmith", "Sarah Smith (CS)", Role.CUSTOMER_SUPPORT, []),
        ("u-sup-002", "rkumar", "Rahul Kumar (CS)", Role.CUSTOMER_SUPPORT, []),
        ("u-sup-003", "mgarcia", "Maria Garcia (CS)", Role.CUSTOMER_SUPPORT, []),
    ]
    store: dict[str, dict[str, Any]] = {}
    for user_id, username, display_name, role, contracts in rows:
        store[username] = {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "password_hash": pw,
            "primary_role": role,
            "contract_ids": contracts,
            "is_active": True,
        }
    return store


_USERS: dict[str, dict[str, Any]] = _seed_users()


async def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """Look up a user by login handle (placeholder for a BigQuery read)."""
    return _USERS.get((username or "").strip().lower())


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def issue_token(user: dict[str, Any], settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    role = user["primary_role"]
    payload = {
        "sub": user["user_id"],
        "username": user["username"],
        "name": user.get("display_name"),
        "role": role.value if isinstance(role, Role) else str(role),
        "contract_ids": user.get("contract_ids", []),
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _claims_to_context(claims: dict[str, Any]) -> UserContext:
    return UserContext(
        user_id=claims.get("sub", "unknown"),
        roles=[claims.get("role", Role.CUSTOMER.value)],
        contract_ids=claims.get("contract_ids", []) or [],
    )


def public_user(user: dict[str, Any]) -> PublicUser:
    role = user["primary_role"]
    role = role if isinstance(role, Role) else Role(str(role))
    return PublicUser(
        user_id=user["user_id"],
        username=user["username"],
        display_name=user.get("display_name"),
        role=role,
        contract_ids=user.get("contract_ids", []),
        allowed_agents=sorted(ALLOWED_AGENTS[role]),
    )


# --------------------------------------------------------------------------- #
# FastAPI dependencies
# --------------------------------------------------------------------------- #
def _decode(cred: Optional[HTTPAuthorizationCredentials]) -> Optional[dict[str, Any]]:
    if cred is None or not cred.credentials:
        return None
    try:
        return jwt.decode(
            cred.credentials, get_settings().jwt_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc


def optional_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[UserContext]:
    """Return the authenticated caller when a valid token is present, else None.

    Kept optional so unauthenticated/legacy requests continue to work exactly as
    before (the caller falls back to its previous default identity).
    """
    claims = _decode(cred)
    return _claims_to_context(claims) if claims else None


def require_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> UserContext:
    claims = _decode(cred)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated."
        )
    return _claims_to_context(claims)


def require_support(user: UserContext = Depends(require_user)) -> UserContext:
    if Role.CUSTOMER_SUPPORT.value not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer support role required.",
        )
    return user


def channel_for(user: Optional[UserContext]) -> Channel:
    """Map a caller's role to the pipeline channel.

    Support users get the CS console (human-in-the-loop). Customers get the
    self-service portal, where the pipeline already refuses actionable output.
    """
    if user is not None and Role.CUSTOMER_SUPPORT.value in user.roles:
        return Channel.CS
    return Channel.CUSTOMER_PORTAL


def allowed_agents_for(user: Optional[UserContext]) -> set[str]:
    if user is not None and Role.CUSTOMER_SUPPORT.value in user.roles:
        return ALLOWED_AGENTS[Role.CUSTOMER_SUPPORT]
    if user is not None:
        return ALLOWED_AGENTS[Role.CUSTOMER]
    # Anonymous/legacy callers keep the previous behaviour (all agents).
    return {"explain", "resolve", "simulate", "prevent"}
