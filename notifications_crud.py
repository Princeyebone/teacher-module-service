from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from typing import List
from database import get_db
from model import TeacherNotification
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID
from dependencies import get_current_teacher

router = APIRouter(tags=["Notifications"])

@router.get("/notifications", response_model=List[TeacherNotification])
async def get_notifications(
    current_teacher=Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
    unread_only: bool = False
):
    query = select(TeacherNotification).where(TeacherNotification.teacher_id == current_teacher.id)
    if unread_only:
        query = query.where(TeacherNotification.is_read == False)
    notifications = (await db.execute(query.order_by(TeacherNotification.created_at.desc()))).scalars().all()
    return notifications

@router.get("/notifications/latest", response_model=List[TeacherNotification])
async def get_latest_notifications(
    current_teacher=Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
    limit: int = 10
):
    """
    Get the latest notifications for the current teacher.
    By default, returns the 10 most recent notifications.
    """
    query = select(TeacherNotification)\
        .where(TeacherNotification.teacher_id == current_teacher.id)\
        .order_by(TeacherNotification.created_at.desc())\
        .limit(limit)
    
    notifications = (await db.execute(query)).scalars().all()
    return notifications

@router.post("/notifications/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: UUID,
    current_teacher=Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    notification = await db.get(TeacherNotification, notification_id)
    if not notification or notification.teacher_id != current_teacher.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.add(notification)
    await db.commit()
    return {"status": "success", "message": "Notification marked as read."}

@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_teacher=Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    notifications = (await db.execute(
        select(TeacherNotification).where(
            TeacherNotification.teacher_id == current_teacher.id,
            TeacherNotification.is_read == False
        )
    )).scalars().all()

    for n in notifications:
        n.is_read = True
        db.add(n)
    await db.commit()

    return {"status": "success", "message": f"{len(notifications)} notifications marked as read."}