# Student Support Pack API Documentation

## Overview

The Student Support Pack API provides endpoints for creating personalized lesson packs 
tailored to individual students based on their interests, health considerations, and learning needs.

## Base URL
```
/api/teacher/student-support
```

---

## Authentication

All endpoints require teacher authentication via JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## Endpoints

### 1. Create Student Support Pack

**POST** `/api/teacher/student-support`

Creates a new personalized student support pack. The generation runs in the background.

#### Request Body

```typescript
interface CreateRequest {
  student_name: string;        // Required: Name of the student
  subject: string;             // Required: Subject (e.g., "Science", "Mathematics")
  class_name: string;          // Required: Class name (e.g., "Basic 8", "Class 10A")
  topic: string;               // Required: Topic to cover
  interests: string[];         // Optional: Student's interests for personalization
  health_considerations?: string; // Optional: Health issues or special considerations
}
```

#### Example Request

```javascript
const response = await fetch('/api/teacher/student-support', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    student_name: "John Smith",
    subject: "Science",
    class_name: "Basic 8",
    topic: "The Water Cycle",
    interests: ["football", "video games", "music"],
    health_considerations: "Student has ADHD - needs frequent breaks and visual aids"
  })
});
```

#### Response

```json
{
  "message": "Student support pack created. Generation will start when worker picks it up.",
  "pack_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "student_name": "John Smith",
  "topic": "The Water Cycle",
  "note": "Run 'python student_back/run_workers.py' to start background processing"
}
```

#### Status Codes
- `200` - Pack created successfully
- `400` - Invalid request
- `401` - Unauthorized
- `500` - Server error

#### Important: Running the Worker

The pack is created with `pending` status. To generate content, you need to run the background worker:

```bash
# From project root
python student_back/run_workers.py
```

This starts 2 worker processes that poll the database for pending packs and generate content.

---

### 2. List Student Support Packs

**GET** `/api/teacher/student-support`

Returns all student support packs for a specific subject and class.
Click on a pack to get full details using the pack_id.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | **Yes** | Subject name (e.g., "Science") |
| `class_name` | string | **Yes** | Class name (e.g., "Basic 8") |
| `status` | string | No | Filter by status (`pending`, `processing`, `completed`, `failed`) |

#### Example Request

```javascript
const response = await fetch('/api/teacher/student-support?subject=Science&class_name=Basic 8', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

#### Response

```typescript
interface ListItem {
  id: string;           // UUID
  student_name: string;
  subject: string;
  class_name: string;
  topic: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;   // ISO datetime
}
```

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "student_name": "John Smith",
    "subject": "Science",
    "class_name": "Basic 8",
    "topic": "The Water Cycle",
    "status": "completed",
    "created_at": "2024-12-30T19:00:00Z"
  }
]
```

---

### 3. Get Student Support Pack (Full Details)

**GET** `/api/teacher/student-support/{pack_id}`

Returns the full pack including all slides and content.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `pack_id` | UUID | The pack ID |

#### Example Request

```javascript
const response = await fetch(`/api/teacher/student-support/${packId}`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

#### Response

```typescript
interface StudentSupportPackResponse {
  id: string;                     // UUID
  teacher_id: string;             // UUID
  student_name: string;
  subject: string;
  class_name: string;
  edu_sys?: string;               // Education system (auto-fetched)
  edu_lvl?: string;               // Education level (auto-fetched)
  topic: string;
  interests: string[];
  health_considerations?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;             // ISO datetime
  updated_at: string;             // ISO datetime
  teacher_instructions?: string;  // Special instructions for the teacher
  
  // Structured content (available when status = 'completed')
  pack_id?: string;
  generated_at?: string;
  slides: Slide[];
  summary?: Summary;
}

interface Slide {
  id: string;                     // e.g., "slide-1"
  type: SlideType;
  layout: string;
  content: SlideContent;
}

interface SlideContent {
  title?: string;
  subtitle?: string;
  html_content?: string;          // HTML formatted content
  description?: string;
  images?: Image[];               // For visual_gallery type
  questions?: Question[];         // For assessment types
  answers?: Answer[];             // For answer_key types
  instructions?: string;
  note?: string;
}

interface Image {
  gcs_path: string;
  image_url: string;              // Signed URL (valid for 60 mins)
  alt_text: string;
  caption: string;
}

interface Summary {
  total_slides: number;
  has_notes: boolean;
  image_count: number;
  has_teacher_instructions: boolean;
  mcq_count: number;
  essay_count: number;
}

type SlideType = 
  | 'title'             // Title slide
  | 'profile'           // Student profile/intro
  | 'visual_gallery'    // Images
  | 'notes'             // Learning notes (HTML)
  | 'teacher_notes'     // Teacher instructions
  | 'assessment_mcq'    // MCQ questions
  | 'assessment_essay'  // Essay questions
  | 'answer_key_mcq'    // MCQ answers
  | 'answer_key_essay'; // Essay answers
