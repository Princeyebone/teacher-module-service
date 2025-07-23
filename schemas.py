from pydantic import BaseModel, EmailStr, Field
from datetime import date, time
from typing import Optional, List
from uuid import UUID

class TokenData(BaseModel):
    email:str | None = None
    role:str | None = None
    school_id:UUID | None = None
    individual_id:UUID | None = None

# Existing models
class TeacherRegistrationRequest(BaseModel):
    name: str
    email: EmailStr
    contact: str
    date_of_birth: str
    nationality: str
    location: str

class TeacherBase(BaseModel):
    individual_id: UUID
    employment_status: str
    subjects: str
    email: EmailStr
    qualifications: str
    rating: int
    bio: str

class TeacherCreate(TeacherBase):
    pass

class TeacherRead(TeacherBase):
    display_name:Optional[str] = None
    qualification:Optional[str] = None
    qualification_year:Optional[int] = None
    qualification_institution:Optional[str] = None
    work_institution:Optional[str] = None
    subjects:Optional[str] = None    
    bio:Optional[str] = None

class TeacherUpdate(BaseModel):
    display_name:Optional[str] = None
    qualification:Optional[str] = None
    qualification_year:Optional[int] = None
    qualification_institution:Optional[str] = None
    work_institution:Optional[str] = None
    country:Optional[str] = None
    subjects:Optional[str] = None    
    bio:Optional[str] = None

class TeacherProfileRead(BaseModel):
    id: Optional[UUID] = None
    no_id: Optional[int] = None
    school_id: Optional[UUID] = None
    individual_id: Optional[UUID] = None
    display_name: Optional[str] = None
    qualification: Optional[str] = None
    qualification_year: Optional[int] = None
    qualification_institution: Optional[str] = None
    work_institution: Optional[str] = None
    subjects: Optional[str] = None
    bio: Optional[str] = None
    rating: Optional[int] = None
    role: Optional[str] = None

    class Config:
        from_attributes = True
    

class EmailSync(BaseModel):
    old_email: EmailStr
    new_email: EmailStr

class TeacherProfileResponse(BaseModel):
    name: str
    email: str
    qualifications: Optional[str] 
    bio: Optional[str] = None
    subjects: Optional[str] = None
    employment_status: Optional[str] = None
    rating: Optional[int] = None
    school_id: Optional[UUID] = None

    class Config:
        from_attributes = True

class TimeTableItem(BaseModel):
    weekday: str
    pupils: str
    subject: str
    start_time: time
    end_time: time
    location: Optional[str] = None

class TimeTableEntry(BaseModel):
    items:List[TimeTableItem]
    
class AcademicCalendarEntry(BaseModel):
    teacher_id:UUID
    calender_id:int
    semester_name: str
    start_date: date
    mid_semester_break_start_date:Optional[date] = None
    mid_semester_break_start_date:Optional[date] = None
    end_date: date
    academic_level: Optional[str] = None
    event_name: Optional[str] = None
    event_start_day: Optional[date] = None
    event_end_date: Optional[date] = None
    event_start_time: Optional[time] = None
    event_end_time: Optional[time] = None
    is_holiday: Optional[bool] = None
    requires_no_classes: Optional[bool] = None

class AcademicCalendarPublic(BaseModel):
    teacher_id: Optional[UUID] = None
    semester_name: str
    academic_level: Optional[str] = None
    midsem_exams_date: Optional[date] = None
    revision_start_date: Optional[date] = None
    semester_start_date: date
    mid_semester_break_start_date: Optional[date] = None
    mid_semester_break_end_date:Optional[date] = None
    semester_end_date: date

class CalendarEventPublic(BaseModel):
    event_name: Optional[str] = None
    event_start_date: Optional[date] = None
    event_end_date: Optional[date]  = None
    event_start_time: Optional[time] = None
    event_end_time: Optional[time] = None
    is_holiday: Optional[bool] = None
    requires_no_classes: Optional[bool] = None

class UpdateCalendarResponse(BaseModel):
    academic_calendar: AcademicCalendarPublic
    calendar_events: List[CalendarEventPublic]

# Semester Planner Schemas
class SubjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class SubjectCreate(SubjectBase):
    pass

class SubjectRead(SubjectBase):
    id: UUID
    teacher_id: UUID

    class Config:
        from_attributes = True

class TimetableEntryBase(BaseModel):
    subject_id: UUID
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    classroom: Optional[str] = None

class TimetableEntryCreate(TimetableEntryBase):
    pass

class TimetableEntryRead(TimetableEntryBase):
    id: UUID
    teacher_id: UUID

    class Config:
        from_attributes = True

class AcademicEventBase(BaseModel):
    title: str
    start_date: date
    end_date: date
    event_type: str = Field(..., description="holiday, break, exam, event")
    description: Optional[str] = None

class AcademicEventCreate(AcademicEventBase):
    pass

class AcademicEventRead(AcademicEventBase):
    id: UUID
    teacher_id: UUID

    class Config:
        from_attributes = True

class MaterialRequest(BaseModel):
    subject_id: UUID
    topic: str
    grade_level: str
    guidance: Optional[str] = None
    objectives: Optional[str] = None
    duration_minutes: Optional[int] = Field(60, ge=15, le=240)

class GeneratedMaterial(BaseModel):
    type: str
    content: str
    title: str

class MaterialResponse(BaseModel):
    topic: str
    lesson_plan: str
    presentations: List[GeneratedMaterial] = []
    worksheets: List[GeneratedMaterial] = []
    videos: List[GeneratedMaterial] = []
    images: List[GeneratedMaterial] = []
    questions: List[GeneratedMaterial] = []

# Full Timetable Response
class TeacherTimetableResponse(BaseModel):
    subjects: List[SubjectRead]
    timetable_entries: List[TimetableEntryRead]
    academic_events: List[AcademicEventRead]

# UI Data Formats
class TimetableSlot(BaseModel):
    id: UUID
    subject_name: str
    start_time: str
    end_time: str
    classroom: Optional[str] = None

class DaySchedule(BaseModel):
    day: str
    slots: List[TimetableSlot]

class WeeklyTimetable(BaseModel):
    monday: List[TimetableSlot]
    tuesday: List[TimetableSlot]
    wednesday: List[TimetableSlot]
    thursday: List[TimetableSlot]
    friday: List[TimetableSlot]
    saturday: List[TimetableSlot]
    sunday: List[TimetableSlot]

# Calendar View Models
class CalendarEvent(BaseModel):
    id: UUID
    title: str
    start: date
    end: date
    type: str
    description: Optional[str] = None
    color: Optional[str] = None  # For UI differentiation

    class Config:
        from_attributes = True
