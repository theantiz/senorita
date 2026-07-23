from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import secrets
import hashlib


from db.session import get_db
from db.models import User, AuthToken

router = APIRouter(prefix="/auth", tags=["auth"])

class SetupRequest(BaseModel):
    name: str
    timezone: str

@router.post("/setup")
async def setup_auth(request: SetupRequest, session: AsyncSession = Depends(get_db)):
    stmt = select(User)
    result = await session.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    # Create User
    new_user = User(
        name=request.name,
        timezone=request.timezone
    )
    session.add(new_user)
    await session.flush()

    # Generate token
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    auth_token = AuthToken(
        user_id=new_user.id,
        token_hash=token_hash
    )
    session.add(auth_token)
    await session.commit()

    return {"token": raw_token}
