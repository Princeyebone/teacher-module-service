from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlmodel import Session
from typing import Optional
from datetime import date
from model import AcademicCalender, CalenderEvent
from database import get_db
from dependencies import get_current_teacher
from model import TeacherProfile
from typing import Annotated
from schemas import TimeTableEntry
from model import WeeklyTimeTable

router = APIRouter()


@router.post("/timetable/upload")
async def upload_weekly_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],   
    db: Session = Depends(get_db),
    data=TimeTableEntry
):
    try:
            
     timetable_entry = WeeklyTimeTable(
                teacher_id=current_teacher.id,
                weekday=data.weekday,
                pupils=data.pupils,
                subject=data.subject,
                start_time=data.start_time,
                end_time=data.end_time,
                location=data.location
            )
     db.add(timetable_entry)
     db.commit()
     return {"message": "Weekly timetable uploaded successfully."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error uploading timetable: {str(e)}")
    

# This function will talk to AI to extract data
async def extract_calendar_data_with_ai(file: UploadFile, semester_name: str, level: str) -> dict:
    # Integrate with your AI provider (e.g. Gemini, GPT-4o)
    # Your prompt should include semester_name and level to filter the extraction
    raise NotImplementedError("Plug in your AI logic here.")


@router.post("/calendar/upload")
async def upload_academic_calendar(
    current_teacher:Annotated[TeacherProfile, Depends(get_current_teacher)],
    file: UploadFile = File(...),
    semester_name: str = Form(...),
    level: str = Form(...),
    session: Session = Depends(get_db)
):
    try:
        # AI extracts calendar data relevant to that semester and level
        extracted = await extract_calendar_data_with_ai(file, semester_name, level)

        cal = AcademicCalender(
            teacher_id=current_teacher.id,
            semester_name=semester_name,
            level=level,
            start_date=extracted["start_date"],
            end_date=extracted["end_date"]
        )
        session.add(cal)
        session.commit()
        session.refresh(cal)

        for event in extracted["events"]:
            ev = CalenderEvent(
                calender_id=cal.id,
                event_name=event["event_name"],
                event_start_day=event["event_start_day"],
                event_end_date=event["event_end_date"],
                event_start_time=event.get("event_start_time"),
                event_end_time=event.get("event_end_time"),
                is_holiday=event.get("is_holiday", True),
                requires_no_classes=event.get("requires_no_classes", True)
            )
            session.add(ev)

        session.commit()
        return {"message": "Academic calendar uploaded and saved successfully.", "calendar_id": cal.id}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error uploading calendar: {str(e)}")
