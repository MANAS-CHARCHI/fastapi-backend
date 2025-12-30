
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import Users as User, Activations
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
    expires_delta: timedelta
):
    payload = {
        "sub": subject,
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
    expires_delta: timedelta
):
    payload = {
        "sub": subject,
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

async def get_users_view(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()

async def login_user_view(user: UserLogin, db: AsyncSession, response: Response):
    result = await db.execute(select(User).where(User.email == user.email))
    db_user = result.scalar_one_or_none()
    
    if db_user and verify_password(user.password, db_user.password):
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=db_user.email, expires_delta=access_token_expires
        )
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = create_refresh_token(
            subject=db_user.email, expires_delta=refresh_token_expires
        )

        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax")
        response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax")

        return {"email": db_user.email}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

async def activate_user_view(user_email: str, activation_code: str, db: AsyncSession):
    # Fetch the user by email
    user_result = await db.execute(select(User).where(User.email == user_email))
    db_user = user_result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if db_user.is_active:
        return {"message": "User is already active"}
    
    # Fetch the activation record
    act_result = await db.execute(
        select(Activations).where(
            Activations.user_id == db_user.id,
            Activations.activation_code == activation_code,
            Activations.is_used == False
        )
    )
    db_activation = act_result.scalar_one_or_none()

    if not db_activation:
        raise HTTPException(status_code=400, detail="Invalid or already used activation code")

    # Perform update
    db_user.is_active = True
    db_activation.is_used = True
    await db.commit()
    return {"message": "User activated successfully"}

async def refresh_token_view(
    db: AsyncSession,
    request: Request,
    response: Response
):
    # This function assumes the refresh token is sent via cookies
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_email = payload.get("sub")
        
        if user_email is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            subject=user_email, expires_delta=access_token_expires
        )
        
        response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=False, samesite="lax")
        return {"message": "Access token refreshed"}
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")