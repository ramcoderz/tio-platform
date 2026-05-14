from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
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

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme), db: AsyncSession = Depends(get_db)) -> User:
    token = creds.credentials
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        stmt = select(User).where(User.username == username)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id, 
        "username": user.username, 
        "role": user.role, 
        "email": user.email,
        "theme": user.theme,
        "private_inference": bool(user.private_inference)
    }

class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    theme: str | None = None
    private_inference: bool | None = None

@router.put("/me")
async def update_me(payload: UserUpdate, creds: HTTPAuthorizationCredentials = Depends(auth_scheme), db: AsyncSession = Depends(get_db)):
    token = creds.credentials
    data = decode_token(token)
    user_id = data.get("uid")
    
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.username:
        # Check uniqueness
        stmt = select(User).where(User.username == payload.username)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = payload.username
        
    if payload.email:
        # Check uniqueness
        stmt = select(User).where(User.email == payload.email)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = payload.email
        
    if payload.theme is not None:
        user.theme = payload.theme
        
    if payload.private_inference is not None:
        user.private_inference = 1 if payload.private_inference else 0
        
    await db.commit()
    await db.refresh(user)
    
    # Generate new token if username changed
    new_token = create_access_token({"sub": user.username, "uid": user.id})
    return {
        "access_token": new_token,
        "user": {
            "id": user.id, 
            "username": user.username, 
            "role": user.role, 
            "email": user.email,
            "theme": user.theme,
            "private_inference": bool(user.private_inference)
        }
    }

@router.delete("/me")
async def delete_account(creds: HTTPAuthorizationCredentials = Depends(auth_scheme), db: AsyncSession = Depends(get_db)):
    user = await get_current_user(creds, db)
    user_id = user.id
    
    from backend.utils.cleanup import deep_delete_chatbot
    from backend.models.entities import Chatbot
    
    # 1. Delete all chatbots owned by the user (deep cleanup)
    stmt = select(Chatbot).where(Chatbot.user_id == user_id)
    chatbots = (await db.execute(stmt)).scalars().all()
    for cb in chatbots:
        await deep_delete_chatbot(cb.id, db)
    
    # 2. Cleanup orphaned conversations/messages for this user
    from backend.models.entities import Conversation, Message
    stmt_conv = select(Conversation).where(Conversation.user_id == user_id)
    user_convs = (await db.execute(stmt_conv)).scalars().all()
    for conv in user_convs:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.delete(conv)
    
    # 3. Delete user profile
    await db.delete(user)
    await db.commit()
    
    return {"status": "account_deleted"}
