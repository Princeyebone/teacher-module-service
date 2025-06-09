from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import UUID
import uuid
from enum import Enum

class UserRole(str, Enum):
    SUPERUSER = "superuser"
    ADMIN = "admin"
    TEACHER = "teacher"


class Teacher(SQLModel, table=True):
    id:Optional[UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    school_id:Optional[UUID] = None
    individual_id:Optional[UUID] = None
    employment_status:Optional[str] = None
    subjects:Optional[str] = None
    qualifications:Optional[str] = None
    rating:Optional[int] = None
    bio:Optional[str] = None