from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, Optional
from model import TeacherProfile, WeeklyTimeTable, TempExtract, AcademicCalendar
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select, delete
from schemas import TimeTableEntry, TimeTableItem
from uuid import UUID
from schedule_utils import check_and_trigger_session_generation
from logger import logger

router = APIRouter(prefix="/api")

@router.get("/subjects")
async def subjects(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        # First check if there's temporary extracted data
        temp_extract = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == current_teacher.id,
                TempExtract.type == "timetable"
            )
        )).scalar_one_or_none()
        
        if temp_extract:
            # Use temporary data
            timetable_data = temp_extract.data.get("entries", [])
            if not timetable_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No timetable found for this teacher"
                )
            
            # Extract subjects and pupils from the temporary timetable entries
            subjects_with_pupils = [
                {
                    "subject": entry.get("subject", ""),
                    "pupils": entry.get("pupils", "")  # Assuming `pupils` is a field or relationship in WeeklyTimeTable
                }
                for entry in timetable_data if entry.get("subject")
            ]
            
            # Add source indicator for frontend
            return {
                "subjects": subjects_with_pupils,
                "data_source": "temp_extract"  # Indicates data came from temp table
            }
        else:
            # Fall back to permanent timetable data
            timetable = (await db.execute(
                select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
            )).scalars().all()
            if not timetable:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No timetable found for this teacher"
                )
            
            # Extract subjects and pupils from the timetable entries
            subjects_with_pupils = [
                {
                    "subject": entry.subject,
                    "pupils": entry.pupils  # Assuming `pupils` is a field or relationship in WeeklyTimeTable
                }
                for entry in timetable if entry.subject
            ]
            
            # Add source indicator for frontend
            return {
                "subjects": subjects_with_pupils,
                "data_source": "weekly_timetable"  # Indicates data came from permanent table
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving subjects: {str(e)}"
        )

class SingleTimeTableRequest(TimeTableItem):
    id: Optional[int] = None

@router.post("/save-timetable")
async def save_timetable(
    data: SingleTimeTableRequest,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to create or update a single timetable entry.
    If 'id' is provided, it updates the existing entry.
    If 'id' is not provided, it creates a new entry.
    """
    # Prepare response data
    item_response = None
    operation_type = "create"
    teacher_id_str = str(current_teacher.id)
    teacher_country = current_teacher.country or "Ghana"
    
    try:
        entry = None

        if data.id:
            # Update existing entry
            stmt = select(WeeklyTimeTable).where(
                WeeklyTimeTable.id == data.id,
                WeeklyTimeTable.teacher_id == current_teacher.id
            )
            result = await db.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if entry:
                operation_type = "update"
                # Update fields
                entry_data = data.model_dump(exclude={'id', 'data_source'}, exclude_unset=True)
                for field, value in entry_data.items():
                    if hasattr(entry, field):
                        setattr(entry, field, value)
                db.add(entry)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Timetable entry with id {data.id} not found"
                )
        else:
            # Create new entry
            entry = WeeklyTimeTable(
                teacher_id=current_teacher.id,
                weekday=data.weekday,
                pupils=data.pupils,
                subject=data.subject,
                start_time=data.start_time,
                end_time=data.end_time,
                location=data.location,
                data_source=data.data_source
            )
            db.add(entry)
            
        await db.commit()
        await db.refresh(entry)

        # Manually construct response to avoid potential lazy load issues
        item_response = {
            "id": entry.id,
            "weekday": entry.weekday,
            "pupils": entry.pupils,
            "subject": entry.subject,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "location": entry.location,
            "edu_sys": entry.edu_sys,
            "edu_lvl": entry.edu_lvl
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error saving timetable: {str(e)}"
        )
    
    # Trigger session generation AFTER database transaction is complete
    # This happens outside the db transaction context to avoid greenlet conflicts
    from enque_task import enqueue_schedule_generation
    try:
        job_id = await enqueue_schedule_generation(teacher_id_str, teacher_country)
        if job_id:
            logger.info(f"✅ Session generation job enqueued: {job_id}")
        else:
            logger.warning(f"⚠️ Session generation job returned None (check if both timetable and calendar exist)")
    except Exception as e:
        logger.error(f"❌ Failed to enqueue session generation: {e}")
        # Don't fail the request if background job fails

    return {
        "message": "Timetable saved successfully",
        "item": item_response,
        "operation": operation_type
    }

@router.get("/get-timetable")  # Removed response_model to allow custom response structure
async def get_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        # Strictly read from permanent timetable data
        timetable = (await db.execute(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )).scalars().all()

        if not timetable:
            return {
                "items": [],
                "data_source": "weekly_timetable"
            }
        
        # Convert entries to dict format
        result = []
        for entry in timetable:
            entry_dict = entry.model_dump()
            result.append(entry_dict)
            
        return {
            "items": result,
            "data_source": "weekly_timetable"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve timetable: {str(e)}"
        )

@router.delete("/delete-timetable/{entry_id}")
async def delete_timetable(
    entry_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a single timetable entry by its ID.
    """
    try:
        stmt = select(WeeklyTimeTable).where(
            WeeklyTimeTable.id == entry_id,
            WeeklyTimeTable.teacher_id == current_teacher.id
        )
        result = await db.execute(stmt)
        entry = result.scalar_one_or_none()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timetable entry not found"
            )

        await db.delete(entry)
        await db.commit()
        
        # Trigger session generation directly like other file handlers
        from enque_task import enqueue_schedule_generation
        try:
            job_id = await enqueue_schedule_generation(str(current_teacher.id), current_teacher.country or "Ghana")
            if job_id:
                logger.info(f"✅ Session generation job enqueued: {job_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to enqueue session generation: {e}")
        
        return {
            "message": "Timetable entry deleted successfully",
            "id": entry_id
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting timetable entry: {str(e)}"
        )

@router.delete("/delete-all-timetable")
async def delete_all_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """
    Delete all timetable entries for the current teacher.
    """
    try:
        # Check if there are any entries to delete
        stmt = select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        result = await db.execute(stmt)
        entries = result.scalars().all()
        
        if not entries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No timetable entries found for this teacher"
            )

        # Delete all entries
        await db.execute(
            delete(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )
        await db.commit()
        
        # Trigger session generation directly like other file handlers
        from enque_task import enqueue_schedule_generation
        try:
            job_id = await enqueue_schedule_generation(str(current_teacher.id), current_teacher.country or "Ghana")
            if job_id:
                logger.info(f"✅ Session generation job enqueued: {job_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to enqueue session generation: {e}")
        
        return {
            "message": "All timetable entries deleted successfully",
            "count": len(entries)
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting all timetable entries: {str(e)}"
        )