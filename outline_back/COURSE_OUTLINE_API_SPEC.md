# Course Outline (Teacher Lesson Pack) - Database & API Specification

## 1. Interface Overview

The **Course Outline** interface (also called "Teacher Lesson Pack") is a comprehensive document builder for educators to create structured course outlines, syllabi, and lesson packs. The interface supports two terminology modes:
- **Course/Lecturer** mode (higher education)
- **Subject/Teacher** mode (K-12 education)

### Key Interface Sections:

| Section # | Section Name | Description | Dynamic/Fixed |
|-----------|--------------|-------------|---------------|
| 1 | School Info Headers | Centered text headers at top (e.g., school name, department, program) | **Dynamic** - variable number of headers |
| 2 | Lecture/Course Info | Two-column layout with label:value pairs (e.g., Course Code, Credit Hours) | **Dynamic** - variable number of fields per column |
| 3 | Course/Subject Objectives | Numbered list of learning objectives | **Dynamic** - variable number of items |
| 4 | Course/Subject Description | Free-text description of the course | Fixed - single text field |
| 5 | Learning Outcomes | Numbered list of expected outcomes | **Dynamic** - variable number of items |
| 6 | Course/Subject Delivery Methods | Free-text describing teaching methods | Fixed - single text field |
| 7 | Course Content Table | Weekly schedule with topic and activity columns | **Dynamic** - variable number of weeks/rows |
| 8 | Policies | Numbered list of academic policies | **Dynamic** - variable number of items |

---

## 2. Database Table Design

### Table Name: `course_outlines`

```sql
CREATE TABLE course_outlines (
    -- Primary Key & Metadata
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Terminology Settings
    terminology_type VARCHAR(20) DEFAULT 'Course',  -- 'Course' or 'Subject'
    terminology_role VARCHAR(20) DEFAULT 'Lecturer', -- 'Lecturer' or 'Teacher'
    
    -- Section 1: School Info Headers (Dynamic array of strings)
    school_info_headers JSONB NOT NULL DEFAULT '[]',
    -- Example: ["University of Ghana", "Department of Computer Science", "BSc Computer Science Program"]
    
    -- Section 2: Lecture/Course Info (Dynamic object with left/right arrays)
    lecture_info JSONB NOT NULL DEFAULT '{"left": [], "right": []}',
    -- Example: {
    --   "left": [
    --     {"label": "Course Code", "value": "CS101"},
    --     {"label": "Course Title", "value": "Introduction to Programming"},
    --     {"label": "Course Lecturer", "value": "Dr. John Doe"},
    --     {"label": "Email", "value": "john.doe@university.edu"}
    --   ],
    --   "right": [
    --     {"label": "Credit Hour(s)", "value": "3"},
    --     {"label": "Office Hours", "value": "Mon-Wed 2-4pm"},
    --     {"label": "Room", "value": "Block A, Room 205"},
    --     {"label": "Phone", "value": "+233 20 123 4567"}
    --   ]
    -- }
    
    -- Section 3: Course/Subject Objectives (Dynamic array of strings)
    course_objectives JSONB NOT NULL DEFAULT '[""]',
    -- Example: [
    --   "Understand fundamental programming concepts",
    --   "Apply problem-solving techniques using algorithms",
    --   "Develop proficiency in Python programming"
    -- ]
    
    -- Section 4: Course/Subject Description (Single text field)
    course_description TEXT DEFAULT '',
    -- Example: "This course introduces students to the fundamentals of programming..."
    
    -- Section 5: Learning Outcomes (Dynamic array of strings)
    learning_outcomes JSONB NOT NULL DEFAULT '[""]',
    -- Example: [
    --   "Students will be able to write basic Python programs",
    --   "Students will understand data types and control structures",
    --   "Students will be able to debug and test code"
    -- ]
    
    -- Section 6: Course/Subject Delivery Methods (Single text field)
    course_delivery TEXT DEFAULT '',
    -- Example: "Lectures, hands-on lab sessions, group projects, online resources"
    
    -- Section 7: Course Content Table (Dynamic array of week objects)
    course_content JSONB NOT NULL DEFAULT '[]',
    -- Example: [
    --   {"week": 1, "topic": "Introduction to Programming", "activity": "Lecture + Lab Setup"},
    --   {"week": 2, "topic": "Variables and Data Types", "activity": "Lecture + Coding Exercises"},
    --   {"week": 3, "topic": "Control Structures", "activity": "Lecture + Quiz"},
    --   ...
    -- ]
    
    -- Section 8: Policies (Dynamic array of strings)
    policies JSONB NOT NULL DEFAULT '[""]',
    -- Example: [
    --   "Attendance is mandatory. More than 3 absences will result in grade reduction.",
    --   "Academic dishonesty will result in automatic course failure.",
    --   "Late submissions will be penalized 10% per day."
    -- ]
    
    -- Optional: Association with subject/class (for integration with timetable)
    subject_name VARCHAR(255),
    class_name VARCHAR(255),
    academic_year VARCHAR(20),
    semester VARCHAR(20),
    
    -- Indexes
    CONSTRAINT unique_teacher_subject_class UNIQUE (teacher_id, subject_name, class_name, academic_year, semester)
);

-- Create indexes for common queries
CREATE INDEX idx_course_outlines_teacher ON course_outlines(teacher_id);
CREATE INDEX idx_course_outlines_subject ON course_outlines(subject_name);
CREATE INDEX idx_course_outlines_updated ON course_outlines(updated_at DESC);
```

