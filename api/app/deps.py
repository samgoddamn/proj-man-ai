"""Auth-dependencies: aktuell användare och projekt-åtkomstkontroll (org-scoping)."""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Membership, Project, User
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        user_id = decode_access_token(creds.credentials)
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "Ogiltig eller utgången token")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Användaren finns inte")
    return user


async def user_org_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    rows = await session.scalars(select(Membership.org_id).where(Membership.user_id == user.id))
    return set(rows)


async def primary_org_id(session: AsyncSession, user: User) -> uuid.UUID:
    """Org som nya projekt knyts till — den användaren äger (skapas vid register)."""
    from .models import Organization

    org_id = await session.scalar(
        select(Organization.id).where(Organization.owner_id == user.id).limit(1)
    )
    if org_id is None:  # fallback: första medlemskapet
        org_id = await session.scalar(
            select(Membership.org_id).where(Membership.user_id == user.id).limit(1)
        )
    if org_id is None:
        raise HTTPException(400, "Användaren saknar organisation")
    return org_id


async def ensure_project_access(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Project:
    """Hämta projektet och verifiera att användaren tillhör dess organisation.

    Använd som dependency i routes med {project_id} i pathen. Returnerar projektet
    så att routen slipper hämta det igen.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Projekt hittades inte")
    if project.org_id not in await user_org_ids(session, user):
        raise HTTPException(403, "Du har inte åtkomst till detta projekt")
    return project
