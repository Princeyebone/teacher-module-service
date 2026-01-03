# Lesson Brief API Specification

## Overview

The Lesson Brief API provides **read-only** endpoints for fetching AI-generated lesson briefs. These briefs are designed to give teachers a quick, actionable overview of their upcoming lesson, readable in under 5 minutes.

**Base URL:** `/api/teacher`

---

## Endpoints

### 1. Get Lesson Brief by ID

```
GET /api/teacher/lesson-brief/{brief_id}
```

**Description:** Fetch a specific lesson brief by its unique ID.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `brief_id` | integer | Unique ID of the lesson brief |

**Response:** `LessonBriefResponse`

---

### 2. Get Lesson Brief by Query Parameters

```
GET /api/teacher/lesson-brief?subject=Mathematics&class_name=Class 8&session_date=2024-09-18
```

**Description:** Fetch a lesson brief by filtering on subject, class, and date. This is the **primary endpoint** for fetching a specific lesson brief.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | ✅ Yes | Subject name (e.g., "Mathematics", "English") |
| `class_name` | string | ✅ Yes | Class name (e.g., "Class 8", "Class 10A") |
| `session_date` | date | ✅ Yes | Session date in `YYYY-MM-DD` format |

**Response:** `LessonBriefResponse`

---

### 3. Get Today's Lesson Brief (Convenience)

```
GET /api/teacher/lesson-brief/today/{subject}/{class_name}
```

**Description:** Shorthand endpoint to get today's lesson brief for a specific subject and class automatically uses today's date.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `subject` | string | Subject name |
| `class_name` | string | Class name |

**Response:** `LessonBriefResponse`

---

### 4. List Lesson Briefs

```
GET /api/teacher/lesson-briefs
```

**Description:** List all lesson briefs for the current teacher with optional filters. Returns compact list items with previews (not full content).

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | No | Filter by subject |
| `class_name` | string | No | Filter by class |
| `from_date` | date | No | Filter from date |
| `to_date` | date | No | Filter to date |
| `limit` | integer | No | Max results (default: 20, max: 100) |
| `offset` | integer | No | Pagination offset (default: 0) |

**Response:** `LessonBriefListResponse`

---

## Response Schemas

### LessonBriefResponse

The full lesson brief response containing markdown-formatted content.

```json
{
  "id": 123,
  "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
  "subject": "Mathematics",
  "class_name": "Class 8",
  "session_date": "2024-09-18",
  "session_id": 1604,
  "previous_session_id": 1603,
  "brief_content": "**LESSON BRIEF: Class 8 Mathematics**\n**Teacher: Prince Yeboah**\n\n---\n\n**Quick Recap**\n\nYesterday, we mastered manipulating and simplifying algebraic expressions...\n\n---\n\n**Lesson Hook**\n\nEvery time you throw a ball, launch a rocket, or even just sneeze...\n\n---\n\n...",
  "created_at": "2024-09-18T06:00:00.000Z",
  "updated_at": "2024-09-18T06:00:00.000Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique ID of the brief |
| `teacher_id` | UUID | Teacher's unique ID |
| `subject` | string | Subject name |
| `class_name` | string | Class name |
| `session_date` | date | Date of the lesson |
| `session_id` | integer | Current session ID (nullable) |
| `previous_session_id` | integer | Previous session ID (nullable) |
| `brief_content` | string | **Full lesson brief in Markdown format** |
| `created_at` | datetime | When the brief was created |
| `updated_at` | datetime | When the brief was last updated |

---

### LessonBriefListResponse

Response for listing multiple briefs (compact, no full content).

```json
{
  "briefs": [
    {
      "id": 123,
      "subject": "Mathematics",
      "class_name": "Class 8",
      "session_date": "2024-09-18",
      "created_at": "2024-09-18T06:00:00.000Z",
      "preview": "**LESSON BRIEF: Class 8 Mathematics**\n**Teacher: Prince Yeboah**\n\n---\n\n**Quick Recap**\n\nYesterday, we mastered manipulating..."
    }
  ],
  "total_count": 45
}
```

---

## Brief Content Structure (Markdown Format)

The `brief_content` field contains a **Markdown-formatted** lesson brief with the following sections:

```markdown
**LESSON BRIEF: [Class Name] [Subject]**
**Teacher: [Teacher Name]**
**Date: [Today's Date]**

---

**Quick Recap**
[1-2 sentences about what was covered in the previous lesson and key concepts students should already know]

---

**Lesson Hook**
[A SHOCKING, topic-related opening statement followed by a transition like "Today, we'll find out..."]

---

**Today's Focus**
[2-3 sentences about the main topic and learning objectives]

---

**Key Points to Cover**

1.  **[Point 1 Title]**
    *   **Explanation:** [Clear explanation]
    *   **Example:** [Concrete example]
    *   **Connection:** [How it connects to what students know]

2.  **[Point 2 Title]**
    *   ...

[5-7 main points with sub-points]

---

**Quick Activity Suggestion**
[A simple mid-lesson activity to engage students]

---

**Connection to Weekly Goal**
[How today's lesson contributes to the week's objective]

---

**Ready-to-Use Resources**

a) **Presentation Slides**: [Information about auto-generated slides in "Lesson Slides" section]

b) **Student-Specific Support**: [Information about "Student Support" feature for personalized materials]
```

---

## Frontend Display Recommendations

1. **Parse Markdown**: Use a markdown renderer (e.g., `react-markdown`, `marked.js`) to display the `brief_content`.

2. **Collapsible Sections**: Consider making each major section (Quick Recap, Lesson Hook, Key Points, etc.) collapsible for easy navigation.

3. **Print-Friendly**: The brief should be printable for teachers who prefer paper.

4. **Time Indicator**: Show "5-minute read" or estimated read time.

5. **Key Points Highlighting**: The Key Points section is the most detailed - consider special styling.

6. **Resource Links**: The "Ready-to-Use Resources" section will eventually link to:
   - Lesson Slides page
   - Student Support feature

---

## Error Responses

| Status Code | Description |
|-------------|-------------|
| 404 | Lesson brief not found |
| 401 | Unauthorized (invalid/missing token) |
| 422 | Validation error (invalid query params) |

---

## Authentication

All endpoints require a valid JWT token in the `Authorization` header:

```
Authorization: Bearer <token>
```
