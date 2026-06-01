"""Registrering, inloggning och nuvarande användare.

Vid registrering skapas en användare + en personlig organisation + ett
ägarmedlemskap, så att nya projekt direkt har ett org att höra till.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user
from ..dto import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..models import Membership, Organization, User
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    exists = await session.scalar(select(User).where(User.email == body.email))
    if exists:
        raise HTTPException(409, "E-postadressen är redan registrerad")

    user = User(email=body.email, name=body.name, hashed_password=hash_password(body.password))
    session.add(user)
    await session.flush()  # tilldela user.id

    org = Organization(name=body.org_name or f"{body.name}s workspace", owner_id=user.id)
    session.add(org)
    await session.flush()  # tilldela org.id

    session.add(Membership(user_id=user.id, org_id=org.id, role="owner"))

    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Fel e-post eller lösenord")
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
