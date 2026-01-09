from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Response, Request
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from .models import Users, TokenBlacklist, Invitation, UserRole
from .schemas import UserCreate, UserLogin, InvitationCreate
from datetime import datetime, timedelta, timezone
import os
import jwt
from config import settings
from apps.users.security import hash_password, verify_password
import uuid
import secrets

def create_access_token(
    subject: str,
    user_id: str,
    role: str,
    expires_delta: timedelta
):
    payload = {
        "sub": subject,
        "id": user_id,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + expires_delta
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

def create_refresh_token(
    subject: str,
    user_id: str,
    role: str,
    expires_delta: timedelta
):
    payload = {
        "sub": subject,
        "id": user_id,
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + expires_delta
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

def generate_secure_token() -> str:
    return secrets.token_urlsafe(32)

async def create_user_view(user: UserCreate, db: AsyncSession, invitation_token: Optional[str] = None):
    if invitation_token:
        # Validate invitation token
        result = await db.execute(
            select(Invitation).where(
                Invitation.token == invitation_token,
                Invitation.expires_at > datetime.now(timezone.utc)
            )
        )
        invitation = result.scalar_one_or_none()
        if not invitation or invitation.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Invalid or expired invitation token")
        user.email=invitation.email
        assigned_role=invitation.role

    existing_user_query= select(Users).where(Users.email == user.email)
    result = await db.execute(existing_user_query)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    if invitation_token:
        db_user = Users(email=user.email, password=hash_password(user.password), role=assigned_role, invited_by=invitation.creator_id, is_active=True)
        db_user._skip_activation = True  # Custom attribute to skip activation email
    else:
        db_user = Users(email=user.email, password=hash_password(user.password))
        db_user._skip_activation = False  # Custom attribute to indicate activation email should be sent
    db.add(db_user)
    if invitation_token:
        await db.delete(invitation)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_users_view(db: AsyncSession, request: Request):

    user_email = request.state.user_email
    result = await db.execute(select(Users).where(Users.email == user_email))
    db_user = result.scalar_one_or_none()
    test_tls= await db.execute(select(Users))
    all_users= test_tls.scalars().all()
    print(f"All users in DB: {[user.id for user in all_users]}")
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

async def login_user_view(user: UserLogin, response: Response, db: AsyncSession):
    result = await db.execute(select(Users).where(Users.email == user.email))
    db_user = result.scalar_one_or_none()
    if db_user and verify_password(user.password, db_user.password):
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=db_user.email, user_id=str(db_user.id), role=db_user.role, expires_delta=access_token_expires
        )
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = create_refresh_token(
            subject=db_user.email, user_id=str(db_user.id), role=db_user.role, expires_delta=refresh_token_expires
        )

        # insert jti into TokenBlacklist table
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        expires_at = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
        token_blacklist_entry = TokenBlacklist(
            jti=jti,
            user_id=db_user.id,
            expires_at=expires_at
        )
        db.add(token_blacklist_entry)
        await db.commit()

        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax")
        response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax")
        return {"email": db_user.email}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

async def activate_user_view(user_email: str, activation_code: str, db: AsyncSession):
    # Fetch the user by email
    user_result = await db.execute(select(Users).where(Users.email == user_email).options(selectinload(Users.activations)))
    db_user = user_result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if db_user.is_active:
        return {"message": "User is already active"}

    activation_result = db_user.activations.activation_code == activation_code and db_user.activations.is_used == False
    db_activation = activation_result

    if not db_activation:
        raise HTTPException(status_code=400, detail="Invalid or already used activation code")

    # Perform update
    db_user.is_active = True
    db_user.activations.is_used = True
    await db.commit()
    return {"message": "User activated successfully"}

async def refresh_token_view(db: AsyncSession, request: Request, response: Response):
    # This function assumes the refresh token is sent via cookies
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        old_jti = payload.get("jti")
        user_email = payload.get("sub")
        user_id = payload.get("id")
        user_role = payload.get("role") 
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Check if jti is in TokenBlacklist
    new_refresh_token = create_refresh_token(
            subject=user_email, user_id=str(user_id), role=user_role, expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
    new_payload = jwt.decode(new_refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    new_jti = new_payload.get("jti")
    new_exp = datetime.fromtimestamp(new_payload.get("exp"), tz=timezone.utc)

    # Attempt to update the row and if exist return ID
    statement = (
        update(TokenBlacklist)
        .where(TokenBlacklist.jti == old_jti)
        .values(jti=new_jti, expires_at=new_exp)
        .returning(TokenBlacklist.id)
    )
    result = await db.execute(statement)
    updated_id = result.scalar_one_or_none()

    if updated_id is None:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or has been revoked")
    try:
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update refresh token")
    
    new_access_token = create_access_token(
        subject=user_email, user_id=user_id, role=user_role, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=False, samesite="lax")
    response.set_cookie(key="refresh_token", value=new_refresh_token, httponly=True, secure=False, samesite="lax")
    return {"message": "Access token refreshed"}

async def logout_user_view(db: AsyncSession, request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        jti = payload.get("jti")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Delete the token from TokenBlacklist
    statement = (
        delete(TokenBlacklist)
        .where(TokenBlacklist.jti == jti)
    )
    await db.execute(statement)
    await db.commit()
    
    # Clear cookies
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    
    return {"message": "Logged out successfully"}

async def invite_user_view(body: InvitationCreate, db: AsyncSession, request: Request):
    token = generate_secure_token()
    new_invite = Invitation(
        email=body.email,
        role=body.role,
        creator_id=request.state.user_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_invite)
    await db.commit()
    # TODO: Send invitation email with the token link
    verification_link= f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/register?invitation_token={token}"
    print(f"Invitation Link is : {verification_link}")

    return {"message": "Invitation sent successfully"}

async def get_all_user_view(db: AsyncSession, request: Request):
    result = await db.execute(select(Users))
    users = result.scalars().all()
    users_list = [
        {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
        for user in users
    ]
    
    return users_list