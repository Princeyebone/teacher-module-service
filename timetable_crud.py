from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from model import TeacherProfile, WeeklyTimeTable, TempExtract, AcademicCalendar
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select, delete
from schemas import TimeTableEntry, TimeTableItem
from uuid import UUID
from schedule_utils import check_and_trigger_session_generation

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

@router.post("/save-timetable")
async def save_timetable(
    data: TimeTableEntry,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Fused endpoint that either creates new timetable entries or updates existing ones.
    If existing timetable data is found for the teacher, it will be updated.
    If no existing data is found, new entries will be created.
    Also cleans up any temporary data from TempExtract table.
    """
    try:
        # Check if there's temporary data that should be cleaned up
        temp_extract = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == current_teacher.id,
                TempExtract.type == "timetable"
            )
        )).scalar_one_or_none()
        
        # Check if existing timetable entries exist for this teacher
        existing_entries = (await db.execute(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )).scalars().all()
        
        operation_type = "create"
        
        if existing_entries:
            # Update existing entries instead of deleting all and recreating
            operation_type = "update"
            
            # Create a mapping of existing entries by their unique characteristics
            existing_map = {(entry.weekday, entry.start_time, entry.subject): entry for entry in existing_entries}
            
            # Track which existing entries have been updated
            updated_entries = set()
            
            # Update or create entries
            for item in data.items:
                item_dict = item.model_dump(exclude_unset=True)
                key = (item.weekday, item.start_time, item.subject)
                
                if key in existing_map:
                    # Update existing entry
                    entry = existing_map[key]
                    for field, value in item_dict.items():
                        if field != 'id' and hasattr(entry, field):
                            setattr(entry, field, value)
                    db.add(entry)
                    updated_entries.add(key)
                else:
                    # Create new entry
                    new_entry = WeeklyTimeTable(
                        teacher_id=current_teacher.id,
                        **item_dict
                    )
                    db.add(new_entry)
            
            # Delete entries that weren't in the new data
            for key, entry in existing_map.items():
                if key not in updated_entries:
                    await db.delete(entry)
        else:
            # Create new entries from the provided data
            timetable_entries = [
                WeeklyTimeTable(
                    teacher_id=current_teacher.id,
                    **item.model_dump(exclude_unset=True)
                )
                for item in data.items
            ]

            for entry in timetable_entries:
                db.add(entry)
        
        # If there was temporary data, delete it
        if temp_extract:
            await db.delete(temp_extract)
            
        await db.commit()

        # Get the latest list of entries
        final_entries = (await db.execute(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )).scalars().all()
        
        # Add source indicator for frontend
        result = []
        for entry in final_entries:
            entry_dict = entry.model_dump()
            result.append(entry_dict)
            
        response_data = {
            "items": result,
            "operation": operation_type,
            "data_source": "weekly_timetable",
            "temp_data_cleaned": temp_extract is not None  # Indicates if temp data was cleaned up
        }
        
        # Trigger session generation after successful save
        # We do this after the main transaction is complete to avoid session issues
        from schedule_utils import trigger_session_generation_after_save
        await trigger_session_generation_after_save(str(current_teacher.id))
        
        return response_data
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error saving timetable: {str(e)}"
        )

@router.get("/get-timetable")  # Removed response_model to allow custom response structure
async def get_timetable(
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
            
            # Return the data with source information
            return {
                "items": timetable_data,
                "data_source": "temp_extract"
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

@router.delete("/delete-timetable")
async def delete_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        # Check if there's temporary data that should be cleaned up
        temp_extract = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == current_teacher.id,
                TempExtract.type == "timetable"
            )
        )).scalar_one_or_none()
        
        result = await db.execute(
            delete(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )
        await db.commit()
        
        # If there was temporary data, delete it
        if temp_extract:
            await db.delete(temp_extract)
            await db.commit()
        
        # Check if any rows were deleted (if supported by the backend)
        if hasattr(result, 'rowcount') and result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No timetable entries found for this teacher"
            )
        return {
            "message": "Timetable deleted successfully",
            "temp_data_cleaned": temp_extract is not None  # Indicates if temp data was cleaned up
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting timetable: {str(e)}"
        )