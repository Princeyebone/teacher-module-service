# Student Pack Notes Frontend Implementation Guide

## Overview

The **Student Lesson Pack** now includes structured notes slides that can be rendered in the frontend similar to how **Teacher Slides** are displayed. This document explains the new slide structure and how to implement the frontend rendering.

---

## API Response Structure

### Example Response with Structured Notes

```json
{
  "id": "34c770e8-5da9-49a9-b335-f959d34799dd",
  "status": "completed",
  "slides": [
    {
      "id": "slide-1",
      "type": "title",
      "layout": "title_center",
      "content": {
        "title": "Student Learning Pack: Electric Charge",
        "subtitle": "Physics - Class 11A"
      }
    },
    {
      "id": "slide-2",
      "type": "notes_section",
      "layout": "content_with_bullets",
      "content": {
        "title": "⚡️ Electric Charge: Tiny Sparks! ⚡️",
        "body": "Imagine everything around you is made of LEGO bricks. Electric charge is like the special glue that holds atoms together!",
        "bullet_points": [
          "Protons have positive (+) charge",
          "Electrons have negative (-) charge",
          "Neutrons have no charge (neutral)"
        ],
        "content_parts": [
          {
            "type": "paragraph",
            "text": "Imagine everything around you is made of LEGO bricks..."
          },
          {
            "type": "bullet_list",
            "items": [
              "Protons have positive (+) charge",
              "Electrons have negative (-) charge",
              "Neutrons have no charge (neutral)"
            ]
          }
        ],
        "subsections": []
      }
    },
    {
      "id": "slide-3",
      "type": "notes_section",
      "layout": "content_with_subsections",
      "content": {
        "title": "📚 Types of Charge",
        "content_parts": [...],
        "subsections": [
          {
            "heading": "🔴 Positive Charge",
            "content": [
              {
                "type": "paragraph",
                "text": "Found in protons in the nucleus"
              }
            ]
          },
          {
            "heading": "🔵 Negative Charge",
            "content": [
              {
                "type": "paragraph", 
                "text": "Found in electrons orbiting the atom"
              }
            ]
          }
        ]
      }
    },
    {
      "id": "slide-4",
      "type": "notes_section",
      "layout": "bullet_list",
      "content": {
        "title": "💡 Did You Know?",
        "bullet_points": [
          "A single lightning bolt can contain up to 1 billion volts!",
          "The human body generates a small amount of electricity"
        ]
      }
    },
    {
      "id": "slide-5",
      "type": "video_resources",
      "layout": "video_grid",
      "content": {...}
    },
    {
      "id": "slide-6",
      "type": "podcast",
      "layout": "audio_player",
      "content": {...}
    },
    {
      "id": "slide-7",
      "type": "assessment_mcq",
      "layout": "assessment",
      "content": {...}
    }
  ],
  "summary": {
    "total_slides": 10,
    "has_notes": true,
    "video_count": 5,
    "mcq_count": 15
  }
}
```

---

## Slide Types Reference

### 1. `notes_section` - Main Notes Slides

The new `notes_section` type is used for structured lesson notes. Each H2 section in the original HTML becomes a separate slide.

#### Layouts:

| Layout | When Used | Content Fields |
|--------|-----------|----------------|
| `content_with_bullets` | Has paragraphs AND bullet points | `title`, `body`, `bullet_points` |
| `bullet_list` | Only has bullet points | `title`, `bullet_points` |
| `content_with_subsections` | Has H3 subsections | `title`, `subsections` |
| `text_only` | Only paragraphs, no lists | `title`, `body`, `content_parts` |

#### Content Structure:

