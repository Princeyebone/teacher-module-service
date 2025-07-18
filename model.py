from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import UUID
import uuid
from enum import Enum
from datetime import date, time

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


class AcademicCalendar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    semester_name: str
    academic_level: Optional[str] = None
    semester_start_date: date
    mid_semester_break_start_date:Optional[date] = None
    mid_semester_break_end_date:Optional[date] =None
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
    timetable_id: int = Field(foreign_key="weeklytimetable.id")
    subject: str
    date: date
    start_time: str
    end_time: str
    class_name: str
    session_number: Optional[int]
    is_completed: bool = False
    resource_generated: bool = False

class TeacherPlannerEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    date: date
    start_time: str
    end_time: str
    title: str
    description: Optional[str] = None
    event_type: str  # e.g., "meeting", "grading", "revision"
    is_required: bool = True
    related_session_id: Optional[int] = Field(default=None, foreign_key="classsession.id")