---

## 3. API Endpoints

### 3.1 Get Course Outline

**Endpoint:** `GET /api/course-outline`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| subject_name | string | No | Filter by subject name |
| class_name | string | No | Filter by class name |
| academic_year | string | No | Filter by academic year |
| semester | string | No | Filter by semester |
| id | UUID | No | Get specific outline by ID |

**Response Format:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-here",
    "teacher_id": "teacher-uuid",
    "created_at": "2024-12-13T10:00:00Z",
    "updated_at": "2024-12-13T14:30:00Z",
    
    "terminology": {
      "type": "Course",
      "role": "Lecturer"
    },
    
    "schoolInfoHeaders": [
      "University of Ghana",
      "Department of Computer Science",
      "BSc Computer Science Program"
    ],
    
    "lectureInfo": {
      "left": [
        {"label": "Course Code", "value": "CS101"},
        {"label": "Course Title", "value": "Introduction to Programming"},
        {"label": "Course Lecturer", "value": "Dr. John Doe"},
        {"label": "Email", "value": "john.doe@university.edu"}
      ],
      "right": [
        {"label": "Credit Hour(s)", "value": "3"},
        {"label": "Office Hours", "value": "Mon-Wed 2-4pm"},
        {"label": "Room", "value": "Block A, Room 205"},
        {"label": "Phone", "value": "+233 20 123 4567"}
      ]
    },
    
    "courseObjectives": [
      "Understand fundamental programming concepts",
      "Apply problem-solving techniques using algorithms",
      "Develop proficiency in Python programming"
    ],
    
    "courseDescription": "This course introduces students to the fundamentals of programming using Python. Topics covered include variables, data types, control structures, functions, and basic object-oriented programming concepts.",
    
    "learningOutcomes": [
      "Students will be able to write basic Python programs",
      "Students will understand data types and control structures",
      "Students will be able to debug and test code"
    ],
    
    "courseDelivery": "Lectures (2 hours/week), Lab Sessions (2 hours/week), Group Projects, Online Resources via LMS",
    
    "courseContent": [
      {"week": 1, "topic": "Introduction to Programming", "activity": "Lecture + Lab Setup"},
      {"week": 2, "topic": "Variables and Data Types", "activity": "Lecture + Coding Exercises"},
      {"week": 3, "topic": "Control Structures (if/else)", "activity": "Lecture + Quiz 1"},
      {"week": 4, "topic": "Loops (for, while)", "activity": "Lecture + Lab Assignment 1"},
      {"week": 5, "topic": "Functions", "activity": "Lecture + Group Discussion"},
      {"week": 6, "topic": "Lists and Tuples", "activity": "Lecture + Coding Exercises"},
      {"week": 7, "topic": "Mid-Semester Review", "activity": "Revision + Mid-Semester Exam"},
      {"week": 8, "topic": "Dictionaries and Sets", "activity": "Lecture + Lab Assignment 2"},
      {"week": 9, "topic": "File Handling", "activity": "Lecture + Practical Session"},
      {"week": 10, "topic": "Error Handling", "activity": "Lecture + Debugging Workshop"},
      {"week": 11, "topic": "Introduction to OOP", "activity": "Lecture + Mini Project"},
      {"week": 12, "topic": "Final Project Presentations", "activity": "Student Presentations + Exam Prep"}
    ],
    
    "policies": [
      "Attendance is mandatory. More than 3 unexcused absences will result in a 5% grade reduction.",
      "Academic dishonesty (plagiarism, cheating) will result in automatic course failure and disciplinary action.",
      "Late submissions will be penalized 10% per day, up to a maximum of 3 days. After 3 days, submissions will not be accepted.",
      "All students must complete the mid-semester and final examinations. Make-up exams are only available for documented medical emergencies.",
      "Use of AI tools for assignments must be disclosed and properly cited according to department guidelines."
    ],
    
    "subjectName": "Computer Science",
    "className": "Year 1 - Group A",
    "academicYear": "2024/2025",
    "semester": "First Semester"
  }
}
```

### 3.2 Create Course Outline

**Endpoint:** `POST /api/course-outline`

**Request Body:**
```json
{
  "terminology": {
    "type": "Course",
    "role": "Lecturer"
  },
  "schoolInfoHeaders": ["Header 1", "Header 2"],
  "lectureInfo": {
    "left": [{"label": "Course Code", "value": "CS101"}],
    "right": [{"label": "Credit Hours", "value": "3"}]
  },
  "courseObjectives": ["Objective 1", "Objective 2"],
  "courseDescription": "Course description text...",
  "learningOutcomes": ["Outcome 1", "Outcome 2"],
  "courseDelivery": "Delivery methods...",
  "courseContent": [
    {"week": 1, "topic": "Topic 1", "activity": "Activity 1"}
  ],
  "policies": ["Policy 1", "Policy 2"],
  "subjectName": "Mathematics",
  "className": "Grade 10A",
  "academicYear": "2024/2025",
  "semester": "First Semester"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Course outline created successfully",
  "data": {
    "id": "new-uuid-here",
    ...full outline data...
  }
}
```

### 3.3 Update Course Outline

**Endpoint:** `PUT /api/course-outline/{id}`

**Request Body:** Same as POST (fields to update)

**Response:**
```json
{
  "success": true,
  "message": "Course outline updated successfully",
  "data": {
    ...updated outline data...
  }
}
```

### 3.4 Delete Course Outline

**Endpoint:** `DELETE /api/course-outline/{id}`

**Response:**
```json
{
  "success": true,
  "message": "Course outline deleted successfully"
}
```

### 3.5 List Course Outlines (for a teacher)

**Endpoint:** `GET /api/course-outlines`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-1",
      "subjectName": "Computer Science",
      "className": "Year 1 - Group A",
      "academicYear": "2024/2025",
      "semester": "First Semester",
      "updatedAt": "2024-12-13T14:30:00Z"
    },
    {
      "id": "uuid-2",
      "subjectName": "Mathematics",
      "className": "Year 2 - Group B",
      "academicYear": "2024/2025",
      "semester": "First Semester",
      "updatedAt": "2024-12-10T09:15:00Z"
    }
  ]
}
```