```typescript
interface NoteSectionContent {
  // Main heading (from H2)
  title: string;
  
  // First paragraph(s) - for quick display
  body?: string;
  
  // All bullet points combined
  bullet_points?: string[];
  
  // Detailed content parts for precise rendering
  content_parts: ContentPart[];
  
  // H3 subsections (if any)
  subsections?: Subsection[];
}

interface ContentPart {
  type: "paragraph" | "bullet_list" | "numbered_list" | "emphasis";
  text?: string;      // For paragraph/emphasis
  items?: string[];   // For bullet_list/numbered_list
}

interface Subsection {
  heading: string;
  content: ContentPart[];
}
```

---

## React Implementation

### Complete Component Example

```tsx
import React from 'react';
import './StudentPackSlides.css';

interface StudentPackProps {
  pack: StudentPack;
}

export function StudentPackSlides({ pack }: StudentPackProps) {
  const [currentSlide, setCurrentSlide] = React.useState(0);

  return (
    <div className="student-pack-container">
      <div className="slide-navigation">
        <button 
          onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
          disabled={currentSlide === 0}
        >
          Previous
        </button>
        <span>{currentSlide + 1} / {pack.slides.length}</span>
        <button 
          onClick={() => setCurrentSlide(Math.min(pack.slides.length - 1, currentSlide + 1))}
          disabled={currentSlide === pack.slides.length - 1}
        >
          Next
        </button>
      </div>
      
      <div className="slide-container">
        {renderSlide(pack.slides[currentSlide])}
      </div>
    </div>
  );
}

function renderSlide(slide: Slide) {
  switch (slide.type) {
    case 'title':
      return <TitleSlide slide={slide} />;
    case 'notes_section':
      return <NotesSectionSlide slide={slide} />;
    case 'video_resources':
      return <VideoResourcesSlide slide={slide} />;
    case 'podcast':
      return <PodcastSlide slide={slide} />;
    case 'assessment_mcq':
      return <MCQAssessmentSlide slide={slide} />;
    case 'assessment_essay':
      return <EssayAssessmentSlide slide={slide} />;
    case 'answer_key_mcq':
      return <MCQAnswerKeySlide slide={slide} />;
    case 'answer_key_essay':
      return <EssayAnswerKeySlide slide={slide} />;
    default:
      return <div>Unknown slide type: {slide.type}</div>;
  }
}
```

### Notes Section Slide Component

```tsx
interface NotesSectionSlideProps {
  slide: {
    id: string;
    type: 'notes_section';
    layout: string;
    content: {
      title: string;
      body?: string;
      bullet_points?: string[];
      content_parts?: ContentPart[];
      subsections?: Subsection[];
      html_content?: string; // Fallback
    };
  };
}

function NotesSectionSlide({ slide }: NotesSectionSlideProps) {
  const { content, layout } = slide;

  return (
    <div className={`slide notes-section ${layout}`}>
      {/* Main Title */}
      <h2 className="slide-title">{content.title}</h2>
      
      {/* Render based on layout */}
      {layout === 'content_with_bullets' && (
        <>
          {content.body && <p className="slide-body">{content.body}</p>}
          {content.bullet_points && (
            <ul className="bullet-list">
              {content.bullet_points.map((point, i) => (
                <li key={i}>{point}</li>
              ))}
            </ul>
          )}
        </>
      )}
      
      {layout === 'bullet_list' && content.bullet_points && (
        <ul className="bullet-list">
          {content.bullet_points.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      )}
      
      {layout === 'content_with_subsections' && content.subsections && (
        <div className="subsections">
          {content.subsections.map((sub, i) => (
            <div key={i} className="subsection">
              <h3>{sub.heading}</h3>
              {sub.content.map((part, j) => (
                <ContentPartRenderer key={j} part={part} />
              ))}
            </div>
          ))}
        </div>
      )}
      
      {layout === 'text_only' && (
        <>
          {content.body && <p className="slide-body">{content.body}</p>}
          {content.content_parts?.map((part, i) => (
            <ContentPartRenderer key={i} part={part} />
          ))}
        </>
      )}
      
      {/* Fallback for raw HTML */}
      {content.html_content && !content.content_parts && (
        <div 
          className="html-content"
          dangerouslySetInnerHTML={{ __html: content.html_content }}
        />
      )}
    </div>
  );
}

function ContentPartRenderer({ part }: { part: ContentPart }) {
  switch (part.type) {
    case 'paragraph':
      return <p className="content-paragraph">{part.text}</p>;
    case 'bullet_list':
      return (
        <ul className="bullet-list">
          {part.items?.map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      );
    case 'numbered_list':
      return (
        <ol className="numbered-list">
          {part.items?.map((item, i) => <li key={i}>{item}</li>)}
        </ol>
      );
    case 'emphasis':
      return <p className="emphasis">{part.text}</p>;
    default:
      return null;
  }
}
```

