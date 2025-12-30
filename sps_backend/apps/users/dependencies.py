from fastapi import Request, HTTPException, Cookie
import jwt
from config import settings

# Note: Using Cookie(...) directly is a 2025 best practice for HttpOnly tokens
async def is_authenticated(request: Request, access_token: str = Cookie(None)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
