# Weekly Lesson Notes API Documentation

## Overview

This API provides endpoints for reading and updating weekly lesson notes generated for teachers. Lesson notes are auto-generated on Wednesday/Thursday midnight (local time) but can be edited by teachers.

**Important**: A subject+class combination may have **multiple lesson notes** if there are multiple indicators scheduled for that week. Each indicator gets its own lesson note document.

## Base URL

```
/api/teacher
```

## Authentication

All endpoints require a Bearer JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

---

## Endpoints

### 1. GET /lesson-notes

**Get all lesson notes for a subject+class (returns a LIST)**

#### Request

```
GET /api/teacher/lesson-notes?subject=Mathematics&class_name=Class%208&week_date=2025-12-20
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | ✅ | Subject name (e.g., "Mathematics") |
| `class_name` | string | ✅ | Class name (e.g., "Class 8") |
| `week_date` | date | ❌ | Friday date (YYYY-MM-DD). Defaults to most recent week. |

#### Response

```json
{
  "subject": "Mathematics",
  "class_name": "Class 8",
  "week_date": "2025-12-20",
  "total_count": 2,
  "lesson_notes": [
    {
      "id": "e37bd0c9-f761-48fe-80b0-82c4213de6f7",
      "teacher_id": "a1b2c3d4-...",
      "subject": "Mathematics",
      "class_name": "Class 8",
      "indicator_id": 45,
      "week_date": "2025-12-20",
      "duration": "12:00 - 13:00",
      "strand": "Number Operations",
      "substrand": "Fractions",
      "content_standard": "Demonstrate understanding of operations on fractions",
      "content_standard_code": "B8.1.2.1",
      "indicator_text": "Solve problems involving addition of fractions",
      "indicator_code": "IND1.2.1.1",
      "class_size": null,
      "week_number": 8,
      "semester_name": "First Semester 2024/2025",
      "lesson_number": "1 of 2",
      "performance_indicator": "By the end of the lesson, learners will be able to add fractions with unlike denominators...",
      "core_competency": "Critical thinking, Problem-solving, Communication",
      "reference_page": "Mathematics curriculum",
      "phase1": {
        "activity": "Draw a circle on the board and ask learners to identify fractions...",
        "resources": "Whiteboard, markers, fraction cards"
      },
      "phase2": {
        "activity": "Present step-by-step method for adding fractions with unlike denominators...",
        "resources": "Textbook, worksheets, colored paper"
      },
      "phase3": {
        "activity": "Use peer discussion to summarize key learning points...",
        "resources": "Exercise books"
      },
      "generated_at": "2025-12-18T08:30:48.000Z",
      "updated_at": "2025-12-18T08:30:48.000Z"
    },
    {
      "id": "f48ce1da-...",
      "lesson_number": "2 of 2",
      "indicator_code": "IND1.2.1.2",
      "...": "..."
    }
  ]
}
```

---

### 2. GET /lesson-notes/{note_id}

**Get a single lesson note by ID**

#### Request

```
GET /api/teacher/lesson-notes/e37bd0c9-f761-48fe-80b0-82c4213de6f7
```

#### Response

Returns a single `LessonNoteResponse` object (same structure as items in the list above).

---

### 3. GET /lesson-notes/weeks

**Get available week dates for a subject+class**

Useful for building a week selector dropdown.

#### Request

```
GET /api/teacher/lesson-notes/weeks?subject=Mathematics&class_name=Class%208
```

#### Response

```json
[
  "2025-12-20",
  "2025-12-13",
  "2025-12-06"
]
```

---

### 4. PUT /lesson-notes/{note_id}

**Update a lesson note (teacher edits)**

Only provided fields will be updated.

#### Request

```
PUT /api/teacher/lesson-notes/e37bd0c9-f761-48fe-80b0-82c4213de6f7
```

**Body:**

```json
{
  "class_size": "35",
  "performance_indicator": "Updated performance indicator text...",
  "core_competency": "Updated competencies...",
  "phase1_activity": "Modified starter activity...",
  "phase1_resources": "Modified resources...",
  "phase2_activity": "Modified main learning activity...",
  "phase2_resources": "Modified resources...",
  "phase3_activity": "Modified reflection activity...",
  "phase3_resources": "Modified resources..."
}
```

**All fields are optional** - only include the fields you want to update.

| Field | Type | Description |
|-------|------|-------------|
| `class_size` | string | Class size (teacher fills this) |
| `performance_indicator` | string | Edit AI-generated content |
| `core_competency` | string | Edit AI-generated content |
| `phase1_activity` | string | Phase 1: Starter - Activity |
| `phase1_resources` | string | Phase 1: Starter - Resources |
| `phase2_activity` | string | Phase 2: New Learning - Activity |
| `phase2_resources` | string | Phase 2: New Learning - Resources |
| `phase3_activity` | string | Phase 3: Reflection - Activity |
| `phase3_resources` | string | Phase 3: Reflection - Resources |

#### Response

Returns the updated `LessonNoteResponse` object.

---

### 5. POST /lesson-notes

**Create or update a lesson note (UPSERT)**

If a lesson note with the same `(subject, class_name, indicator_id, week_date)` exists, it will be updated.

#### Request

```
POST /api/teacher/lesson-notes
```

**Body:**

```json
{
  "subject": "Mathematics",
  "class_name": "Class 8",
  "indicator_id": 45,
  "week_date": "2025-12-20",
  "duration": "12:00 - 13:00",
  "strand": "Number Operations",
  "substrand": "Fractions",
  "content_standard": "...",
  "content_standard_code": "B8.1.2.1",
  "indicator_text": "...",
  "indicator_code": "IND1.2.1.1",
  "class_size": "35",
  "week_number": 8,
  "semester_name": "First Semester 2024/2025",
  "lesson_number": "1 of 2",
  "performance_indicator": "...",
  "core_competency": "...",
  "reference_page": "Mathematics curriculum",
  "phase1_activity": "...",
  "phase1_resources": "...",
  "phase2_activity": "...",
  "phase2_resources": "...",
  "phase3_activity": "...",
  "phase3_resources": "..."
}
```

**Required fields:**
- `subject`
- `class_name`
- `week_date`

All other fields are optional.

#### Response

Returns the created/updated `LessonNoteResponse` object.

---

## Data Model

### LessonNoteResponse

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier |
| `teacher_id` | UUID | Teacher who owns this note |
| `subject` | string | Subject name |
| `class_name` | string | Class name |
| `indicator_id` | int? | Reference to curriculum indicator |
| `week_date` | date | Friday of the week (always a Friday) |
| `duration` | string? | From timetable, e.g., "12:00 - 13:00" |
| `strand` | string? | Curriculum strand |
| `substrand` | string? | Curriculum substrand |
| `content_standard` | string? | Content standard text |
| `content_standard_code` | string? | Content standard code |
| `indicator_text` | string? | Learning indicator text |
| `indicator_code` | string? | Learning indicator code |
| `class_size` | string? | Empty for teacher to fill |
| `week_number` | int? | Calculated week number |
| `semester_name` | string? | Current semester name |
| `lesson_number` | string? | e.g., "1 of 3" |
| `performance_indicator` | string? | AI-generated, editable |
| `core_competency` | string? | AI-generated, editable |
| `reference_page` | string? | Reference page info |
| `phase1` | PhaseContent | Phase 1: Starter |
| `phase2` | PhaseContent | Phase 2: New Learning |
| `phase3` | PhaseContent | Phase 3: Reflection |
| `generated_at` | datetime? | When AI generated this |
| `updated_at` | datetime? | Last update time |

### PhaseContent

| Field | Type | Description |
|-------|------|-------------|
| `activity` | string | Learner activity description |
| `resources` | string | Teaching/learning resources |

---

## Frontend Implementation Notes

### 1. Fetching Lesson Notes

Since there may be **multiple lesson notes per subject+class**, the frontend should:

```javascript
// Fetch lesson notes
const response = await fetch('/api/teacher/lesson-notes?subject=Mathematics&class_name=Class%208', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const data = await response.json();

// data.total_count tells you how many notes exist
// data.lesson_notes is the array of notes

if (data.total_count === 1) {
  // Single lesson note - display directly
} else {
  // Multiple lesson notes - show a selector or accordion
  // The lesson_number field (e.g., "1 of 3") helps identify each note
}
```

### 2. Displaying Lesson Notes

Suggested UI structure:

```
┌─────────────────────────────────────────────────────────────┐
│ Mathematics - Class 8 | Week: Dec 20, 2025                  │
│ [Week Selector Dropdown]                                    │
├─────────────────────────────────────────────────────────────┤
│ Showing 2 Lesson Notes for this week                        │
├─────────────────────────────────────────────────────────────┤
│ ▼ Lesson 1 of 2: IND1.2.1.1 - Addition of Fractions         │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ Date: Dec 20, 2025    Duration: 12:00 - 13:00       │   │
│   │ Class Size: [  35  ]  (editable)                    │   │
│   │ Strand: Number Operations                           │   │
│   │ Substrand: Fractions                                │   │
│   │ ...                                                 │   │
│   │ Performance Indicator: [textarea - editable]         │   │
│   │ Core Competency: [textarea - editable]               │   │
│   ├─────────────────────────────────────────────────────┤   │
│   │ Phase 1: Starter                                    │   │
│   │ Activity: [textarea]  Resources: [textarea]          │   │
│   ├─────────────────────────────────────────────────────┤   │
│   │ Phase 2: New Learning                               │   │
│   │ Activity: [textarea]  Resources: [textarea]          │   │
│   ├─────────────────────────────────────────────────────┤   │
│   │ Phase 3: Reflection                                 │   │
│   │ Activity: [textarea]  Resources: [textarea]          │   │
│   └─────────────────────────────────────────────────────┘   │
│ ► Lesson 2 of 2: IND1.2.1.2 - Subtraction of Fractions      │
└─────────────────────────────────────────────────────────────┘
[Save Changes]
```

### 3. Updating Lesson Notes

When the teacher edits a lesson note:

```javascript
// Update a single note
const updateData = {
  class_size: "35",
  performance_indicator: "Updated text...",
  phase1_activity: "Updated activity..."
};

await fetch(`/api/teacher/lesson-notes/${noteId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(updateData)
});
```

### 4. Week Navigation

Use the `/lesson-notes/weeks` endpoint to populate a week selector:

```javascript
// Get available weeks
const weeks = await fetch('/api/teacher/lesson-notes/weeks?subject=Mathematics&class_name=Class%208');
// Returns: ["2025-12-20", "2025-12-13", "2025-12-06"]

// Then fetch specific week
const notes = await fetch(`/api/teacher/lesson-notes?subject=Mathematics&class_name=Class%208&week_date=${selectedWeek}`);
```

---

## Error Responses

| Status | Description |
|--------|-------------|
| 401 | Unauthorized - Invalid or missing token |
| 404 | Not found - No lesson notes found for the query |
| 400 | Bad request - Invalid parameters |
| 500 | Server error |

Example error response:

```json
{
  "detail": "No lesson notes found for Mathematics - Class 8"
}
```

---

## Notes

1. **Lesson notes are auto-generated** on Wednesday/Thursday at midnight (local time based on teacher's country)
2. **Multiple notes per subject+class** are possible if multiple indicators are scheduled for the week
3. **The `week_date` is always a Friday** - it represents the Friday of the current week when generating for the coming week
4. **Use the `lesson_number` field** (e.g., "1 of 3") to show users which indicator/lesson they're viewing
5. **All AI-generated fields are editable** - teachers can modify the content to suit their needs
