from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import generate_token, hash_token
from app.db.models import AuthToken, User

router = APIRouter(prefix="/auth", tags=["auth"])


class SetupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)


def build_token_response(raw_token: str, user: User) -> dict:
    return {"token": raw_token, "user": {"id": str(user.id), "name": user.name}}


@router.post("/setup")
async def setup_auth(request: SetupRequest, session: AsyncSession = Depends(get_db)):
    stmt = select(User)
    result = await session.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    new_user = User(name=request.name, timezone=request.timezone)
    session.add(new_user)
    await session.flush()

    raw_token = generate_token()
    auth_token = AuthToken(user_id=new_user.id, token_hash=hash_token(raw_token))
    session.add(auth_token)
    await session.commit()

    return build_token_response(raw_token, new_user)


@router.post("/login")
async def login_auth(request: LoginRequest, session: AsyncSession = Depends(get_db)):
    # Find user by name
    stmt = select(User).where(User.name == request.name)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        user = User(name=request.name, timezone="UTC")
        session.add(user)
        await session.flush()

    await session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))

    raw_token = generate_token()
    auth_token = AuthToken(user_id=user.id, token_hash=hash_token(raw_token))
    session.add(auth_token)
    await session.commit()

    return build_token_response(raw_token, user)
