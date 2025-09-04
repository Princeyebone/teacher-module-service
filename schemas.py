from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, time, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
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
    weeks_sessions: Dict[str, List[int]]  # e.g., {"Week 1": [53, 54], "Week 2": [55]}

class StrandUpdate(BaseModel):
    strand_name: str
    original_strand_name: str | None = None
    subject: str
    weeks_sessions: Dict[str, List[int]]  # e.g., {"Week 1": [53], "Week 2": [54]}

class StrandResponse(BaseModel):
    strand_name: str
    subject: str
    teacher_id: UUID
    weeks_sessions: Dict[str, List[SessionDetail]]
    created_at: datetime
    updated_at: datetime

class SubstrandCreate(BaseModel):
    substrand_name: str
    strand_name: str
    subject: str
    weeks_sessions: dict[str, List[int]]  # e.g., {"Week 1": [1, 2], "Week 2": [3]}

class SubstrandUpdate(BaseModel):
    substrand_name: str
    original_substrand_name: str | None = None
    strand_name: str
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
