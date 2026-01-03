# Student Support Pack - Final Format Fix

## Problem
The support pack is storing raw HTML (`<p>`, `<ul>`, etc.) while the student lesson pack stores structured JSON with plain text.

## Root Cause
Both systems:
1. AI generates HTML
2. **Student Lesson Pack**: Parses HTML → Extracts plain text → Stores in structured JSON
3. **Support Pack (OLD)**: Stores raw HTML directly ❌

## Solution
Make support pack parse HTML into structured JSON like student lesson pack.

## Changes Made

### 1. ✅ Updated Slide Building (Line 450-455)
**Before:**
```python
# === 4. Notes Slides ===
if notes_html:
    slides.append({
        "id": f"slide-{slide_num}",
        "type": "notes",
        "layout": "notes",
        "content": {
            "title": "Your Learning Notes",
            "html_content": notes_html  # ❌ Raw HTML
        }
    })
```

**After:**
```python
# === 4. Notes Slides (parsed into structured slides) ===
if notes_html:
    # Parse HTML into structured slides like student lesson pack
    notes_slides = _parse_notes_into_slides(notes_html, slide_num)
    slides.extend(notes_slides)
    slide_num += len(notes_slides)
```

### 2. ⏳ Need to Add `_parse_notes_into_slides` Function

**Location:** Insert at line 382 in `student_support_generator.py` (right before `_build_support_pack_slides`)

**Function:** See `student_back/parse_notes_function.py` for the complete function code.

This function:
- Parses HTML using BeautifulSoup
- Extracts plain text from `<p>`, `<ul>`, `<li>` tags
- Structures content into JSON with:
  - `content_parts`: Array of `{type, text/items}`
  - `paragraphs`: Plain text paragraphs
  - `bullet_points`: Plain text bullet items
  - `subsections`: Nested sections with heading + content
- Creates multiple `notes_section` slides (not one big HTML blob)
- Uses layouts: `text_only`, `bullet_list`, `content_with_bullets`, `content_with_subsections`

## Result Format

**Student Lesson Pack Format (CORRECT):**
```json
{
  "type": "notes_section",
  "layout": "content_with_subsections",
  "content": {
    "title": "Understanding Fractions",
    "content_parts": [
      {"type": "paragraph", "text": "A fraction represents part of a whole."},
      {"type": "bullet_list", "items": ["First: ...", "Second: ..."]}
    ],
    "subsections": [
      {
        "heading": "Main Idea",
        "content": [
          {"type": "paragraph", "text": "Fractions show parts of something."}
        ]
      }
    ]
  }
}
```

**Support Pack Format (NOW MATCHES):**
Same structure - no more raw HTML!

## To Complete

1. Copy the `_parse_notes_into_slides` function from `student_back/parse_notes_function.py`
2. Insert it at line 382 in `student_support_generator.py`
3. Restart the worker
4. Generate a new support pack

The notes will now be formatted exactly like student lesson pack! ✅