### CSS Styling

```css
/* StudentPackSlides.css */

.student-pack-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

.slide-navigation {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.slide-container {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 40px;
  min-height: 500px;
  color: white;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

/* Notes Section Styles */
.slide.notes-section {
  animation: fadeIn 0.3s ease;
}

.slide-title {
  font-size: 2rem;
  margin-bottom: 24px;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

.slide-body {
  font-size: 1.2rem;
  line-height: 1.8;
  margin-bottom: 20px;
}

.bullet-list {
  list-style: none;
  padding: 0;
}

.bullet-list li {
  position: relative;
  padding-left: 30px;
  margin-bottom: 12px;
  font-size: 1.1rem;
  line-height: 1.6;
}

.bullet-list li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: #4ade80;
  font-weight: bold;
}

.subsection {
  margin-top: 24px;
  padding-left: 20px;
  border-left: 3px solid rgba(255, 255, 255, 0.3);
}

.subsection h3 {
  font-size: 1.4rem;
  margin-bottom: 12px;
}

.content-paragraph {
  margin-bottom: 16px;
  line-height: 1.7;
}

.numbered-list {
  padding-left: 24px;
}

.numbered-list li {
  margin-bottom: 10px;
  line-height: 1.6;
}

.emphasis {
  font-weight: bold;
  font-style: italic;
  background: rgba(255, 255, 255, 0.1);
  padding: 12px;
  border-radius: 8px;
}

/* Layout-specific styles */
.slide.content_with_bullets .bullet-list {
  margin-top: 20px;
  background: rgba(255, 255, 255, 0.1);
  padding: 20px;
  border-radius: 12px;
}

.slide.bullet_list .bullet-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.slide.content_with_subsections .subsections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

/* Animation */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Responsive */
@media (max-width: 768px) {
  .slide-container {
    padding: 24px;
    min-height: auto;
  }
  
  .slide-title {
    font-size: 1.5rem;
  }
  
  .slide-body {
    font-size: 1rem;
  }
}
```

---

## TypeScript Interfaces

