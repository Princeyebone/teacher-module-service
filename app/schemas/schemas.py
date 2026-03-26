from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from datetime import date, time, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

 

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
    data_source: Optional[str] = None  # Added to indicate data source (temp_extract or weekly_timetable)

class TimeTableEntry(BaseModel):
    items:List[TimeTableItem]
    
class AcademicCalendarEntry(BaseModel):
    teacher_id:UUID
    calender_id:int
    semester_name: str
    start_date: date
    mid_semester_break_start_date:Optional[date] = None
    mid_semester_break_end_date:Optional[date] = None
    end_date: date
    event_name: Optional[str] = None
    event_start_day: Optional[date] = None
    event_end_date: Optional[date] = None
    event_start_time: Optional[time] = None
    event_end_time: Optional[time] = None
    is_holiday: Optional[bool] = None
    requires_no_classes: Optional[bool] = None

    @model_validator(mode='before')
    @classmethod
    def convert_empty_strings_to_none(cls, data: Any) -> Any:
        """Convert empty strings or whitespace-only strings to None for optional date fields"""
        if isinstance(data, dict):
            date_fields = ['mid_semester_break_start_date', 'mid_semester_break_end_date', 'event_start_day', 'event_end_date']
            for field in date_fields:
                if field in data and isinstance(data[field], str) and data[field].strip() == "":
                    data[field] = None
        return data

class AcademicCalendarPublic(BaseModel):
    id: Optional[int] = None
    teacher_id: Optional[UUID] = None
    semester_name: str
    midsem_exams_date: Optional[date] = None
    revision_start_date: Optional[date] = None
    semester_start_date: date
    mid_semester_break_start_date: Optional[date] = None
    mid_semester_break_end_date:Optional[date] = None
    semester_end_date: date

    @model_validator(mode='before')
    @classmethod
    def convert_empty_strings_to_none(cls, data: Any) -> Any:
        """Convert empty strings or whitespace-only strings to None for optional date fields"""
        if isinstance(data, dict):
            date_fields = ['midsem_exams_date', 'revision_start_date', 'mid_semester_break_start_date', 'mid_semester_break_end_date']
            for field in date_fields:
                if field in data and isinstance(data[field], str) and data[field].strip() == "":
                    data[field] = None
        return data

class CalendarEventPublic(BaseModel):
    event_name: Optional[str] = None
    event_start_date: Optional[date] = None
    event_end_date: Optional[date]  = None
    event_start_time: Optional[time] = None
    event_end_time: Optional[time] = None
    is_holiday: Optional[bool] = None
    requires_no_classes: Optional[bool] = None

    @model_validator(mode='before')
    @classmethod
    def convert_empty_strings_to_none(cls, data: Any) -> Any:
        """Convert empty strings or whitespace-only strings to None for optional date fields"""
        if isinstance(data, dict):
            date_fields = ['event_start_date', 'event_end_date']
            for field in date_fields:
                if field in data and isinstance(data[field], str) and data[field].strip() == "":
                    data[field] = None
        return data

class UpdateCalendarResponse(BaseModel):
    academic_calendar: AcademicCalendarPublic
    calendar_events: List[CalendarEventPublic]


