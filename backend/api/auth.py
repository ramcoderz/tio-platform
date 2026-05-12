from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Any

from backend.db.session import get_db
from backend.models.entities import User
from backend.utils.auth import get_password_hash, verify_password, create_access_token, decode_token
from backend.config.settings import get_settings

settings = get_settings()
router = APIRouter()

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/register")
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    stmt = select(User).where((User.username == payload.username) | (User.email == payload.email))
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    new_user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="admin" if "admin" in payload.email else "user"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    token = create_access_token({"sub": new_user.username, "uid": new_user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": new_user.id, "username": new_user.username, "role": new_user.role}}

@router.post("/login")
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == payload.username)
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.username, "uid": user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "username": user.username, "role": user.role}}

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

auth_scheme = HTTPBearer()

@router.get("/me")
async def get_me(creds: HTTPAuthorizationCredentials = Depends(auth_scheme), db: AsyncSession = Depends(get_db)):
    token = creds.credentials
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        stmt = select(User).where(User.username == username)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
        return {"id": user.id, "username": user.username, "role": user.role, "email": user.email}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