---

## 4. Data Field Specifications

### 4.1 School Info Headers
| Property | Type | Description |
|----------|------|-------------|
| Format | `string[]` | Array of strings |
| Min Items | 0 | Can be empty |
| Max Items | 10 | Reasonable limit |
| Item Max Length | 200 | Characters per header |
| Storage | JSONB | PostgreSQL JSONB column |

**Example:**
```json
["University Name", "Faculty of Science", "Department of Physics"]
```

### 4.2 Lecture Info
| Property | Type | Description |
|----------|------|-------------|
| Format | `{left: [{label, value}], right: [{label, value}]}` | Two-column structure |
| Min Items per side | 0 | Can be empty |
| Max Items per side | 20 | Reasonable limit |
| Label Max Length | 50 | Characters |
| Value Max Length | 200 | Characters |
| Storage | JSONB | PostgreSQL JSONB column |

**Example:**
```json
{
  "left": [
    {"label": "Course Code", "value": "PHYS201"},
    {"label": "Course Title", "value": "Classical Mechanics"}
  ],
  "right": [
    {"label": "Credit Hours", "value": "4"},
    {"label": "Semester", "value": "Fall 2024"}
  ]
}
```

### 4.3 Course Objectives / Learning Outcomes / Policies
| Property | Type | Description |
|----------|------|-------------|
| Format | `string[]` | Array of strings |
| Min Items | 1 | At least one empty string |
| Max Items | 50 | Reasonable limit |
| Item Max Length | 500 | Characters per item |
| Storage | JSONB | PostgreSQL JSONB column |