```typescript
// types/StudentPack.ts

export interface StudentPack {
  id: string;
  teacher_id: string;
  session_id: number;
  slide_id: string;
  subject: string;
  class_name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  
  // Structured slides
  slides: Slide[];
  
  // Summary
  summary: {
    total_slides: number;
    has_notes: boolean;
    video_count: number;
    has_podcast: boolean;
    podcast_duration_ms: number;
    mcq_count: number;
    essay_count: number;
  };
  
  // Audio URL (signed)
  podcast_audio_signed_url?: string;
}

export type Slide = 
  | TitleSlide 
  | NotesSectionSlide 
  | VideoResourcesSlide 
  | PodcastSlide 
  | AssessmentMCQSlide 
  | AssessmentEssaySlide
  | AnswerKeyMCQSlide
  | AnswerKeyEssaySlide;

export interface TitleSlide {
  id: string;
  type: 'title';
  layout: 'title_center';
  content: {
    title: string;
    subtitle: string;
  };
}

export interface NotesSectionSlide {
  id: string;
  type: 'notes_section';
  layout: 'content_with_bullets' | 'bullet_list' | 'content_with_subsections' | 'text_only';
  content: {
    title: string;
    body?: string;
    bullet_points?: string[];
    content_parts?: ContentPart[];
    subsections?: Subsection[];
    html_content?: string; // Fallback
  };
}

export interface ContentPart {
  type: 'paragraph' | 'bullet_list' | 'numbered_list' | 'emphasis';
  text?: string;
  items?: string[];
}

export interface Subsection {
  heading: string;
  content: ContentPart[];
}

export interface VideoResourcesSlide {
  id: string;
  type: 'video_resources';
  layout: 'video_grid';
  content: {
    title: string;
    description: string;
    videos: Video[];
  };
}

export interface Video {
  id?: string;
  title: string;
  url: string;
  channel: string;
  duration: string;
  thumbnail?: string;
  views?: string;
  description?: string;
  type: 'video';
}

export interface PodcastSlide {
  id: string;
  type: 'podcast';
  layout: 'audio_player';
  content: {
    title: string;
    description: string;
    audio_url: string;
    duration_ms: number;
  };
}

export interface AssessmentMCQSlide {
  id: string;
  type: 'assessment_mcq';
  layout: 'assessment';
  content: {
    title: string;
    instructions: string;
    questions: MCQQuestion[];
  };
}

export interface MCQQuestion {
  question: string;
  options: { label: string; text: string }[];
}

export interface AssessmentEssaySlide {
  id: string;
  type: 'assessment_essay';
  layout: 'assessment';
  content: {
    title: string;
    instructions: string;
    questions: { question: string; marks: number }[];
  };
}

export interface AnswerKeyMCQSlide {
  id: string;
  type: 'answer_key_mcq';
  layout: 'answer_key';
  content: {
    title: string;
    note: string;
    answers: {
      question_number: number;
      question: string;
      correct_answer: string;
      explanation: string;
    }[];
  };
}

export interface AnswerKeyEssaySlide {
  id: string;
  type: 'answer_key_essay';
  layout: 'answer_key';
  content: {
    title: string;
    note: string;
    answers: {
      question_number: number;
      question: string;
      key_points: string[];
      marks: number;
    }[];
  };
}
```

---

## Migration Notes

### Before (Old Format)

The old format had a single `notes` slide with raw HTML:

```json
{
  "type": "notes",
  "layout": "text_only",
  "content": {
    "title": "Simplified Lesson Notes",
    "html_content": "<h2>Title</h2><p>Content...</p><ul><li>Point 1</li></ul>"
  }
}
```

### After (New Format)

The new format has multiple `notes_section` slides with structured content:

```json
[
  {
    "type": "notes_section",
    "layout": "content_with_bullets",
    "content": {
      "title": "Title",
      "body": "Content...",
      "bullet_points": ["Point 1"],
      "content_parts": [
        { "type": "paragraph", "text": "Content..." },
        { "type": "bullet_list", "items": ["Point 1"] }
      ]
    }
  }
]
```

### Backward Compatibility

If you encounter the old `notes` type with `html_content`, you can render it using `dangerouslySetInnerHTML`:

```tsx
{slide.content.html_content && (
  <div dangerouslySetInnerHTML={{ __html: slide.content.html_content }} />
)}
```

---

## Summary

| Feature | Before | After |
|---------|--------|-------|
| Notes Structure | Single slide with HTML | Multiple structured slides |
| Rendering | `dangerouslySetInnerHTML` | Component-based rendering |
| Type | `notes` | `notes_section` |
| Layouts | `text_only` | `content_with_bullets`, `bullet_list`, `content_with_subsections`, `text_only` |
| Content Access | Parse HTML | Direct access to `title`, `body`, `bullet_points`, `subsections` |

This new structure enables:
- ✅ Consistent styling with Teacher Slides
- ✅ Component-based rendering (no HTML injection)
- ✅ Better accessibility
- ✅ Slide-by-slide navigation
- ✅ Mobile-responsive layouts