class Calendar(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    Location:Optional[str] = None
    is_completed: bool = False

class UpdateCalendar(BaseModel):
    items:List[Calendar]


    

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

class SessionDetail(BaseModel):
    id: int
    date: str
    subject: str
    start_time: str
    end_time: str
    class_name: str
    location: str
    week_number: int

class StrandCreate(BaseModel):
    strand_name: str
    subject: str
    class_name:str
    weeks_sessions: Dict[str, List[int]]  # e.g., {"Week 1": [53, 54], "Week 2": [55]}

class StrandUpdate(BaseModel):
    strand_name: str
    original_strand_name: str | None = None
    subject: str
    class_name: str
    weeks_sessions: Dict[str, List[int]]  # e.g., {"Week 1": [53, 54], "Week 2": [55]}

class StrandResponse(BaseModel):
    strand_name: str
    subject: str
    class_name: str
    teacher_id: UUID
    weeks_sessions: Dict[str, List[SessionDetail]]
    created_at: datetime
    updated_at: datetime
    data_source: Optional[str] = None  # Added to indicate data source (temp_extract or strand_table)
    file: Optional[str] = None  # Added to include signed URL for the file

class SubstrandCreate(BaseModel):
    substrand_name: str
    strand_name: str
    class_name: str
    subject: str
    weeks_sessions: dict[str, List[int]]  # e.g., {"Week 1": [1, 2], "Week 2": [3]}

class SubstrandUpdate(BaseModel):
    substrand_name: str
    original_substrand_name: str | None = None
    strand_name: str
    class_name: str
    subject: str
    weeks_sessions: dict[str, List[int]]

class SubstrandResponse(BaseModel):
    substrand_name: str
    strand_name: str
    subject: str
    teacher_id: UUID
    weeks_sessions: dict[str, List[SessionDetail]]
    created_at: datetime
    updated_at: datetime

class ContentStandardCreate(BaseModel):
    content_standard_code: str | None = None
    content_standard: str
    substrand_name: str
    strand_name: str
    subject: str
    weeks_sessions: Dict[str, List[int]] | None = None  # e.g., {"Week 1": [53, 54], "Week 2": [55]}

class ContentStandardUpdate(BaseModel):
    content_standard_code: str | None = None
    original_content_standard_code: str | None = None
    original_content_standard_text: str | None = None
    content_standard: str
    substrand_name: str
    strand_name: str
    subject: str
    weeks_sessions: Dict[str, List[int]] | None = None  # e.g., {"Week 1": [53, 54], "Week 2": [55]}

class ContentStandardResponse(BaseModel):
    content_standard_code: str | None = None
    content_standard: str
    substrand_name: str
    strand_name: str
    subject: str
    teacher_id: UUID
    weeks_sessions: Dict[str, List[SessionDetail]] | None = None
    created_at: datetime
    updated_at: datetime

class IndicatorCreate(BaseModel):
    indicator_code: str | None = None
    indicator_text: str
    content_standard_code: str | None = None
    content_standard_text: str | None = None
    substrand_name: str
    strand_name: str
    subject: str
    # Add session information
    weeks_sessions: Dict[str, List[int]] | None = None  # e.g., {"Week 1": [53, 54], "Week 2": [55]}

class IndicatorUpdate(BaseModel):
    indicator_code: str | None = None
    original_indicator_code: str | None = None
    original_indicator_text: str | None = None
    indicator_text: str
    content_standard_code: str | None = None
    content_standard_text: str | None = None
    original_content_standard_code: str | None = None
    original_content_standard_text: str | None = None
    substrand_name: str
    strand_name: str
    subject: str
    # Add session information
    weeks_sessions: Dict[str, List[int]] | None = None
    
class IndicatorResponse(BaseModel):
    indicator_code: str | None = None
    indicator_text: str
    content_standard_code: str | None = None
    content_standard_text: str
    substrand_name: str
    strand_name: str
    subject: str
    teacher_id: UUID
    # Add session information
    weeks_sessions: Dict[str, List[SessionDetail]] | None = None
    created_at: datetime
    updated_at: datetime

class SessionInfo(BaseModel):
    id: int
    date: str
    subject: str
    start_time: str
    end_time: str
    class_name: str
    location: Optional[str] = None
    session_number: Optional[int] = None

class WeekAvailability(BaseModel):
    week_key: str  # e.g., "Week 6"
    week_number: int  # e.g., 6
    total_sessions: int
    available_sessions: List[SessionInfo]

class AvailableWeeksResponse(BaseModel):
    subject: str
    class_name: str
    teacher_id: UUID
    available_weeks: Dict[str, WeekAvailability]  # week_key -> WeekAvailability
    total_available_weeks: int
    total_available_sessions: int
    semester_info: Dict[str, str]  # start_date, end_date, total_weeks

class GradeRange(BaseModel):
    id: int
    min: float
    max: float
    grade: str
    description: Optional[str] = None


class GradeSystemCreate(BaseModel):
    name: str
    grading_type: str
    grade_ranges: List[GradeRange]
    is_default: bool = False


class GradeSystemUpdate(BaseModel):
    name: Optional[str] = None
    grading_type: Optional[str] = None
    grade_ranges: Optional[List[GradeRange]] = None
    is_default: Optional[bool] = None


class GradeSystemResponse(BaseModel):
    id: int
    name: str
    teacher_id: UUID
    grading_type: str
    grade_ranges: List[GradeRange]
    is_default: bool
    created_at: datetime
    updated_at: datetime


# Assessment Weights Schemas
class WeightsEntry(BaseModel):
    id: str  # Unique identifier for the weight entry
    assessment_type: str  # e.g., "Exams", "Test", "Midsem Ex", etc.
    weight: float  # Weight percentage (0-100)
    
    @field_validator('weight')
    def validate_weight(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Weight must be between 0 and 100')
        return v

# Add a new schema for column information
class ColumnInfoW(BaseModel):
    id: str
    assessment_type: str
    full_mark: str
    custom_full_mark: Optional[str] = None

class AssessmentWeightsCreate(BaseModel):
    name: str
    subject: str
    class_name: str
    weights: List[WeightsEntry]
    columns: Optional[List[ColumnInfoW]] = None  # Add column information
    is_default: bool = False
    
    @field_validator('weights')
    def validate_total_weight(cls, v):
        total = sum(entry.weight for entry in v)
        if total > 100:
            raise ValueError('Total weight cannot exceed 100%')
        return v


class AssessmentWeightsUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    class_name: Optional[str] = None
    weights: Optional[List[WeightsEntry]] = None
    columns: Optional[List[ColumnInfoW]] = None  # Add column information
    is_default: Optional[bool] = None
    
    @field_validator('weights')
    def validate_total_weight(cls, v):
        if v is not None:
            total = sum(entry.weight for entry in v)
            if total > 100:
                raise ValueError('Total weight cannot exceed 100%')
        return v


class AssessmentWeightsResponse(BaseModel):
    id: int
    name: str
    teacher_id: UUID
    subject: str
    class_name: str
    weights: List[WeightsEntry]
    columns: Optional[List[ColumnInfoW]] = None  # Add column information
    is_default: bool
    created_at: datetime
    updated_at: datetime


# Assessment Scores Schemas
class ColumnInfoS(BaseModel):
    id: str
    label: str
    type: str  # 'readonly' for student name, 'input' for assessment columns
    assessmentType: Optional[str] = None  # e.g., "Exams", "Test", etc.
    fullMark: Optional[str] = None  # e.g., "100", "Other"
    customFullMark: Optional[str] = None  # Custom full mark value when fullMark is "Other"


class AssessmentScoresCreate(BaseModel):
    subject: str
    class_name: str
    columns: List[ColumnInfoS]
    grades: Dict[str, Dict[str, Any]]  # {student_id: {column_id: grade_value}}


class AssessmentScoresUpdate(BaseModel):
    subject: Optional[str] = None
    class_name: Optional[str] = None
    columns: Optional[List[ColumnInfoS]] = None
    grades: Optional[Dict[str, Dict[str, Any]]] = None


class AssessmentScoresResponse(BaseModel):
    id: int
    teacher_id: UUID
    subject: str
    class_name: str
    columns: List[ColumnInfoS]
    grades: Dict[str, Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


# Student Authentication Schemas
class StudentLoginRequest(BaseModel):
    email: EmailStr
    password: str

class StudentIDLoginRequest(BaseModel):
    student_id: str
    password: str


class StudentRegistrationRequest(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    index_number: Optional[str] = None
    class_name: Optional[str] = None
    subject: Optional[str] = None
    teacher_display_name: Optional[str] = None

class StudentPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class StudentToken(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class StudentTokenData(BaseModel):
    student_id: UUID | None = None
    email: str | None = None
    index_number: str | None = None
    role: str = "student"

class StudentProfileResponse(BaseModel):
    id: UUID
    email: Optional[str]
    index_number: Optional[str]
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class StudentEnrollmentResponse(BaseModel):
    id: int
    subject: str
    class_name: str
    teacher_display_name: Optional[str] = None
    enrollment_date: datetime
    is_active: bool

    class Config:
        from_attributes = True

class StudentRegistrationResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    index_number: str
    login_id: str
    created_at: Optional[str] = None
    enrollment: Optional[Dict[str, Any]] = None

class PaginatedStudentResponse(BaseModel):
    students: List[StudentProfileResponse]
    pagination: Dict[str, Any]
    sort: Dict[str, str]

# Pydantic Schemas for API
class QuestionOption(BaseModel):
    id: int
    text: str
    is_correct: bool


class MatchingPair(BaseModel):
    id: int
    left: str
    right: str


class SubQuestion(BaseModel):
    id: Optional[int] = None
    type: str
    question_text: str
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    marking_guidelines: Optional[str] = None
    points: int = 1


class QuestionCreate(BaseModel):
    subject: str
    class_name: str
    strand: Optional[str] = None  # Made strand optional
    topic: Optional[str] = None
    type: str
    question_text: str
    points: int = 1
    tags: List[str] = []
    
    # Type-specific fields
    options: Optional[List[QuestionOption]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    marking_guidelines: Optional[str] = None
    matching_pairs: Optional[List[MatchingPair]] = None
    sub_questions: Optional[List[SubQuestion]] = None


class QuestionUpdate(BaseModel):
    subject: Optional[str] = None
    class_name: Optional[str] = None
    strand: Optional[str] = None
    topic: Optional[str] = None
    type: Optional[str] = None
    question_text: Optional[str] = None
    points: Optional[int] = None
    tags: Optional[List[str]] = None
    
    # Type-specific fields
    options: Optional[List[QuestionOption]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    marking_guidelines: Optional[str] = None
    matching_pairs: Optional[List[MatchingPair]] = None
    sub_questions: Optional[List[SubQuestion]] = None


class QuestionResponse(BaseModel):
    id: int
    teacher_id: UUID
    subject: str
    class_name: str
    strand: Optional[str]  # Made strand optional
    topic: Optional[str]
    type: str
    question_text: str
    points: int
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    
    # Type-specific fields
    options: Optional[List[QuestionOption]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    marking_guidelines: Optional[str] = None
    matching_pairs: Optional[List[MatchingPair]] = None
    sub_questions: Optional[List[SubQuestion]] = None


# Assessment Pydantic Schemas
class AssessmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    subject: str
    class_name: str
    assessment_type: str  # quiz, test, exercise, exam, etc.
    tags: List[str] = []
    question_ids: List[int] = []  # List of question IDs to include in the assessment
from typing import List, Optional

from pydantic import BaseModel


class AssessmentSectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    section_order: int = 0


class AssessmentSectionWithQuestionsCreate(AssessmentSectionCreate):
    questions: List[int] = []  # List of question IDs to include in this section


class AssessmentSectionWithQuestionsUpdate(AssessmentSectionCreate):
    id: Optional[int] = None  # ID of existing section (if updating)
    questions: List[int] = []  # List of question IDs to include in this section


class AssessmentWithSectionsCreate(BaseModel):
    title: str
    description: Optional[str] = None
    subject: str
    class_name: str
    assessment_type: str  # Should be "exam" for exams with sections
    tags: List[str] = []
    sections: List[AssessmentSectionWithQuestionsCreate] = []


class AssessmentWithSectionsUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    class_name: Optional[str] = None
    assessment_type: Optional[str] = None
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    sections: Optional[List[AssessmentSectionWithQuestionsUpdate]] = None


class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    class_name: Optional[str] = None
    assessment_type: Optional[str] = None
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    question_ids: Optional[List[int]] = None  # Add this field to handle question associations

class AssessmentQuestionCreate(BaseModel):
    question_id: int
    question_order: int = 0
    points: int = 1
    section_id: Optional[int] = None  # For sectioned assessments like exams


class AssessmentQuestionUpdate(BaseModel):
    question_order: Optional[int] = None
    points: Optional[int] = None
    section_id: Optional[int] = None


class AssessmentQuestionResponse(BaseModel):
    id: int
    assessment_id: int
    question_id: int
    question_order: int
    points: int
    section_id: Optional[int] = None  # Add section_id field
    created_at: datetime
    
    # Include question details
    question: QuestionResponse


class AssessmentResponse(BaseModel):
    id: int
    teacher_id: UUID
    title: str
    description: Optional[str]
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    tags: List[str]
    is_published: bool
    created_at: datetime
    updated_at: datetime
    
    # Include assessment questions
    assessment_questions: List[AssessmentQuestionResponse] = []
    
    # Include sections for exams
    sections: Optional[List[dict]] = []

class StudentLogCreate(BaseModel):
    """Create model for student logs"""
    assignment_id: int
    activity_type: str
    question_id: Optional[int] = None
    additional_data: Dict[str, Any] = {}


class StudentLogBatchCreate(BaseModel):
    """Create model for batch student logs"""
    assignment_id: int
    logs: List[StudentLogCreate]


class AssessmentAssignmentCreate(BaseModel):
    assessment_id: int
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int] = None
    is_active: bool = True
    max_attempts: Optional[int] = None
    show_results_timing: str = "after_submission"  # New field for when students see results
    instructions: Optional[str] = None  # New field for teacher instructions



class AssessmentAssignmentResponse(BaseModel):
    id: int
    assessment_id: int
    assigned_by_teacher_id: UUID
    assigned_at: datetime
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int] = None
    is_active: bool
    show_results_timing: str  # New field for when students see results
    instructions: Optional[str] = None  # New field for teacher instructions
    created_at: datetime
    updated_at: datetime
    # Add the new fields for subject and class_name
    subject: str
    class_name: str

class SecuritySettingCreateWithoutAssignment(BaseModel):
    strict_mode: bool = False
    open_mode: bool = False
    free_mode: bool = False
    review: bool = False


class StudentAccessRuleCreateWithoutAssignment(BaseModel):
    student_id: Optional[UUID] = None
    class_id: Optional[int] = None
    can_access: bool = True


class CompositePublishingDataCreate(BaseModel):
    assignment_data: AssessmentAssignmentCreate
    security_settings: SecuritySettingCreateWithoutAssignment
    access_rules: List[StudentAccessRuleCreateWithoutAssignment]

class SurveillanceDataResponse(BaseModel):
    id: int
    title: str
    assessment_type: str
    subject: str
    class_name: str
    question_count: int
    total_points: int
    created_at: datetime
    is_published: bool
    is_active: bool
    available_from: datetime
    available_until: datetime

class StudentMonitoringUpdate(BaseModel):
    """Request model for student monitoring updates"""
    assessment_id: int
    student_id: str
    student_name: str
    current_status: str = "active"
    current_question_id: Optional[int] = None
    time_on_question: Optional[int] = None
    total_time: int = 0
    ip_address: str
    location: str
    security_breaches: int = 0
    additional_data: Dict[str, Any] = {}


class StudentMonitoringResponse(BaseModel):
    """Response model for student monitoring data"""
    id: int
    assessment_id: int
    student_id: str
    student_name: str
    last_updated: datetime
    current_status: str
    current_question_id: Optional[int] = None
    time_on_question: Optional[int] = None
    total_time: int
    ip_address: str
    location: str
    security_breaches: int
    additional_data: Dict[str, Any]
    created_at: datetime

class AssessmentAssignmentUpdate(BaseModel):
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    time_limit_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    show_results_timing: Optional[str] = None  # New field for when students see results
    instructions: Optional[str] = None  # New field for teacher instructions


class SecuritySettingUpdate(BaseModel):
    strict_mode: Optional[bool] = None
    open_mode: Optional[bool] = None
    free_mode: Optional[bool] = None
    review: Optional[bool] = None

class SecuritySettingResponse(BaseModel):
    id: int
    assignment_id: int
    strict_mode: bool
    open_mode: bool
    free_mode: bool
    review: bool
    created_at: datetime
    updated_at: datetime

class StudentAccessRuleCreate(BaseModel):
    assignment_id: int
    student_id: Optional[UUID] = None
    class_id: Optional[int] = None
    can_access: bool = True

class StudentAccessRuleResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: Optional[UUID] = None
    class_id: Optional[int] = None
    can_access: bool
    access_granted_at: datetime
    created_at: datetime
    updated_at: datetime


class AssessmentAssignmentUpdateWithRelations(BaseModel):
    assignment_data: Optional[AssessmentAssignmentUpdate] = None
    security_settings: Optional[SecuritySettingUpdate] = None
    access_rules: Optional[List[StudentAccessRuleCreateWithoutAssignment]] = None  # For adding new rules



class StudentAvailableAssessmentResponse(BaseModel):
    """Summary data for available assessments"""
    id: int
    title: str
    assessment_type: str
    subject: str
    class_name: str
    question_count: int
    total_points: int
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int]
    max_attempts: int
    show_results_timing: str
    created_at: datetime

class StudentQuestionResponse(BaseModel):
    id: int
    subject: str
    class_name: str
    strand: Optional[str]
    topic: Optional[str]
    type: str
    question_text: str
    points: int
    created_at: datetime
    parent_id: Optional[int] = None  # Add parent_id field
    options: Optional[List[dict]] = None  # For multiple choice and true/false
    matching_pairs: Optional[List[dict]] = None  # For matching questions (left side only)
    sub_questions: Optional[List[dict]] = None  # For essay and short answer (without answers)


class StudentAssessmentQuestionResponse(BaseModel):
    """Assessment question data for students"""
    id: int
    question_order: int
    points: int
    section_id: Optional[int] = None
    question: StudentQuestionResponse

class StudentAssessmentSectionResponse(BaseModel):
    """Assessment section data for students"""
    id: int
    name: str
    section_order: int
    description: Optional[str]

class StudentAssessmentResponse(BaseModel):
    """Assessment data for students (excluding sensitive information)"""
    id: int
    title: str
    description: Optional[str]
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    created_at: datetime
    assessment_questions: List[StudentAssessmentQuestionResponse] = []
    sections: List[StudentAssessmentSectionResponse] = []

class StudentAssignedAssessmentResponse(BaseModel):
    """Assigned assessment data for students"""
    id: int
    title: str
    assessment_type: str
    subject: str
    class_name: str
    question_count: int
    total_points: int
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int]
    max_attempts: int
    show_results_timing: str
    status: str  # active, expired, completed
    created_at: datetime

class StudentQuestionOption(BaseModel):
    id: int
    text: str

class StudentMatchingPair(BaseModel):
    id: int
    left: str
    right: str

class StudentSubQuestion(BaseModel):
    id: Optional[int] = None
    type: str
    question_text: str
    points: int = 1


class StudentQuestionResponse(BaseModel):
    id: int
    subject: str
    class_name: str
    strand: Optional[str]
    topic: Optional[str]
    type: str
    question_text: str
    points: int
    created_at: datetime
    parent_id: Optional[int] = None  # Add parent_id field
    
    # Type-specific fields (without answers/explanations)
    options: Optional[List[StudentQuestionOption]] = None
    matching_pairs: Optional[List[StudentMatchingPair]] = None
    sub_questions: Optional[List[StudentSubQuestion]] = None

class StudentAssessmentSectionResponse(BaseModel):
    id: int
    name: str
    section_order: int
    description: Optional[str] = None
    created_at: datetime

class StudentAssessmentQuestionResponse(BaseModel):
    id: int
    assessment_id: int
    question_id: int
    question_order: int
    points: int
    section_id: Optional[int] = None
    created_at: datetime
    
    # Include question details (without answers/explanations)
    question: StudentQuestionResponse

class StudentAssessmentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    created_at: datetime
    updated_at: datetime
    
    # Include assessment questions (without answers/explanations)
    assessment_questions: List[StudentAssessmentQuestionResponse] = []
    
    # Include sections for exams
    sections: Optional[List[StudentAssessmentSectionResponse]] = []

# New model for dashboard daily challenges (simplified)
class DashboardDailyChallengeResponse(BaseModel):
    id: int
    title: str
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    created_at: datetime

class AssessmentCountResponse(BaseModel):
    total_assessments: int
    daily_challenges: int
    enrolled_courses: int

class StudentAssessmentAccessResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int]
    show_results_timing: str
    instructions: Optional[str]
    created_at: datetime
    updated_at: datetime

class StudentAssessmentDetailResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    teacher_id: str  # Teacher ID as string
    current_page: int
    total_pages: int
    total_questions: int
    page_size: int
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int]
    show_results_timing: str
    instructions: Optional[str]
    security_settings: dict  # Will contain the security settings
    created_at: datetime
    updated_at: datetime
    
    # Include assessment questions (without answers/explanations)
    assessment_questions: List[StudentAssessmentQuestionResponse] = []
    
    # Include sections for exams
    sections: Optional[List[StudentAssessmentSectionResponse]] = []

class StudentAssessmentInitialDetailResponse(BaseModel):
    """Simplified assessment detail response for initial assessment data"""
    id: int
    title: str
    description: Optional[str]
    subject: str
    class_name: str
    assessment_type: str
    total_points: int
    available_from: datetime
    available_until: datetime
    time_limit_minutes: Optional[int]
    show_results_timing: str
    instructions: Optional[str]
    teacher_id: str
    security_settings: dict
    created_at: datetime
    updated_at: datetime

class SubmissionAnswerResponse(BaseModel):
    id: int
    submission_id: int
    question_id: int
    answer_data: Dict[str, Any]
    is_correct: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

class StudentSubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: UUID
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class StudentAssessmentSubmissionCreate(BaseModel):
    """Combined model for creating student submission with answers"""
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    answers: Dict[str, Any] = {}  # Dictionary with question_id as keys and answer_data as values

class StudentAssessmentSubmissionUpdate(BaseModel):
    """Combined model for updating student submission with answers"""
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    answers: Optional[Dict[str, Any]] = None  # Dictionary with question_id as keys and answer_data as values


class StudentSubmissionWithAnswersResponse(BaseModel):
    submission: StudentSubmissionResponse
    answers: List[SubmissionAnswerResponse]