**Example:**
```json
["First objective", "Second objective", "Third objective"]
```

### 4.4 Course Content (Weekly Schedule)
| Property | Type | Description |
|----------|------|-------------|
| Format | `[{week, topic, activity}]` | Array of week objects |
| Min Items | 1 | At least one week |
| Max Items | 52 | Full year if needed |
| Topic Max Length | 300 | Characters |
| Activity Max Length | 500 | Characters |
| Storage | JSONB | PostgreSQL JSONB column |

**Example:**
```json
[
  {"week": 1, "topic": "Introduction", "activity": "Lecture + Discussion"},
  {"week": 2, "topic": "Fundamentals", "activity": "Lab Session"}
]
```

### 4.5 Text Fields (Description, Delivery)
| Property | Type | Description |
|----------|------|-------------|
| Format | `string` | Plain text |
| Max Length | 5000 | Characters |
| Storage | TEXT | PostgreSQL TEXT column |

---

## 5. API Response Data Format (READ Endpoint)

### CRITICAL: This section explains exactly how data should be returned from the backend to the frontend.

When the frontend calls `GET /api/course-outline` or `GET /api/course-outline/{id}`, the backend **MUST** return data in the following exact structure. The frontend React component (`TeacherLessonPack.jsx`) expects this specific format to populate its state.

### 5.1 Complete Response Structure

```json
{
  "success": true,
  "data": {
    // Metadata fields
    "id": "uuid-string",
    "teacherId": "uuid-string",
    "createdAt": "ISO-8601-datetime",
    "updatedAt": "ISO-8601-datetime",
    
    // Terminology settings (object with 2 properties)
    "terminology": {
      "type": "Course",      // String: "Course" or "Subject"
      "role": "Lecturer"     // String: "Lecturer" or "Teacher"
    },
    
    // Section 1: School Info Headers (array of strings)
    "schoolInfoHeaders": [
      "School/University Name",
      "Department/Faculty Name", 
      "Program/Course Name"
    ],
    
    // Section 2: Lecture Info (object with left and right arrays)
    "lectureInfo": {
      "left": [
        { "label": "Course Code", "value": "CS101" },
        { "label": "Course Title", "value": "Programming Fundamentals" },
        { "label": "Course Lecturer", "value": "Dr. John Smith" },
        { "label": "Email", "value": "john.smith@university.edu" }
      ],
      "right": [
        { "label": "Credit Hour(s)", "value": "3" },
        { "label": "Office Hours", "value": "Mon-Wed 2-4pm" },
        { "label": "Room", "value": "Block A, Room 101" },
        { "label": "Phone", "value": "+233 20 123 4567" }
      ]
    },
    
    // Section 3: Course Objectives (array of strings)
    "courseObjectives": [
      "First learning objective text",
      "Second learning objective text",
      "Third learning objective text"
    ],
    
    // Section 4: Course Description (single string)
    "courseDescription": "Full text description of the course...",
    
    // Section 5: Learning Outcomes (array of strings)
    "learningOutcomes": [
      "First expected outcome",
      "Second expected outcome",
      "Third expected outcome"
    ],
    
    // Section 6: Course Delivery (single string)
    "courseDelivery": "Description of teaching/delivery methods...",
    
    // Section 7: Course Content Table (array of week objects)
    "courseContent": [
      { "topic": "Week 1 Topic Text", "activity": "Week 1 Activity Text" },
      { "topic": "Week 2 Topic Text", "activity": "Week 2 Activity Text" },
      { "topic": "Week 3 Topic Text", "activity": "Week 3 Activity Text" }
    ],
    
    // Section 8: Policies (array of strings)
    "policies": [
      "First policy text",
      "Second policy text",
      "Third policy text"
    ],
    
    // Optional metadata for integration
    "subjectName": "Computer Science",
    "className": "Year 1 - Group A",
    "academicYear": "2024/2025",
    "semester": "First Semester"
  }
}
```

### 5.2 Database-to-Response Field Transformation

The backend must transform database column names (snake_case) to response field names (camelCase):

