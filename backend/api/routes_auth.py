from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import secrets
import hashlib
from uuid import UUID

from db.session import get_db
from db.models import User, AuthToken

router = APIRouter(prefix="/auth", tags=["auth"])

class SetupRequest(BaseModel):
    name: str
    timezone: str

@router.post("/setup")
async def setup_auth(request: SetupRequest, session: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.name == request.name)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        # Create User
        user = User(
            name=request.name,
            timezone=request.timezone
        )
        session.add(user)
        await session.flush()

    # Generate token
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    auth_token = AuthToken(
        user_id=user.id,
        token_hash=token_hash
    )
    session.add(auth_token)
    await session.commit()

    return {"token": raw_token}
