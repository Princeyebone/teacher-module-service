from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import UUID
import uuid
from enum import Enum

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


class TimeTable(SQLModel, table=True):