| Database Column | Response Field | Transformation |
|-----------------|----------------|----------------|
| `id` | `id` | Direct copy |
| `teacher_id` | `teacherId` | snake_case → camelCase |
| `created_at` | `createdAt` | snake_case → camelCase + ISO-8601 format |
| `updated_at` | `updatedAt` | snake_case → camelCase + ISO-8601 format |
| `terminology_type` | `terminology.type` | Nest under `terminology` object |
| `terminology_role` | `terminology.role` | Nest under `terminology` object |
| `school_info_headers` | `schoolInfoHeaders` | Direct JSONB parse |
| `lecture_info` | `lectureInfo` | Direct JSONB parse |
| `course_objectives` | `courseObjectives` | Direct JSONB parse |
| `course_description` | `courseDescription` | Direct copy |
| `learning_outcomes` | `learningOutcomes` | Direct JSONB parse |
| `course_delivery` | `courseDelivery` | Direct copy |
| `course_content` | `courseContent` | Direct JSONB parse (see special note below) |
| `policies` | `policies` | Direct JSONB parse |
| `subject_name` | `subjectName` | snake_case → camelCase |
| `class_name` | `className` | snake_case → camelCase |
| `academic_year` | `academicYear` | snake_case → camelCase |
| `semester` | `semester` | Direct copy |

### 5.3 Special Data Structure Notes

#### Course Content Array
The `courseContent` array should contain objects with only `topic` and `activity` properties (NO `week` property). The week number is determined by the array index (index 0 = Week 1, index 1 = Week 2, etc.):

```json
// ✅ CORRECT format (frontend expects this)
"courseContent": [
  { "topic": "Introduction", "activity": "Lecture + Discussion" },
  { "topic": "Variables", "activity": "Lab Session" }
]

// ❌ WRONG format (do NOT include week number in object)
"courseContent": [
  { "week": 1, "topic": "Introduction", "activity": "Lecture + Discussion" }
]
```

#### Lecture Info Structure
Each item in `lectureInfo.left` and `lectureInfo.right` must have exactly two properties:
- `label`: String - the field name (e.g., "Course Code")
- `value`: String - the field value (e.g., "CS101")

```json
// ✅ CORRECT format
{ "label": "Course Code", "value": "CS101" }

// ❌ WRONG formats
{ "name": "Course Code", "content": "CS101" }
{ "key": "Course Code", "val": "CS101" }
```

#### Empty Arrays
When there is no data for a dynamic array field, return an array with one empty string (not an empty array):

```json
// ✅ CORRECT - user can immediately start typing in the first field
"courseObjectives": [""]
"learningOutcomes": [""]
"policies": [""]
"schoolInfoHeaders": ["", "", ""]

// ❌ WRONG - frontend has no input fields to show
"courseObjectives": []
```

#### Empty Course Content
For empty course content, return an array of 12 empty week objects:

```json
// ✅ CORRECT - shows 12 week rows ready for input
"courseContent": [
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" },
  { "topic": "", "activity": "" }
]
```

### 5.4 Example Backend Transformation (Pseudocode)

```python
def format_outline_response(db_row):
    return {
        "success": True,
        "data": {
            "id": str(db_row.id),
            "teacherId": str(db_row.teacher_id),
            "createdAt": db_row.created_at.isoformat(),
            "updatedAt": db_row.updated_at.isoformat(),
            
            "terminology": {
                "type": db_row.terminology_type or "Course",
                "role": db_row.terminology_role or "Lecturer"
            },
            
            "schoolInfoHeaders": json.loads(db_row.school_info_headers) or ["", "", ""],
            "lectureInfo": json.loads(db_row.lecture_info) or {"left": [], "right": []},
            "courseObjectives": json.loads(db_row.course_objectives) or [""],
            "courseDescription": db_row.course_description or "",
            "learningOutcomes": json.loads(db_row.learning_outcomes) or [""],
            "courseDelivery": db_row.course_delivery or "",
            "courseContent": json.loads(db_row.course_content) or [{"topic": "", "activity": ""} for _ in range(12)],
            "policies": json.loads(db_row.policies) or [""],
            
            "subjectName": db_row.subject_name,
            "className": db_row.class_name,
            "academicYear": db_row.academic_year,
            "semester": db_row.semester
        }
    }
```

### 5.5 For Empty/New Outline (Default Response)

When creating a new outline or when no data exists, return this default structure:

