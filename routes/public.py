from __future__ import annotations

import logging
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.db import get_db
from app.models import TeamMember, InvestorContact, PartnerContact
from app.schemas.public import (
    TeamMemberSchema, 
    InvestorContactCreate, 
    PartnerContactCreate, 
    NewsletterSubscribe
)
from app.redis_client import get_redis
from app.services.notifications import NotificationService, get_notification_service

router = APIRouter(prefix="/api/v1/public", tags=["Public"])
logger = logging.getLogger(__name__)

@router.get("/team", response_model=List[TeamMemberSchema])
async def get_team(db: AsyncSession = Depends(get_db)):
    """
    Returns the list of active team members.
    """
    stmt = (
        select(TeamMember)
        .where(TeamMember.is_active == True)
        .order_by(TeamMember.sort_order.asc(), TeamMember.created_at.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/investor-contact", status_code=status.HTTP_201_CREATED)
async def create_investor_contact(
    request: Request,
    data: InvestorContactCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    notifications: NotificationService = Depends(get_notification_service)
):
    """
    Accepted investor contact form.
    Includes rate limiting, honeypot protection, and duplicate prevention.
    """
    # 1. Honeypot check
    if data.hp:
        logger.warning(f"Honeypot filled by {request.client.host if request.client else 'unknown'}")
        return {"ok": True}

    # 2. Rate limiting (5 requests / 600 seconds)
    ip = request.client.host if request.client else "unknown"
    rate_key = f"rate_limit:investor_contact:{ip}"
    current_count = await redis.get(rate_key)
    if current_count and int(current_count) >= 5:
        logger.warning(f"Rate limit exceeded for investor-contact by IP: {ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Too many requests. Please try again later."}
        )
    
    await redis.incr(rate_key)
    if not current_count:
        await redis.expire(rate_key, 600)

    # 3. Duplicate prevention (7 days by email)
    seven_days_ago_dt = datetime.now() - timedelta(days=7)
    stmt = select(InvestorContact).where(
        and_(
            InvestorContact.email == data.email,
            InvestorContact.created_at >= seven_days_ago_dt
        )
    )
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        logger.info(f"Duplicate investor contact ignored for email: {data.email}")
        return {"ok": True}

    # 4. Save to DB
    new_contact = InvestorContact(
        name=data.name,
        company=data.company,
        email=data.email,
        linkedin_url=str(data.linkedin) if data.linkedin else None,
        ip=ip,
        user_agent=request.headers.get("User-Agent"),
        source="investors_page"
    )
    db.add(new_contact)
    await db.commit()
    
    import html
    message = (
        f"🚀 <b>New Investor Lead</b>\n"
        f"Name: {html.escape(data.name)}\n"
        f"Company: {html.escape(data.company or 'N/A')}\n"
        f"Email: {html.escape(data.email)}\n"
        f"LinkedIn: {html.escape(str(data.linkedin) or 'N/A')}"
    )
    # We await it here. In a high-load scenario, we could use BackgroundTasks.
    await notifications.notify(topic="investors", message=message, data=data)
    
    logger.info(f"New investor contact saved and notified: {data.email}")
    return {"ok": True}


@router.post("/partner-contact", status_code=status.HTTP_201_CREATED)
async def create_partner_contact(
    request: Request,
    data: PartnerContactCreate,
    db: AsyncSession = Depends(get_db),
    notifications: NotificationService = Depends(get_notification_service)
):
    """
    Partner contact form. Now saves to DB and notifies.
    """
    if data.hp:
        return {"ok": True}
    
    # 1. Save to DB
    contact = PartnerContact(
        name=data.name,
        company=data.company,
        email=data.email,
        website_url=str(data.website) if data.website else None,
        message=data.message,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(contact)
    await db.commit()
    
    # 2. Notify
    message = (
        f"🤝 *New Partner Lead*\n"
        f"Name: {data.name}\n"
        f"Company: {data.company or 'N/A'}\n"
        f"Email: {data.email}\n"
        f"Website: {data.website or 'N/A'}\n"
        f"Message: {data.message}"
    )
    await notifications.notify(topic="partners", message=message, data=data.model_dump())
    return {"ok": True}


@router.post("/newsletter-subscribe", status_code=status.HTTP_201_CREATED)
async def newsletter_subscribe(
    request: Request,
    data: NewsletterSubscribe,
    notifications: NotificationService = Depends(get_notification_service)
):
    """
    Newsletter subscription skeleton.
    """
    if data.hp:
        return {"ok": True}
    
    message = f"📧 *New Newsletter Subscription*: {data.email}"
    await notifications.notify(topic="newsletter", message=message, data=data.model_dump())
    return {"ok": True}
