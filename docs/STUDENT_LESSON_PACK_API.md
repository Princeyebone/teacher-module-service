# Student Lesson Pack API Documentation

## Overview

The Student Lesson Pack API provides endpoints to read and update AI-generated student lesson packs. These packs are automatically generated after teacher slides are created and include:

- **Simplified Notes**: Student-friendly lesson notes (ELI10 style)
- **Video Resources**: Curated educational YouTube videos (3 regular + 2 shorts)
- **Podcast Audio**: 10-minute AI-generated dialogue between ALEX and SAM
- **Assessment Questions**: MCQ and Essay questions (without answers for students)
- **Answer Keys**: Separate answer slides at the end

## Base URL

```
https://your-api-domain.com/api/teacher
```

## Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer <your_jwt_token>
```

---

## Endpoints

### 1. Get Student Pack (by Subject & Class)

**GET** `/student-packs`

Get the student lesson pack for a specific subject and class.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | Yes | Subject name (e.g., "Physics") |
| `class_name` | string | Yes | Class name (e.g., "Class 11A") |
| `session_id` | integer | No | Specific session ID from timetable |
| `pack_date` | date | No | Date to fetch pack for (YYYY-MM-DD, defaults to today) |

#### Example Request

```javascript
const response = await fetch(
  '/api/teacher/student-packs?subject=Physics&class_name=Class%2011A',
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
const pack = await response.json();
```

#### Response (200 OK)

```json
{
  "id": "743ef846-a7d4-4a3e-8116-eccb2f3938de",
  "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
  "session_id": 1618,
  "slide_id": "8cc2a1ab-8870-47b0-8f44-fb18f788f441",
  "subject": "Physics",
  "class_name": "Class 11A",
  "status": "completed",
  "created_at": "2025-12-28T19:31:31.047Z",
  "updated_at": "2025-12-28T19:41:32.907Z",
  
  // Legacy fields (for backward compatibility)
  "simplified_notes": "<h2>Motion</h2><p>...</p>",
  "video_resources": [
    {
      "title": "Motion 1 (Physics JAMB and PUTME class 1)",
      "url": "https://www.youtube.com/watch?v=-Z3jIEKWMfk",
      "thumbnail": "https://i.ytimg.com/vi/-Z3jIEKWMfk/hq720.jpg",
      "duration": "30:30",
      "views": "166K views",
      "type": "video"
    }
  ],
  "podcast_audio_url": "https://storage.googleapis.com/bucket/student_packs/teacher_id/session_id/podcast.mp3",
  "podcast_audio_signed_url": "https://storage.googleapis.com/bucket/student_packs/...?X-Goog-Signature=...",
  
  // Structured content (new format)
  "pack_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "topic": "Motion",
  "generated_at": "2025-12-28T19:31:31.047Z",
  "slides": [
    {
      "id": "slide-1",
      "type": "title",
      "layout": "title_center",
      "content": {
        "title": "Student Learning Pack: Motion",
        "subtitle": "Physics - Class 11A"
      }
    },
    {
      "id": "slide-2",
      "type": "notes_section",
      "layout": "content_with_bullets",
      "content": {
        "title": "⚡️ What is Motion?",
        "body": "Motion is when something changes its position over time. Think of a car driving or a ball rolling!",
        "bullet_points": [
          "Motion = Change in position",
          "Speed = How fast something moves",
          "Velocity = Speed with direction"
        ],
        "content_parts": [
          {"type": "paragraph", "text": "Motion is when something changes..."},
          {"type": "bullet_list", "items": ["Motion = Change in position", "Speed = How fast..."]}
        ]
      }
    },
    {
      "id": "slide-3",
      "type": "notes_section",
      "layout": "bullet_list",
      "content": {
        "title": "📚 Types of Motion",
        "bullet_points": [
          "Linear motion - moving in a straight line",
          "Circular motion - moving in a circle",
          "Oscillatory motion - back and forth"
        ]
      }
    },
    {
      "id": "slide-4",
      "type": "notes_section",
      "layout": "content_with_subsections",
      "content": {
        "title": "💡 Did You Know?",
        "subsections": [
          {
            "heading": "Fun Fact #1",
            "content": [{"type": "paragraph", "text": "The fastest animal is the cheetah!"}]
          }
        ]
      }
    },

    {
      "id": "slide-5",
      "type": "video_resources",
      "layout": "video_grid",
      "content": {
        "title": "Recommended Videos",
        "description": "Watch these videos to learn more about this topic!",
        "videos": [...]
      }
    },
    {
      "id": "slide-6",
      "type": "podcast",
      "layout": "audio_player",
      "content": {
        "title": "Listen & Learn Podcast",
        "description": "A 10-minute conversation about this lesson with ALEX and SAM!",
        "audio_url": "https://storage.googleapis.com/...",
        "duration_ms": 668029
      }
    },
    {
      "id": "slide-7",
      "type": "assessment_mcq",

      "layout": "assessment",
      "content": {
        "title": "Test Your Knowledge - Multiple Choice",
        "instructions": "Choose the best answer for each question.",
        "questions": [
          {
            "question": "What is velocity?",
            "options": [
              {"label": "A", "text": "Speed with direction"},
              {"label": "B", "text": "Just speed"},
              {"label": "C", "text": "Acceleration"},
              {"label": "D", "text": "Force"}
            ]
          }
        ]
      }
    },
    {
      "id": "slide-6",
      "type": "assessment_essay",
      "layout": "assessment",
      "content": {
        "title": "Test Your Knowledge - Essay Questions",
        "instructions": "Answer the following questions in detail.",
        "questions": [
          {
            "question": "Explain Newton's first law of motion",
            "marks": 10
          }
        ]
      }
    },
    {
      "id": "slide-7",
      "type": "answer_key_mcq",
      "layout": "answer_key",
      "content": {
        "title": "Answer Key - Multiple Choice",
        "note": "Compare your answers with the correct answers below.",
        "answers": [
          {
            "question_number": 1,
            "question": "What is velocity?...",
            "correct_answer": "A",
            "explanation": "Velocity is speed with direction"
          }
        ]
      }
    },
    {
      "id": "slide-8",
      "type": "answer_key_essay",
      "layout": "answer_key",
      "content": {
        "title": "Answer Key - Essay Questions",
        "note": "Your answers should include these key points.",
        "answers": [
          {
            "question_number": 1,
            "question": "Explain Newton's first law...",
            "key_points": [
              "An object at rest stays at rest",
              "An object in motion stays in motion",
              "Unless acted upon by an external force"
            ],
            "marks": 10
          }
        ]
      }
    }
  ],
  "summary": {
    "total_slides": 8,
    "has_notes": true,
    "video_count": 5,
    "has_podcast": true,
    "podcast_duration_ms": 668029,
    "mcq_count": 15,
    "essay_count": 5
  }
}
```

---

### 2. Get Student Pack by ID

**GET** `/student-packs/{pack_id}`

Get a specific student lesson pack by its UUID.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pack_id` | UUID | Yes | Student pack UUID |

#### Example Request

```javascript
const packId = '743ef846-a7d4-4a3e-8116-eccb2f3938de';
const response = await fetch(`/api/teacher/student-packs/${packId}`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const pack = await response.json();
```

#### Response

Same structure as endpoint #1.

---

### 3. Get Student Pack by Session ID

**GET** `/student-packs/by-session/{session_id}`

Get student lesson pack by session ID from the timetable.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | integer | Yes | Session ID from timetable |

#### Example Request

```javascript
const sessionId = 1618;
const response = await fetch(`/api/teacher/student-packs/by-session/${sessionId}`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const pack = await response.json();
```

---

### 4. List Student Packs

**GET** `/student-packs/list`

List all student packs for the teacher with optional filtering.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | No | Filter by subject |
| `class_name` | string | No | Filter by class |
| `limit` | integer | No | Max results (1-100, default: 20) |

#### Example Request

```javascript
const response = await fetch(
  '/api/teacher/student-packs/list?subject=Physics&limit=10',
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
const packs = await response.json();
```

#### Response (200 OK)

```json
[
  {
    "id": "743ef846-a7d4-4a3e-8116-eccb2f3938de",
    "session_id": 1618,
    "subject": "Physics",
    "class_name": "Class 11A",
    "status": "completed",
    "has_audio": true,
    "video_count": 5,
    "created_at": "2025-12-28T19:31:31.047Z"
  }
]
```

---

### 5. Update Student Pack

**PUT** `/student-packs/{pack_id}`

Update an existing student lesson pack.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pack_id` | UUID | Yes | Student pack UUID |

#### Request Body

```json
{
  "simplified_notes": "<h2>Updated Notes</h2><p>...</p>",
  "video_resources": [
    {
      "title": "New Video",
      "url": "https://youtube.com/watch?v=...",
      "thumbnail": "https://...",
      "duration": "15:30",
      "views": "1M views",
      "type": "video"
    }
  ],
  "content_json": {
    "pack_id": "...",
    "subject": "Physics",
    "class_level": "Class 11A",
    "topic": "Motion",
    "slides": [...]
  }
}
```

#### Example Request

```javascript
const packId = '743ef846-a7d4-4a3e-8116-eccb2f3938de';
const response = await fetch(`/api/teacher/student-packs/${packId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    simplified_notes: '<h2>Updated Notes</h2>',
    video_resources: [...]
  })
});
const updatedPack = await response.json();
```

#### Response (200 OK)

Returns the updated pack with the same structure as GET endpoints.

---

### 6. Get Signed Audio URL

**GET** `/student-packs/{pack_id}/audio`

Get a signed URL for downloading/streaming the podcast audio file.

**Important**: The signed URL is temporary and expires after the specified duration (default 60 minutes).

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pack_id` | UUID | Yes | Student pack UUID |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `expiration_minutes` | integer | No | URL expiration (5-1440 minutes, default: 60) |

#### Example Request

```javascript
const packId = '743ef846-a7d4-4a3e-8116-eccb2f3938de';
const response = await fetch(
  `/api/teacher/student-packs/${packId}/audio?expiration_minutes=120`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
const audioData = await response.json();
```

#### Response (200 OK)

```json
{
  "original_url": "https://storage.googleapis.com/bucket/student_packs/teacher_id/session_id/podcast.mp3",
  "signed_url": "https://storage.googleapis.com/bucket/student_packs/teacher_id/session_id/podcast.mp3?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=...&X-Goog-Date=...&X-Goog-Expires=7200&X-Goog-SignedHeaders=host&X-Goog-Signature=...",
  "expires_in_minutes": 120,
  "content_type": "audio/mpeg"
}
```

#### Usage Example

```javascript
// Get signed URL
const audioData = await getSignedAudioUrl(packId);

// Use in audio player
const audioPlayer = document.getElementById('audio-player');
audioPlayer.src = audioData.signed_url;

// Or download
const link = document.createElement('a');
link.href = audioData.signed_url;
link.download = 'podcast.mp3';
link.click();
```

---

## Frontend Implementation Guide

### 1. Displaying the Student Pack

```javascript
// Fetch student pack
async function loadStudentPack(subject, className) {
  const response = await fetch(
    `/api/teacher/student-packs?subject=${encodeURIComponent(subject)}&class_name=${encodeURIComponent(className)}`,
    {
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    }
  );
  
  if (!response.ok) {
    if (response.status === 404) {
      return null; // No pack available
    }
    throw new Error('Failed to load student pack');
  }
  
  return await response.json();
}

// Render slides
function renderStudentPack(pack) {
  const container = document.getElementById('pack-container');
  
  pack.slides.forEach(slide => {
    const slideEl = document.createElement('div');
    slideEl.className = `slide slide-${slide.type}`;
    
    switch (slide.type) {
      case 'title':
        slideEl.innerHTML = `
          <h1>${slide.content.title}</h1>
          <h2>${slide.content.subtitle}</h2>
        `;
        break;
        
      case 'notes':
        slideEl.innerHTML = `
          <h2>${slide.content.title}</h2>
          <div class="notes-content">${slide.content.html_content}</div>
        `;
        break;
        
      case 'video_resources':
        slideEl.innerHTML = `
          <h2>${slide.content.title}</h2>
          <p>${slide.content.description}</p>
          <div class="video-grid">
            ${slide.content.videos.map(video => `
              <div class="video-card">
                <img src="${video.thumbnail}" alt="${video.title}">
                <h3>${video.title}</h3>
                <a href="${video.url}" target="_blank">Watch Video</a>
              </div>
            `).join('')}
          </div>
        `;
        break;
        
      case 'podcast':
        slideEl.innerHTML = `
          <h2>${slide.content.title}</h2>
          <p>${slide.content.description}</p>
          <audio controls id="podcast-player">
            <source src="${pack.podcast_audio_signed_url}" type="audio/mpeg">
          </audio>
          <p>Duration: ${Math.floor(slide.content.duration_ms / 60000)} minutes</p>
        `;
        break;
        
      case 'assessment_mcq':
        slideEl.innerHTML = `
          <h2>${slide.content.title}</h2>
          <p>${slide.content.instructions}</p>
          <div class="questions">
            ${slide.content.questions.map((q, i) => `
              <div class="question">
                <p><strong>Q${i+1}:</strong> ${q.question}</p>
                <div class="options">
                  ${q.options.map(opt => `
                    <label>
                      <input type="radio" name="q${i}" value="${opt.label}">
                      ${opt.label}. ${opt.text}
                    </label>
                  `).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        `;
        break;
        
      case 'answer_key_mcq':
        slideEl.innerHTML = `
          <h2>${slide.content.title}</h2>
          <p>${slide.content.note}</p>
          <div class="answers">
            ${slide.content.answers.map(ans => `
              <div class="answer">
                <p><strong>Q${ans.question_number}:</strong> ${ans.question}</p>
                <p class="correct-answer">Answer: ${ans.correct_answer}</p>
                <p class="explanation">${ans.explanation}</p>
              </div>
            `).join('')}
          </div>
        `;
        break;
    }
    
    container.appendChild(slideEl);
  });
}
```

### 2. Handling Audio with Signed URLs

```javascript
// The signed URL is already included in the pack response
// Use it directly in the audio player

function setupAudioPlayer(pack) {
  const audioPlayer = document.getElementById('podcast-player');
  
  // Use the signed URL from the pack
  audioPlayer.src = pack.podcast_audio_signed_url;
  
  // Optional: Refresh signed URL before expiration
  setTimeout(() => {
    refreshAudioUrl(pack.id);
  }, 50 * 60 * 1000); // Refresh after 50 minutes (before 60-minute expiration)
}

async function refreshAudioUrl(packId) {
  const response = await fetch(`/api/teacher/student-packs/${packId}/audio`, {
    headers: {
      'Authorization': `Bearer ${getToken()}`
    }
  });
  
  const audioData = await response.json();
  const audioPlayer = document.getElementById('podcast-player');
  const currentTime = audioPlayer.currentTime;
  const wasPlaying = !audioPlayer.paused;
  
  // Update source
  audioPlayer.src = audioData.signed_url;
  audioPlayer.currentTime = currentTime;
  
  if (wasPlaying) {
    audioPlayer.play();
  }
}
```

### 3. Editing Student Pack

```javascript
async function updateStudentPack(packId, updates) {
  const response = await fetch(`/api/teacher/student-packs/${packId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  
  if (!response.ok) {
    throw new Error('Failed to update student pack');
  }
  
  return await response.json();
}

// Example: Update notes
await updateStudentPack(packId, {
  simplified_notes: '<h2>Updated Notes</h2><p>New content...</p>'
});

// Example: Update entire structured content
await updateStudentPack(packId, {
  content_json: {
    pack_id: pack.pack_id,
    subject: pack.subject,
    class_level: pack.class_name,
    topic: pack.topic,
    slides: modifiedSlides,
    summary: pack.summary
  }
});
```

---

## Storage Structure

Audio files are stored in Google Cloud Storage with the following structure:

```
student_packs/
  └── {teacher_id}/
      └── {session_id}/
          └── podcast.mp3
```

**Example**:
```
student_packs/7bed2b69-8000-4b36-8e91-7fe0b70c9d82/1618/podcast.mp3
```

This structure ensures:
- **Multi-teacher support**: Each teacher's files are isolated
- **Session-based organization**: Easy to locate files by session
- **No conflicts**: Unique paths prevent file overwrites

---

## Error Handling

### Common Error Responses

#### 404 Not Found
```json
{
  "detail": "Student pack not found"
}
```

#### 400 Bad Request
```json
{
  "detail": "No update data provided"
}
```

#### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### Example Error Handling

```javascript
async function loadStudentPackSafely(subject, className) {
  try {
    const pack = await loadStudentPack(subject, className);
    
    if (!pack) {
      // No pack available yet
      showMessage('Student pack is being generated. Please check back in a few minutes.');
      return null;
    }
    
    return pack;
  } catch (error) {
    console.error('Error loading student pack:', error);
    showError('Failed to load student pack. Please try again.');
    return null;
  }
}
```

---

## Notes for Frontend Developers

1. **Signed URLs**: The `podcast_audio_signed_url` field in the pack response is already a signed URL valid for 60 minutes. Use it directly in audio players.

2. **URL Expiration**: If users might listen to audio for longer than 60 minutes, implement URL refresh logic (see example above).

3. **Slide Types**: The `slides` array contains different slide types. Render each type appropriately based on the `type` field.

4. **Answer Keys**: Answer key slides (`answer_key_mcq`, `answer_key_essay`) should be displayed separately or with a toggle to prevent students from seeing answers immediately.

5. **Status Field**: Check the `status` field before displaying:
   - `pending`: Pack creation queued
   - `processing`: Pack being generated
   - `completed`: Pack ready to display
   - `failed`: Generation failed

6. **Backward Compatibility**: The API includes both legacy fields (`simplified_notes`, `video_resources`, `podcast_audio_url`) and the new structured format (`slides`, `summary`). Use the structured format for new implementations.

---

## Complete React Example

```jsx
import React, { useState, useEffect } from 'react';

function StudentLessonPack({ subject, className }) {
  const [pack, setPack] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadPack();
  }, [subject, className]);

  async function loadPack() {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/teacher/student-packs?subject=${encodeURIComponent(subject)}&class_name=${encodeURIComponent(className)}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );

      if (response.status === 404) {
        setPack(null);
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to load pack');
      }

      const data = await response.json();
      setPack(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div>Loading student pack...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!pack) return <div>No student pack available yet.</div>;

  return (
    <div className="student-pack">
      <h1>{pack.topic}</h1>
      <p>Status: {pack.status}</p>
      
      <div className="pack-summary">
        <p>Total Slides: {pack.summary?.total_slides}</p>
        <p>Videos: {pack.summary?.video_count}</p>
        <p>MCQs: {pack.summary?.mcq_count}</p>
        <p>Essays: {pack.summary?.essay_count}</p>
      </div>

      <div className="slides">
        {pack.slides.map(slide => (
          <div key={slide.id} className={`slide slide-${slide.type}`}>
            {renderSlide(slide)}
          </div>
        ))}
      </div>
    </div>
  );
}

function renderSlide(slide) {
  switch (slide.type) {
    case 'title':
      return (
        <>
          <h1>{slide.content.title}</h1>
          <h2>{slide.content.subtitle}</h2>
        </>
      );
    
    case 'notes':
      return (
        <>
          <h2>{slide.content.title}</h2>
          <div dangerouslySetInnerHTML={{ __html: slide.content.html_content }} />
        </>
      );
    
    case 'podcast':
      return (
        <>
          <h2>{slide.content.title}</h2>
          <p>{slide.content.description}</p>
          <audio controls src={slide.content.audio_url}>
            Your browser does not support audio playback.
          </audio>
        </>
      );
    
    // Add other slide types...
    default:
      return <p>Unknown slide type: {slide.type}</p>;
  }
}

export default StudentLessonPack;
```

---

## Support

For questions or issues, contact the backend development team.