```json
{
  "success": true,
  "data": {
    "id": null,
    "terminology": {
      "type": "Course",
      "role": "Lecturer"
    },
    "schoolInfoHeaders": ["", "", ""],
    "lectureInfo": {
      "left": [
        { "label": "Course Code", "value": "" },
        { "label": "Course Title", "value": "" },
        { "label": "Course Lecturer", "value": "" },
        { "label": "Email", "value": "" }
      ],
      "right": [
        { "label": "Credit Hour(s)", "value": "" },
        { "label": "Office Hours", "value": "" },
        { "label": "Room", "value": "" },
        { "label": "Phone", "value": "" }
      ]
    },
    "courseObjectives": [""],
    "courseDescription": "",
    "learningOutcomes": [""],
    "courseDelivery": "",
    "courseContent": [
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" },
      { "topic": "", "activity": "" }
    ],
    "policies": [""],
    "subjectName": null,
    "className": null,
    "academicYear": null,
    "semester": null
  }
}
```

---

## 6. Frontend-to-Backend Field Mapping

| Frontend State Field | Database Column | Type |
|---------------------|-----------------|------|
| `terminology.type` | `terminology_type` | VARCHAR(20) |
| `terminology.role` | `terminology_role` | VARCHAR(20) |
| `lessonData.schoolInfoHeaders` | `school_info_headers` | JSONB |
| `lessonData.lectureInfo` | `lecture_info` | JSONB |
| `lessonData.courseObjectives` | `course_objectives` | JSONB |
| `lessonData.courseDescription` | `course_description` | TEXT |
| `lessonData.learningOutcomes` | `learning_outcomes` | JSONB |
| `lessonData.courseDelivery` | `course_delivery` | TEXT |
| `lessonData.courseContent` | `course_content` | JSONB |
| `lessonData.policies` | `policies` | JSONB |

---

## 7. Auto-Save & Draft Support

The interface should support:
1. **Auto-save** - Save draft every 30 seconds if changes detected
2. **Draft status** - Track if outline is draft or published
3. **Version history** - Optional: keep previous versions

Add to database:
```sql
ALTER TABLE course_outlines ADD COLUMN status VARCHAR(20) DEFAULT 'draft';
-- status: 'draft', 'published', 'archived'

ALTER TABLE course_outlines ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE course_outlines ADD COLUMN last_auto_save TIMESTAMP WITH TIME ZONE;
```

---

## 8. Integration Points

### 7.1 Timetable Integration
- `subject_name` and `class_name` can link to timetable data
- Pre-populate fields based on selected subject/class

### 7.2 Semester Mapper Integration
- `course_content` weeks can be linked to strand/substrand weeks
- Import topic organization from semester planning

### 7.3 PDF Export
- API can optionally return a pre-rendered PDF
- Endpoint: `GET /api/course-outline/{id}/pdf`

---

## 9. Validation Rules

| Field | Validation |
|-------|------------|
| `schoolInfoHeaders` | Each item max 200 chars, max 10 items |
| `lectureInfo.*.label` | Required, max 50 chars |
| `lectureInfo.*.value` | Max 200 chars |
| `courseObjectives` | Each item max 500 chars, max 50 items |
| `learningOutcomes` | Each item max 500 chars, max 50 items |
| `policies` | Each item max 500 chars, max 50 items |
| `courseDescription` | Max 5000 chars |
| `courseDelivery` | Max 2000 chars |
| `courseContent.topic` | Max 300 chars |
| `courseContent.activity` | Max 500 chars |
| `courseContent` | Max 52 weeks |

---

## 10. Error Responses

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Course objectives cannot exceed 50 items",
    "field": "courseObjectives"
  }
}
```

Common error codes:
- `VALIDATION_ERROR` - Input validation failed
- `NOT_FOUND` - Outline not found
- `UNAUTHORIZED` - User not authorized
- `DUPLICATE_ENTRY` - Outline already exists for this subject/class/semester

---

## 11. Summary

This specification defines a flexible database schema and API for the Course Outline interface that:

1. ✅ Supports **dynamic arrays** for all list-based sections (headers, objectives, outcomes, policies, content)
2. ✅ Uses **JSONB** storage for efficient querying and flexible schema
3. ✅ Maintains **proper relationships** via teacher_id foreign key
4. ✅ Supports **terminology switching** between Course/Subject and Lecturer/Teacher
5. ✅ Provides **RESTful API** endpoints for CRUD operations
6. ✅ Returns data in a **frontend-friendly format** matching the React state structure
7. ✅ Includes **metadata fields** for integration with other modules (timetable, semester mapper)
