from sqlmodel import SQLModel, Field
from typing import Optional, List, Tuple
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
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    semester_name: str
    academic_level: Optional[str] = None
    semester_start_date: date
    midsem_exams_date:Optional[date] = None
    mid_semester_break_start_date:Optional[date] = None
    mid_semester_break_end_date:Optional[date] =None
    revision_start_date:Optional[date] = None
    semester_end_date: date

class CalendarEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    calender_id:Optional[int] = Field(foreign_key="academiccalendar.id")
    event_name: Optional[str] = None
    event_start_date: Optional[date] = None
    event_end_date: Optional[date] = None
    event_start_time: Optional[time] = None
    event_end_time: Optional[time] = None
    is_holiday: Optional[bool] = None
    requires_no_classes: Optional[bool] = None


class WeeklyTimeTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    weekday: str
    pupils: str
    subject: str
    start_time: time
    end_time: time
    location: Optional[str] = None

class ClassSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
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
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str  # e.g., "meeting", "grading", "revision"
    is_required: bool = True
    related_session_id:Optional[int]=None

class TeacherNotification(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    teacher_id: UUID = Field(index=True, nullable=False)
    title: str
    message: str
    type: Optional[str] = Field(default="info")  # e.g., info, warning, success
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Calendar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    Location:Optional[str] = None
    is_completed: bool = False

class StrandBlock(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)  # Define a primary key
    strand: str
    week_range: str

class SubstrandBlock(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)  # Define a primary key
    substrand: str
    strand_block_id: UUID
    week_range: str

class ContentStandardBlock(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)  # Define a primary key
    content_standard: str
    substrand_block_id: UUID


class IndicatorSlot(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)  # Define a primary key
    indicator_code: str
    content_standard_block_id: UUID
    session_day: date  # or lesson_number
    split_index: Optional[int] = None  # if split into Part A / B


class LearningObjectives(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    class_session_id: int = Field(foreign_key="classsession.id")
    objective_text: str
    key_terms: str  # for AI prompt quality
    taxonomy_level: Optional[str]  # e.g., Bloom's level: Understand, Apply, Analyze

class LearningResource(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    learning_objective_id: UUID = Field(foreign_key="learningobjectives.id")
    type: str  # "note", "video", "quiz", "assignment", etc.
    content: str  # or link, or blob
    generated_by_ai: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

