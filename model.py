from sqlmodel import SQLModel, Field, Column
from typing import Optional, List
from sqlalchemy.dialects.postgresql import JSONB
from uuid import UUID
import uuid
from enum import Enum
from datetime import date, time,datetime,timezone
from uuid import uuid4


class UserRole(str, Enum):
    SUPERUSER = "SUPERUSER"
    ADMIN = "ADMIN"
    SCH_TEACHER = "sch_teacher"
    TEACHER = "TEACHER"

class TeacherProfile(SQLModel, table=True):
    no_id:Optional[int] = Field(default=None, index=True)
    id:Optional[UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    school_id:Optional[UUID] = None
    individual_id:Optional[UUID] = None
    
    display_name:Optional[str] = None
    qualification:Optional[str] = None
    qualification_year:Optional[int] = None
    qualification_institution:Optional[str] = None
    work_institution:Optional[str] = None
    subjects:Optional[str] = None    
    bio:Optional[str] = None
    rating:Optional[int] = None
    role: UserRole = Field(default=UserRole.SCH_TEACHER)
    country:Optional[str]=None 


class AcademicCalendar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    semester_name: str
    academic_level: Optional[str] = None
    semester_start_date: date
    midsem_exams_date:Optional[date] = None
    mid_semester_break_start_date:Optional[date] = None
    mid_semester_break_end_date:Optional[date] =None
    revision_start_date:Optional[date] = None
    semester_end_date: date

class CalendarEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True , index=True)
    calender_id:Optional[int] = Field(foreign_key="academiccalendar.id", index=True)
    event_name: Optional[str] = None
    event_start_date: Optional[date] = None
    event_end_date: Optional[date] = None
    event_start_time: Optional[time] = None
    event_end_time: Optional[time] = None
    is_holiday: Optional[bool] = None
    requires_no_classes: Optional[bool] = None


class WeeklyTimeTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True , index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id" , index=True)
    weekday: str
    pupils: str
    subject: str
    start_time: time
    end_time: time
    location: Optional[str] = None

class ClassSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id" , index=True)
    subject: str
    date: date
    start_time: str
    end_time: str
    class_name: str
    location: Optional[str] = None
    session_number: Optional[int]
    is_completed: bool = False
    resource_generated: bool = False

class TeacherPlannerEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str  # e.g., "meeting", "grading", "revision"
    is_required: bool = True
    related_session_id:Optional[int]=None

class TeacherNotification(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True , index=True)
    teacher_id: UUID = Field(index=True, nullable=False)
    title: str
    message: str
    type: Optional[str] = Field(default="info")  # e.g., info, warning, success
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Calendar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    Location:Optional[str] = None
    is_completed: bool = False

class Strand(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, index=True)
    strand_name: str = Field(index=True)
    subject: str = Field(index=True)
    teacher_id: uuid.UUID = Field(foreign_key="teacherprofile.id", index=True)
    week_number: int = Field(ge=1, le=16)
    session_ids: List[int] = Field(default_factory=list, sa_column=Column(JSONB))
    session_details: List[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    is_completed: bool = Field(default=False)

# Substrand Table Definition
class Substrand(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, index=True)
    substrand_name: str = Field(index=True)
    strand_id: int = Field(foreign_key="strand.id", index=True)
    subject: str = Field(index=True)
    teacher_id: uuid.UUID = Field(foreign_key="teacherprofile.id")
    week_numbers: List[int] = Field(default_factory=list, sa_column=Column(JSONB))
    session_ids: List[int] = Field(default_factory=list, sa_column=Column(JSONB))
    session_details: List[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    is_completed: bool = Field(default=False)

class ContentStandard(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, index=True)
    content_standard_code: str | None = Field(default=None, index=True, nullable=True)
    content_standard: str
    substrand_id: int = Field(foreign_key="substrand.id")
    subject: str = Field(index=True)
    teacher_id: uuid.UUID = Field(foreign_key="teacherprofile.id")
    session_ids: List[int] = Field(default_factory=list, sa_column=Column(JSONB))
    session_details: List[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    is_completed: bool = Field(default=False)
