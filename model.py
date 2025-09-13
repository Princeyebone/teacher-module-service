from sqlmodel import SQLModel, Field, Column
from typing import Optional, List, Dict, Any, Union
from sqlmodel import SQLModel, Field, select, Column, Relationship
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
    class_name: str = Field(index=True)
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
    class_name: str = Field(index=True)
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
    class_name: str = Field(index=True)
    teacher_id: uuid.UUID = Field(foreign_key="teacherprofile.id")
    session_ids: List[int] = Field(default_factory=list, sa_column=Column(JSONB))
    session_details: List[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    is_completed: bool = Field(default=False)


class Indicator(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, index=True)
    indicator_code: str | None = Field(default=None, index=True, nullable=True)
    indicator_text: str
    content_standard_id: int = Field(foreign_key="contentstandard.id")
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    teacher_id: uuid.UUID = Field(foreign_key="teacherprofile.id")
    # Add session storage fields
    session_ids: List[int] = Field(default_factory=list, sa_column=Column(JSONB))
    session_details: List[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    is_completed: bool = Field(default=False)


class UploadedFile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", nullable=False)
    file_name: str
    file_type: str  # "pdf", "docx", "xlsx", "jpg"
    purpose: str    # "timetable", "academic_calendar", "lesson_plan"
    gcs_path: Optional[str] = None   # permanent bucket path
    extracted_text: str | None 

 
class SemesterMaterials(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, index=True)
    teacher_id: uuid.UUID = Field(foreign_key="teacherprofile.id", index=True)
    strand_id: int = Field(foreign_key="strand.id", index=True)
    material:str = Field
    url: str = Field



class AssessmentWeights(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: str = Field(index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    weights: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))
    columns: Optional[List[Dict[str, Any]]] = Field(default_factory=list, sa_column=Column(JSONB))  # Add column information
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

 

class GradeSystem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: str = Field(index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    grading_type: str = Field(index=True)  # e.g., "Letter Grade", "Percentage", "GPA", etc.
    grade_ranges: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

   
class AssessmentScores(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    columns: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))
    grades: Dict[str, Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    
# Add the Student model for authentication
class Student(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    student_id: int = Field(index=True)
    class_name: str = Field(index=True)
    email: str = Field(index=True, unique=True)
    index_number: str = Field(index=True, unique=True)
    hashed_password: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    
    class Config:
        from_attributes = True

# Assessment Question Models
class Question(SQLModel, table=True):
    """Main Question table with common fields for all question types"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    strand: Optional[str] = Field(default=None, index=True)  # Made strand optional
    topic: Optional[str] = Field(default=None, index=True)
    type: str = Field(index=True)  # Question type (multiple_choice, true_false, etc.)
    question_text: str
    points: int = Field(default=1)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Relationship to QuestionDetail
    detail: Optional["QuestionDetail"] = Relationship(back_populates="question")


class QuestionDetail(SQLModel, table=True):
    """Question details table with type-specific fields"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    # Fields for different question types
    options: Optional[List[Dict[str, Any]]] = Field(default_factory=list, sa_column=Column(JSONB))  # For MC and TF
    correct_answer: Optional[str] = Field(default=None)  # Can be index for MC/TF, text for others
    explanation: Optional[str] = Field(default=None)  # For Short Answer and Essay
    marking_guidelines: Optional[str] = Field(default=None)  # For Short Answer and Essay
    matching_pairs: Optional[List[Dict[str, str]]] = Field(default_factory=list, sa_column=Column(JSONB))  # For Matching
    sub_questions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, sa_column=Column(JSONB))  # For Essay and Short Answer
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Relationship to Question
    question: Optional[Question] = Relationship(back_populates="detail")


# Assessment Models
class Assessment(SQLModel, table=True):
    """Main Assessment table for quizzes, tests, exercises, etc."""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    title: str
    description: Optional[str] = Field(default=None)
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    assessment_type: str = Field(index=True)  # quiz, test, exercise, exam, etc.
    total_points: int = Field(default=0)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    is_published: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Relationship to AssessmentQuestion
    assessment_questions: List["AssessmentQuestion"] = Relationship(back_populates="assessment")
    sections: List["AssessmentSection"] = Relationship(back_populates="assessment")


class AssessmentSection(SQLModel, table=True):
    """Assessment sections for exams and other multi-section assessments"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    assessment_id: int = Field(foreign_key="assessment.id", index=True)
    name: str  # Section name (e.g., "Section A", "Part 1")
    section_order: int = Field(default=0)  # Order of section in assessment
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Relationships
    assessment: Optional[Assessment] = Relationship(back_populates="sections")
    section_questions: List["AssessmentSectionQuestion"] = Relationship(back_populates="section")
    assessment_questions: List["AssessmentQuestion"] = Relationship(back_populates="section")


class AssessmentQuestion(SQLModel, table=True):
    """Junction table linking assessments to questions with order and points"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    assessment_id: int = Field(foreign_key="assessment.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    question_order: int = Field(default=0)  # Order of question in assessment
    points: int = Field(default=1)  # Points for this specific question in this assessment
    section_id: Optional[int] = Field(default=None, foreign_key="assessmentsection.id", index=True)  # Optional section for multi-section assessments
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Relationships
    assessment: Optional[Assessment] = Relationship(back_populates="assessment_questions")
    question: Optional[Question] = Relationship()
    section: Optional[AssessmentSection] = Relationship(back_populates="assessment_questions")


class AssessmentSectionQuestion(SQLModel, table=True):
    """Junction table linking assessment sections to questions"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    section_id: int = Field(foreign_key="assessmentsection.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    question_order: int = Field(default=0)  # Order of question in section
    points: int = Field(default=1)  # Points for this specific question in this section
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Relationships
    section: Optional[AssessmentSection] = Relationship(back_populates="section_questions")
    question: Optional[Question] = Relationship()
