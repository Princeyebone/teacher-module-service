# Slide API Documentation

## Overview
The Slide API provides endpoints for retrieving and updating AI-generated lesson slides.

**Base URL**: `/api/teacher`

**Authentication**: Bearer token (JWT) required in `Authorization` header.

---

## Slide Limits

| Education Level | Min Slides | Max Slides | Content Slides |
|-----------------|------------|------------|----------------|
| Primary (1-6) | 8 | 12 | 10 |
| JHS/Middle (7-9) | 12 | 18 | 16 |
| SHS/Secondary (10-12) | 15 | 25 | 23 |
| Tertiary/University | 20 | 30 | 28 |

**Last 2 slides are always reserved for assessment:**
- Second-to-last: 10 Multiple Choice Questions (MCQ)
- Last: 5 Essay Questions

---

## Endpoints

### 1. GET /slides
Get the most recent slide deck for a subject+class on a given date.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | string | Yes | Subject name (e.g., "Physics") |
| `class_name` | string | Yes | Class name (e.g., "Class 11A") |
| `slide_date` | date (YYYY-MM-DD) | No | Date to fetch (defaults to today) |

**Response:** `SlideDeckResponse` or `null`

---

### 2. GET /slides/history
Get historical slides (before today) for a subject+class.

**Full URL**: `GET /api/teacher/slides/history`

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `subject` | string | Yes | - | Subject name (e.g., "Physics") |
| `class_name` | string | Yes | - | Class name (e.g., "Class 11A") |
| `limit` | integer | No | 20 | Max results to return (1-100) |

**Example Request:**
```
GET /api/teacher/slides/history?subject=Physics&class_name=Class%2011A&limit=10
Authorization: Bearer <jwt_token>
```

**Response Schema: SlideHistoryResponse**
```typescript
interface SlideHistoryResponse {
  subject: string;          // The subject filtered by
  class_name: string;       // The class filtered by
  total_count: number;      // Number of results returned
  slide_decks: SlideDeckSummary[];  // Array of slide deck summaries
}

interface SlideDeckSummary {
  id: string;               // UUID - use this to fetch full deck
  subject: string;
  class_name: string;
  topic: string | null;     // Lesson topic
  slide_count: number;      // Number of slides in deck
  created_at: string;       // ISO datetime
}
```

**Example Response:**
```json
{
  "subject": "Physics",
  "class_name": "Class 11A",
  "total_count": 3,
  "slide_decks": [
    {
      "id": "68b75699-9a9c-4303-9979-19d32f22d61d",
      "subject": "Physics",
      "class_name": "Class 11A",
      "topic": "Apply Malus's Law",
      "slide_count": 15,
      "created_at": "2025-12-22T01:44:58.436923"
    },
    {
      "id": "a61e68c2-b973-455e-9a4b-4d3c2ec7c32e",
      "subject": "Physics",
      "class_name": "Class 11A",
      "topic": "Apply Malus's Law",
      "slide_count": 16,
      "created_at": "2025-12-21T15:20:31.875786"
    },
    {
      "id": "7cc7be2f-8d11-407c-8922-d6190e9850fd",
      "subject": "Physics",
      "class_name": "Class 11A",
      "topic": "Apply Malus's Law",
      "slide_count": 16,
      "created_at": "2025-12-21T13:26:03.490388"
    }
  ]
}
```

**Frontend Usage:**
```typescript
// Fetch history
const response = await fetch(
  `/api/teacher/slides/history?subject=${encodeURIComponent(subject)}&class_name=${encodeURIComponent(className)}`,
  { headers: { Authorization: `Bearer ${token}` } }
);
const history: SlideHistoryResponse = await response.json();

// Display in a list
history.slide_decks.forEach(deck => {
  console.log(`${deck.topic} - ${deck.slide_count} slides - ${new Date(deck.created_at).toLocaleDateString()}`);
});

// Load full deck when user clicks
const fullDeck = await fetch(`/api/teacher/slides/${deck.id}`, {
  headers: { Authorization: `Bearer ${token}` }
});
```

