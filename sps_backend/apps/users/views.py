
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from .models import Users as User,TokenBlacklist
from .schemas import UserCreate, UserLogin
from fastapi import HTTPException, Response, Request
from datetime import datetime, timedelta, timezone
import os
import jwt
from config import settings
from apps.users.security import hash_password, verify_password
import uuid

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


async def create_user_view(user: UserCreate, db: AsyncSession):
    db_user = User(email=user.email, password=hash_password(user.password))
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_users_view(db: AsyncSession, request: Request):

    user_email = request.state.user_email
    result = await db.execute(select(User).where(User.email == user_email))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

async def login_user_view(user: UserLogin, response: Response, db: AsyncSession):
    result = await db.execute(select(User).where(User.email == user.email))
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
    user_result = await db.execute(select(User).where(User.email == user_email).options(selectinload(User.activations)))
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

