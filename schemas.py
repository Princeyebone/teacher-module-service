from pydantic import BaseModel, EmailStr, Field
from datetime import date, time
from typing import Optional, List
from uuid import UUID

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
    employment_status: Optional[str] = None
    subjects: Optional[str] = None
    qualifications: Optional[str] = None
    rating: Optional[int] = None
    bio: Optional[str] = None

class TeacherUpdate(BaseModel):
    employment_status: Optional[str] = None
    subjects: Optional[str] = None
    qualifications: Optional[str] = None
    bio: Optional[str] = None

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
