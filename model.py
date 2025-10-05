from sqlmodel import Field, Relationship, SQLModel, Column, JSON, ARRAY
from sqlalchemy import event
from sqlalchemy.types import UserDefinedType
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List, Dict, Any
from datetime import date, time, datetime
import uuid
from uuid import UUID, uuid4
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
    country:Optional[str]=None 

  

class AcademicCalendar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    semester_name: str
    semester_start_date: date
    midsem_exams_date:Optional[date] = None
    mid_semester_break_start_date:Optional[date] = None
    mid_semester_break_end_date:Optional[date] =None
    revision_start_date:Optional[date] = None
    semester_end_date: date

    @classmethod
    def validate_empty_strings_to_none(cls, mapper, connection, target):
        """Convert empty strings to None for optional date fields before saving to database"""
        date_fields = ['midsem_exams_date', 'mid_semester_break_start_date', 'mid_semester_break_end_date', 'revision_start_date']
        for field in date_fields:
            if hasattr(target, field):
                value = getattr(target, field)
                if isinstance(value, str) and value.strip() == "":
                    setattr(target, field, None)

# Attach the validator to the model
@event.listens_for(AcademicCalendar, 'before_insert')
@event.listens_for(AcademicCalendar, 'before_update')
def validate_academic_calendar(mapper, connection, target):
    AcademicCalendar.validate_empty_strings_to_none(mapper, connection, target)

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

    @classmethod
    def validate_empty_strings_to_none(cls, mapper, connection, target):
        """Convert empty strings to None for optional date fields before saving to database"""
        date_fields = ['event_start_date', 'event_end_date']
        for field in date_fields:
            if hasattr(target, field):
                value = getattr(target, field)
                if isinstance(value, str) and value.strip() == "":
                    setattr(target, field, None)

# Attach the validator to the model
@event.listens_for(CalendarEvent, 'before_insert')
@event.listens_for(CalendarEvent, 'before_update')
def validate_calendar_event(mapper, connection, target):
    CalendarEvent.validate_empty_strings_to_none(mapper, connection, target)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)

  
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

    @classmethod
    def validate_empty_strings_to_none(cls, mapper, connection, target):
        """Convert empty strings to None for optional time fields before saving to database"""
        time_fields = ['start_time', 'end_time']
        for field in time_fields:
            if hasattr(target, field):
                value = getattr(target, field)
                if isinstance(value, str) and value.strip() == "":
                    setattr(target, field, None)

# Attach the validator to the model
@event.listens_for(Calendar, 'before_insert')
@event.listens_for(Calendar, 'before_update')
def validate_calendar(mapper, connection, target):
    Calendar.validate_empty_strings_to_none(mapper, connection, target)

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


class TempExtract(SQLModel, table=True):
    """Temporary storage for extracted data before user confirmation"""
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    type: str = Field(index=True)  # e.g., "timetable", "academic_calendar"
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


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
    email: Optional[str] = Field(index=True, unique=True)
    index_number: Optional[str] = Field(index=True, unique=True)
    hashed_password: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    # Add field to track if password has been changed from default
    password_changed: bool = Field(default=False)
    
    class Config:
        from_attributes = True

# Student Models
class StudentEnrollment(SQLModel, table=True):
    """Table for student enrollments in subjects/courses"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    student_id: UUID = Field(foreign_key="student.id", index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    teacher_display_name: Optional[str] = Field(default=None)
    enrollment_date: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

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

class AssessmentAssignment(SQLModel, table=True):
    """Main table for assessment assignments"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    assessment_id: int = Field(foreign_key="assessment.id", index=True)
    assigned_by_teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    available_from: datetime = Field()
    available_until: datetime = Field()
    time_limit_minutes: Optional[int] = Field(default=None)
    max_attempts: int = Field(default=1)  # Added max_attempts field
    is_active: bool = Field(default=True)
    show_results_timing: str = Field(default="after_submission")  # New field for when students see results
    instructions: Optional[str] = Field(default=None)  # New field for teacher instructions
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # Added updated_at field
    # New fields for class_name and subject
    subject: str = Field(index=True)
    class_name: str = Field(index=True)
    
    # Relationship fields
    access_rules: List["StudentAccessRule"] = Relationship(back_populates="assignment")
    security_settings: List["SecuritySetting"] = Relationship(back_populates="assignment")

class StudentAccessRule(SQLModel, table=True):
    """Table for student access rules"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    assignment_id: int = Field(foreign_key="assessmentassignment.id", index=True)
    student_id: Optional[UUID] = Field(default=None, foreign_key="student.id", index=True)  # For individual student
    class_id: Optional[int] = Field(default=None)  # Added class_id field
    can_access: bool = Field(default=True)
    access_granted_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # Added updated_at field
    # Relationship fields
    assignment: Optional[AssessmentAssignment] = Relationship(back_populates="access_rules")

class SecuritySetting(SQLModel, table=True):
    """Table for security settings"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    assignment_id: int = Field(foreign_key="assessmentassignment.id", index=True)
    strict_mode: bool = Field(default=False) 
    open_mode: bool = Field(default=False)
    free_mode: bool = Field(default=False)
    review: bool = Field(default=False)  # Added review field
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)  # Added updated_at field
    # Relationship fields
    assignment: Optional[AssessmentAssignment] = Relationship(back_populates="security_settings")

class AssignmentStatus(SQLModel, table=True):
    """Table to track student assignment completion status"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    student_name: str = Field()
    student_id: UUID = Field(foreign_key="student.id", index=True)
    assignment_id: int = Field(foreign_key="assessmentassignment.id", index=True)
    is_completed: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

 
class SurveillanceLog(SQLModel, table=True):
    """Logging table for surveillance dashboard"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", index=True)
    assignment_id: int = Field(index=True)  # Added assignment_id
    student_id: Optional[str] = Field(default=None, index=True)
    student_name: Optional[str] = Field(default=None)
    log_type: str = Field(index=True)  # e.g., "security_breach", "activity", "status_change"
    log_info: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    is_began: bool = Field(default=False)
    is_completed: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    time_spent: Optional[int] = Field(default=None)  # Time spent in seconds
    question_id: Optional[int] = Field(default=None, index=True)  # For question-specific logs
    event_category: Optional[str] = Field(default=None)  # e.g., "assessment_start", "question_answer", "assessment_complete"
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

class StudentSubmission(SQLModel, table=True):
    """Table for storing student assessment submissions"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    assignment_id: int = Field(foreign_key="assessmentassignment.id", index=True)
    student_id: UUID = Field(foreign_key="student.id", index=True)
    started_at: Optional[datetime] = Field(default=None)
    submitted_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

class SubmissionAnswer(SQLModel, table=True):
    """Table for storing individual student answers to questions"""
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    submission_id: int = Field(foreign_key="studentsubmission.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    answer_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    is_correct: Optional[bool] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)





