**Notes:**
- Returns slides from **before today only** (use GET /slides for today's slides)
- Results ordered by **most recent first**
- To get the full slide deck with content, call `GET /slides/{id}` with the deck's ID

---

### 3. GET /slides/{slide_id}
Get a specific slide deck by UUID.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `slide_id` | UUID | Slide deck ID |

**Response:** `SlideDeckResponse`

---

### 4. PUT /slides/{slide_id}
Update an existing slide deck.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `slide_id` | UUID | Slide deck ID |

**Request Body:**
```json
{
  "topic": "Updated Topic (optional)",
  "content_json": { ... full slide deck ... }
}
```

**Response:** Updated `SlideDeckResponse`

---

## Slide Types
| Type | Description |
|------|-------------|
| `title` | Title slide (first slide) |
| `content` | Regular content slide |
| `image_content` | Content with image |
| `assessment_mcq` | Multiple choice questions (10 questions) |
| `assessment_essay` | Essay questions (5 questions) |

## Slide Layouts
| Layout | Description |
|--------|-------------|
| `title_center` | Centered title text |
| `text_only` | Text content only |
| `image_left_text_right` | Image on left, text on right |
| `image_top_text_bottom` | Image on top, text below |
| `assessment` | Questions layout |

---

## Response Schema: SlideDeckResponse

```json
{
  "id": "uuid",
  "teacher_id": "uuid",
  "subject": "Physics",
  "class_name": "Class 11A",
  "topic": "Electric Fields",
  "indicator_ids": [1586],
  "generation_status": "completed",
  "created_at": "2025-12-21T10:00:00",
  "updated_at": "2025-12-21T10:00:00",
  "lesson_id": "lesson-uuid",
  "class_level": "Class 11A",
  "slides": [
    // Title slide
    {
      "id": "slide-001",
      "type": "title",
      "layout": "title_center",
      "content": {
        "title": "Understanding Electric Fields",
        "heading": null,
        "bullet_points": null,
        "questions": null,
        "mcq_questions": null,
        "essay_questions": null,
        "image": null
      }
    },
    // Content slides...
    {
      "id": "slide-002",
      "type": "content",
      "layout": "text_only",
      "content": {
        "heading": "What is an Electric Field?",
        "bullet_points": [
          "Electric field is a region around a charged object",
          "It exerts force on other charges"
        ]
      }
    },
    // MCQ Assessment slide (second-to-last)
    {
      "id": "slide-mcq",
      "type": "assessment_mcq",
      "layout": "assessment",
      "content": {
        "heading": "Multiple Choice Questions",
        "mcq_questions": [
          {
            "question": "What is the SI unit of electric field?",
            "options": [
              {"label": "A", "text": "Volt"},
              {"label": "B", "text": "Newton per Coulomb"},
              {"label": "C", "text": "Joule"},
              {"label": "D", "text": "Watt"}
            ],
            "correct_answer": "B",
            "explanation": "Electric field is force per unit charge, so N/C"
          }
          // ... 9 more questions
        ]
      }
    },
    // Essay Assessment slide (last)
    {
      "id": "slide-essay",
      "type": "assessment_essay",
      "layout": "assessment",
      "content": {
        "heading": "Essay Questions",
        "essay_questions": [
          {
            "question": "Explain the concept of electric field lines and their properties.",
            "model_answer": "Electric field lines are imaginary lines that represent the direction and strength of an electric field. Properties include: 1) They originate from positive charges and terminate at negative charges, 2) They never cross each other, 3) The density of lines indicates field strength...",
            "marks": 10
          }
          // ... 4 more questions
        ]
      }
    }
  ],
  "images": [
    {
      "id": "image-uuid",
      "slide_item_id": "slide-003",
      "prompt": "flat educational diagram...",
      "style": "flat educational diagram",
      "alt_text": "Electric field lines",
      "image_url": "https://storage.googleapis.com/...",
      "status": "generated"
    }
  ]
}
```

---

## Frontend Integration Notes

1. **Fetching Today's Slides**: Call `GET /slides?subject=Physics&class_name=Class 11A`
2. **Browsing History**: Call `GET /slides/history?subject=Physics&class_name=Class 11A`
3. **Editing Slides**: Call `PUT /slides/{id}` with modified `content_json`
4. **Image Status**: Check `images` array for image generation status
5. **Rendering Assessment Slides**:
   - For MCQ slides: Display each question with 4 options as radio buttons
   - For Essay slides: Display question and provide text area for answers
   - Teacher view can show correct answers/model answers
   - Student view should hide answers until submission

---

## Image Handling for Frontend

### Image Location
Images are stored in two places in the API response:

1. **In `slides` array** - The image prompt/metadata within the slide content:
```json
{
  "id": "slide-3",
  "type": "image_content",
  "content": {
    "image": {
      "prompt": "...",      // AI generation prompt (for debugging)
      "style": "...",       // Style used
      "alt": "..."          // Alt text for accessibility
    }
  }
}
```

2. **In `images` array** - The actual generated image data:
```json
{
  "id": "uuid",
  "slide_item_id": "slide-3",     // ← Links to slide.id
  "prompt": "...",
  "style": "...",
  "alt_text": "...",
  "image_url": "https://storage.googleapis.com/...",  // ← ACTUAL IMAGE URL
  "status": "generated"           // pending | generating | generated | failed
}
```

### How to Display Images

```typescript
// 1. Find the image URL by matching slide_item_id to slide.id
function getImageUrl(slideId: string, images: ImageStatus[]): string | null {
  const image = images.find(img => img.slide_item_id === slideId);
  if (image && image.status === 'generated' && image.image_url) {
    return image.image_url;
  }
  return null; // Show placeholder or loading state
}

// 2. Render the slide
function renderSlide(slide: Slide, images: ImageStatus[]) {
  if (slide.type === 'image_content') {
    const imageUrl = getImageUrl(slide.id, images);
    const altText = slide.content.image?.alt || 'Educational diagram';
    
    if (imageUrl) {
      return <img src={imageUrl} alt={altText} />;
    } else {
      return <div className="image-placeholder">Image loading...</div>;
    }
  }
}
```

### Image Status Values
| Status | Meaning | Frontend Action |
|--------|---------|-----------------|
| `pending` | Queued for generation | Show placeholder |
| `generating` | Currently being generated | Show loading spinner |
| `generated` | Ready to display | Use `image_url` |
| `failed` | Generation failed | Show fallback/error |

### CORS Note
If images fail to load due to CORS, the GCS bucket may need public access enabled. The images are stored at:
```
https://storage.googleapis.com/teacher_module_acatable_bucket/slide_images/{slide_id}/{slide_item_id}.png
```
