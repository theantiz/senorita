import hashlib
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuthToken, User
from app.db.session import get_db

bearer_scheme = HTTPBearer()


def generate_token() -> str:
    """Return a high-entropy bearer token suitable for local auth."""
    return secrets.token_hex(32)


def hash_token(raw_token: str) -> str:
    """Hash bearer tokens before comparing or storing them."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    token_hash = hash_token(credentials.credentials)
    stmt = select(AuthToken).where(AuthToken.token_hash == token_hash)
    result = await session.execute(stmt)
    auth_token = result.scalars().first()

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt_user = select(User).where(User.id == auth_token.user_id)
    result_user = await session.execute(stmt_user)
    user = result_user.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_current_user_ws(
    websocket: "fastapi.WebSocket",
    session: AsyncSession = Depends(get_db),
) -> User:
    import fastapi

    token = websocket.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    else:
        token = websocket.query_params.get("token")

    if not token:
        raise fastapi.HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")

    token_hash = hash_token(token)
    stmt = select(AuthToken).where(AuthToken.token_hash == token_hash)
    result = await session.execute(stmt)
    auth_token = result.scalars().first()

    if not auth_token:
        raise fastapi.HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    stmt_user = select(User).where(User.id == auth_token.user_id)
    result_user = await session.execute(stmt_user)
    user = result_user.scalars().first()

    if not user:
        raise fastapi.HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
