from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from model import TeacherProfile
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import Session, select, delete
from schemas import TimeTableEntry, TimeTableItem
from model import WeeklyTimeTable
from uuid import UUID



router = APIRouter(prefix="/api")


@router.post("/create-timetable")
async def create_timetable(
    data: TimeTableEntry,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    try:
        records = [
            {**item.model_dump(), "teacher_id": current_teacher.id}
            for item in data.items
        ]

        db.bulk_insert_mappings(WeeklyTimeTable, records)
        db.commit()
        return data.items

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating timetable: {e}"
        )

@router.get("/get-timetable", response_model=list[TimeTableItem])
async def get_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
       
        timetable=db.exec(select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)).all()

        if not timetable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No timetable found for this teacher"
            )
        return timetable
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve timetable: {e}"
        )

@router.patch("/update-timetable", response_model=list[TimeTableItem])
async def update_timetable(
    data: TimeTableEntry,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
        # Fetch existing entries for this teacher
        existing_entries = db.exec(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        ).all()
        existing_entries_dict = {e.id: e for e in existing_entries if e.id is not None}

        # Build a set of IDs from the payload (if they exist)
        payload_ids = set()
        updated_entries = []
        for item in data.items:
            item_data = item.model_dump(exclude_unset=True)
            item_id = item_data.get("id")
            if item_id and item_id in existing_entries_dict:
                # Update existing entry
                db_entry = existing_entries_dict[item_id]
                for key, value in item_data.items():
                    if key != "id":
                        setattr(db_entry, key, value)
                db.add(db_entry)
                updated_entries.append(db_entry)
                payload_ids.add(item_id)
            else:
                # New entry
                new_entry = WeeklyTimeTable(
                    teacher_id=current_teacher.id, **item_data
                )
                db.add(new_entry)
                db.commit()
                db.refresh(new_entry)
                updated_entries.append(new_entry)

        # Delete entries that are not in the payload
        for entry in existing_entries:
            if entry.id not in payload_ids:
                db.delete(entry)
        db.commit()

        # Get the latest list of entries
        final_entries = db.exec(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        ).all()

        return final_entries

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating timetable: {e}"
        )

@router.delete("/delete-timetable")
async def delete_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
        result = db.exec(
            delete(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )
        db.commit()
        # result.rowcount may not always be available depending on backend, so double-check
        if hasattr(result, 'rowcount'):
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No timetable entries found for this teacher"
                )
        # Optionally, you can also check if any rows remain
        return {"message": "Timetable deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting timetable: {e}"
        )
