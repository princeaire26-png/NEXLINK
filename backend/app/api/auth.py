"""Authentication API routes."""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import get_db
from app.models import AuditEvent, Session, User, Organization, Membership
from app.schemas import (
    AuthTokenResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.mfa import new_secret, provisioning_uri, verify_code
from app.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    hash_token,
    verify_password,
    verify_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _issue_session(
    user: User,
    db: AsyncSession,
    request: Request,
) -> tuple[str, str]:
    session_id = uuid.uuid4()
    refresh_expires = _now() + timedelta(days=settings.jwt_refresh_token_expire_days)
    claims = {"sub": str(user.id), "email": user.email, "role": user.role, "sid": str(session_id)}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)
    db.add(Session(
        id=session_id,
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=refresh_expires,
    ))
    return access_token, refresh_token


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegister, http_request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "error": "REGISTRATION_FAILED", "message": "An account with this email already exists"
        })

    user = User(
        id=uuid.uuid4(), email=request.email, password_hash=get_password_hash(request.password),
        name=request.name, role="owner", email_verified=False, active=True,
    )
    db.add(user)
    await db.flush()
    org = Organization(id=uuid.uuid4(), name=f"{request.name} Workspace", slug=f"{user.id.hex[:12]}", plan="personal")
    db.add(org)
    await db.flush()
    db.add(Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org.id, role="owner"))
    access_token, refresh_token = await _issue_session(user, db, http_request)
    db.add(AuditEvent(
        id=uuid.uuid4(), event_type="user_registered", actor_id=user.id, actor_type="user",
        action="register", result="success", details={"email": user.email},
    ))
    await db.commit()
    return AuthTokenResponse(user=UserResponse.model_validate(user), access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: UserLogin, http_request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "error": "AUTHENTICATION_FAILED", "message": "Invalid email or password"
        })
    if not user.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
            "error": "ACCOUNT_DISABLED", "message": "Your account has been disabled"
        })

    if user.mfa_enabled:
        if not request.mfa_code or not user.mfa_secret or not verify_code(user.mfa_secret, request.mfa_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "MFA_REQUIRED", "message": "A valid MFA code is required"})

    user.last_login_at = _now()
    access_token, refresh_token = await _issue_session(user, db, http_request)
    db.add(AuditEvent(
        id=uuid.uuid4(), event_type="user_login", actor_id=user.id, actor_type="user",
        action="login", result="success",
    ))
    await db.commit()
    return AuthTokenResponse(user=UserResponse.model_validate(user), access_token=access_token, refresh_token=refresh_token)


@router.post("/mfa/setup")
async def setup_mfa(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a TOTP secret. The caller must verify the code before MFA is enabled."""
    secret = new_secret()
    current_user.mfa_secret = secret
    current_user.mfa_enabled = False
    await db.commit()
    return {"secret": secret, "otpauth_uri": provisioning_uri(secret, current_user.email), "enabled": False}


@router.post("/mfa/enable")
async def enable_mfa(code: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.mfa_secret or not verify_code(current_user.mfa_secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")
    current_user.mfa_enabled = True
    db.add(AuditEvent(id=uuid.uuid4(), event_type="mfa_enabled", actor_id=current_user.id, actor_type="user", action="mfa_enable", result="success"))
    await db.commit()
    return {"enabled": True}


@router.post("/mfa/disable")
async def disable_mfa(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    db.add(AuditEvent(id=uuid.uuid4(), event_type="mfa_disabled", actor_id=current_user.id, actor_type="user", action="mfa_disable", result="success"))
    await db.commit()
    return {"enabled": False}


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = verify_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "error": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"
        })

    session_id = payload.get("sid")
    user_id = payload.get("sub")
    if not session_id or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "INVALID_REFRESH_TOKEN"})

    try:
        session_uuid = UUID(session_id)
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "INVALID_REFRESH_TOKEN"})

    result = await db.execute(select(Session).where(
        Session.id == session_uuid,
        Session.user_id == user_uuid,
        Session.revoked_at.is_(None),
        Session.expires_at > _now(),
    ))
    session = result.scalar_one_or_none()
    if session is None or session.token_hash != hash_token(request.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "error": "INVALID_REFRESH_TOKEN", "message": "Refresh token has been revoked or is invalid"
        })

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "INVALID_REFRESH_TOKEN"})

    session.revoked_at = _now()
    # Issue a new rotated session.
    new_session_id = uuid.uuid4()
    claims = {"sub": str(user.id), "email": user.email, "role": user.role, "sid": str(new_session_id)}
    access_token = create_access_token(claims)
    new_refresh_token = create_refresh_token(claims)
    db.add(Session(
        id=new_session_id, user_id=user.id, token_hash=hash_token(new_refresh_token),
        expires_at=_now() + timedelta(days=settings.jwt_refresh_token_expire_days),
    ))
    await db.commit()
    return RefreshTokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # The authenticated dependency has already validated the access token.
    # Revoke all active sessions for this user so the logout is effective even
    # if the client discards the token before the server sees this request.
    from sqlalchemy import update
    await db.execute(update(Session).where(
        Session.user_id == current_user.id, Session.revoked_at.is_(None)
    ).values(revoked_at=_now()))
    await db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