```

#### Example Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "teacher_id": "123e4567-e89b-12d3-a456-426614174000",
  "student_name": "John Smith",
  "subject": "Science",
  "class_name": "Basic 8",
  "edu_sys": "Ghana Education Service",
  "edu_lvl": "JHS",
  "topic": "The Water Cycle",
  "interests": ["football", "video games", "music"],
  "health_considerations": "Student has ADHD - needs frequent breaks",
  "status": "completed",
  "created_at": "2024-12-30T19:00:00Z",
  "updated_at": "2024-12-30T19:05:00Z",
  "teacher_instructions": "This student requires frequent breaks...",
  "pack_id": "abc123",
  "generated_at": "2024-12-30T19:05:00Z",
  "slides": [
    {
      "id": "slide-1",
      "type": "title",
      "layout": "title_center",
      "content": {
        "title": "Personalized Learning Pack: The Water Cycle",
        "subtitle": "Prepared for John Smith - Science (Basic 8)"
      }
    },
    {
      "id": "slide-2",
      "type": "visual_gallery",
      "layout": "image_grid",
      "content": {
        "title": "Visual Learning Aids",
        "description": "These diagrams will help you understand the key concepts.",
        "images": [
          {
            "gcs_path": "student_support/550e8400/image_1.png",
            "image_url": "https://storage.googleapis.com/...?signed...",
            "alt_text": "Water cycle diagram",
            "caption": "Visual aid for understanding The Water Cycle"
          }
        ]
      }
    }
  ],
  "summary": {
    "total_slides": 8,
    "has_notes": true,
    "image_count": 3,
    "has_teacher_instructions": true,
    "mcq_count": 5,
    "essay_count": 2
  }
}
```

---

### 4. Update Student Support Pack

**PUT** `/api/teacher/student-support/{pack_id}`

Updates text sections of a support pack (teacher instructions or notes).

#### Request Body

```typescript
interface UpdateRequest {
  teacher_instructions?: string;  // New teacher instructions
  notes_update?: string;          // New notes content (HTML)
}
```

#### Example Request

```javascript
const response = await fetch(`/api/teacher/student-support/${packId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    teacher_instructions: "Updated instructions for handling this lesson..."
  })
});
```

#### Response

```json
{
  "message": "Support pack updated successfully",
  "pack_id": "550e8400-e29b-41d4-a716-446655440000",
  "updated_fields": ["pack_id", "instructions"]
}
```

---

## Polling for Status

Since pack generation runs in the background, you should poll for status updates:

```javascript
async function waitForCompletion(packId, maxWaitSeconds = 120) {
  const pollInterval = 3000; // 3 seconds
  const maxAttempts = maxWaitSeconds * 1000 / pollInterval;
  
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`/api/teacher/student-support/${packId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    
    if (data.status === 'completed') {
      return data;  // Pack is ready
    }
    
    if (data.status === 'failed') {
      throw new Error('Pack generation failed');
    }
    
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  throw new Error('Timeout waiting for pack generation');
}
```

---

## React Hook Example

```typescript
import { useState, useCallback } from 'react';

interface UseStudentSupportResult {
  createPack: (data: CreateRequest) => Promise<string>;
  getPack: (packId: string) => Promise<StudentSupportPackResponse>;
  updatePack: (packId: string, updates: UpdateRequest) => Promise<void>;
  listPacks: (filters?: ListFilters) => Promise<ListItem[]>;
  loading: boolean;
  error: string | null;
}

export function useStudentSupport(): UseStudentSupportResult {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const createPack = useCallback(async (data: CreateRequest) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/teacher/student-support', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });
      
      if (!response.ok) throw new Error('Failed to create pack');
      
      const result = await response.json();
      return result.pack_id;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  
  // ... other methods
  
  return { createPack, getPack, updatePack, listPacks, loading, error };
}
```

---

## Status Values

| Status | Description |
|--------|-------------|
| `pending` | Pack is queued for generation |
| `processing` | Pack is currently being generated |
| `completed` | Pack generation successful, content available |
| `failed` | Pack generation failed |

---

## Notes

1. **Image URLs**: The `image_url` in the response is a signed URL valid for 60 minutes. 
   Refresh the pack data if images fail to load due to expired URLs.

2. **Teacher Instructions**: These are special notes for the teacher about how to handle
   the lesson considering the student's specific needs.

3. **Generation Time**: Pack generation typically takes 30-90 seconds depending on content complexity.

4. **Rate Limits**: Please limit requests to a reasonable rate (1-2 per second max).
