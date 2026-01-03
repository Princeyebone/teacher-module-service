# AI-Powered Video Search Implementation

## Overview

Replaced the manual YouTube search with AI-powered video curation using Gemini AI. The AI analyzes learning objectives and returns highly relevant educational videos.

---

## Key Changes

### 1. **New AI-Powered Video Search**

**File**: `slide_builder/student_pack_generator.py`

#### What Changed:
- Replaced `_fetch_video_resources()` function with AI-powered implementation
- AI receives full context: indicator, education level, education system, country, subject, class
- AI returns 3-5 video suggestions with specific search queries
- Each video is validated to be under 20 minutes duration

#### How It Works:

```
1. Build context for AI:
   - Subject: Physics
   - Class: Class 11A
   - Learning Objective: [indicator text]
   - Education Level: Senior High School
   - Education System: Ghana Education Service
   - Country: Ghana

2. AI analyzes and returns video suggestions:
   [
     {
       "title": "Electric Charge Explained",
       "search_query": "electric charge physics class 11 Ghana",
       "estimated_duration": "12:30",
       "reason": "Clear explanation of charge fundamentals"
     },
     ...
   ]

3. Search YouTube for each suggestion
4. Filter by duration (< 20 minutes)
5. Return final video list
```

---

## New Functions

### `_fetch_video_resources()` - Updated
```python
async def _fetch_video_resources(
    subject: str, 
    class_name: str, 
    content: str,
    indicator: Optional[str] = None,
    country: Optional[str] = None,
    education_system: Optional[str] = None,
    education_level: Optional[str] = None  # NEW
) -> List[Dict]
```

**Features**:
- ✅ AI-powered video curation
- ✅ Retry logic (5 retries with exponential backoff)
- ✅ Duration filtering (max 20 minutes)
- ✅ Context-aware search using learning objectives

### `_call_ai_for_video_suggestions()` - New
```python
async def _call_ai_for_video_suggestions(prompt: str) -> List[Dict]
```

**Features**:
- ✅ Calls Gemini 2.0 Flash Exp
- ✅ Returns structured JSON
- ✅ Handles markdown code block wrapping
- ✅ Error handling with re-raise for retry

### `_is_duration_acceptable()` - New
```python
def _is_duration_acceptable(duration_str: str) -> bool
```

**Features**:
- ✅ Parses "MM:SS" and "H:MM:SS" formats
- ✅ Ensures videos are under 20 minutes
- ✅ Rejects videos over 1 hour

### `_get_education_level()` - New
```python
async def _get_education_level(teacher_id: str, subject: str, class_name: str) -> Optional[str]
```

**Features**:
- ✅ Fetches `edu_lvl` from `weeklytimetable`
- ✅ Matches by teacher_id, subject, and class_name
- ✅ Used for AI context

---

## Fixed Issues

### Issue #1: Wrong Indicator for Video Search
**Problem**: Videos were showing content from wrong topics
**Root Cause**: Used `session_ids` column instead of `session_details`
**Fix**: Updated `_get_session_indicator()` to use JSONB containment:

```python
# Before (WRONG):
AND session_ids::text LIKE :sid_pattern

# After (CORRECT):
AND session_details IS NOT NULL
AND session_details @> :session_json
```

Now uses the **exact same indicator** as teacher slide generation.

---

## AI Prompt Template

```
You are an educational content curator. Find 3-5 relevant YouTube educational videos for students.

Subject: Physics
Class: Class 11A
Learning Objective: Describe electric charge, its conservation, and quantization
Education Level: Senior High School
Education System: Ghana Education Service
Country: Ghana

Requirements:
1. Videos must be educational and appropriate for students
2. Maximum duration: 20 minutes (prefer 5-15 minutes)
3. No comedy skits, pranks, or entertainment content
4. Prefer videos from educational channels
5. Include a mix of explanation styles (lectures, animations, demonstrations)
6. If available, prioritize videos from the specified country/education system

Return ONLY a valid JSON array with this exact structure:
[
  {
    "title": "Video title",
    "search_query": "exact YouTube search query to find this video",
    "estimated_duration": "approximate duration like 10:30 or 5:00",
    "reason": "why this video is relevant"
  }
]

Return 3-5 videos. Be specific with search queries to ensure we find the exact videos.
```

---

## Retry Logic

Uses the same retry mechanism as embeddings:

```python
videos_data = await _retry_async(
    lambda: _call_ai_for_video_suggestions(prompt),
    max_retries=5,
    base_delay=2.0,
    max_delay=60.0,
    operation_name="AI_video_search"
)
```

**Retry Strategy**:
- Max retries: 5
- Base delay: 2 seconds
- Max delay: 60 seconds
- Exponential backoff with jitter

---

## Benefits

### 1. **Relevance**
- AI understands learning objectives
- Matches videos to exact curriculum requirements
- Considers education system and country

### 2. **Quality Control**
- Duration filtering (no hour-long videos)
- Educational content only
- Mix of teaching styles

### 3. **Reliability**
- Retry logic handles API failures
- Graceful fallback to empty list
- Detailed logging for debugging

### 4. **Context-Aware**
- Uses same indicator as teacher slides
- Considers education level
- Localizes to country/system

---

## Testing

### Test the Video Search:

```python
# Run the complete flow test
python slide_builder/test_complete_flow.py
```

### Expected Output:

```
[INFO] Using AI to search for educational videos...
[CONTEXT] Country: Ghana, Edu System: Ghana Education Service
[CONTEXT] Education Level: Senior High School
[CONTEXT] Indicator: Describe electric charge, its conservation...
[AI-VIDEO] Calling Gemini for video suggestions...
[AI-VIDEO] Got 5 video suggestions from AI
[VIDEO] AI found 5 relevant videos
```

### Verify Videos:

Check `student_lesson_packs` table:
```sql
SELECT 
    id,
    video_resources,
    content_json->'slides'->2->'content'->'videos' as video_slide
FROM student_lesson_packs
ORDER BY created_at DESC
LIMIT 1;
```

---

## Error Handling

### Scenario 1: AI Returns Invalid JSON
```
[AI-VIDEO] Failed to parse AI response as JSON: ...
[AI-VIDEO] Response was: [first 500 chars]
```
→ Retry triggered automatically

### Scenario 2: YouTube Search Fails
```
[VIDEO] Search failed for 'electric charge physics': ...
```
→ Continues with next video suggestion

### Scenario 3: No Videos Found
```
[VIDEO] AI returned no video suggestions
```
→ Returns empty list, pack generation continues

---

## Configuration

### Required Settings:
- `GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI`: Vertex AI credentials
- YouTube search library: `youtubesearchpython`

### Optional Context:
- `weeklytimetable.edu_lvl`: Education level
- `weeklytimetable.edu_sys`: Education system
- `teacherprofile.country`: Teacher's country

---

## Next Steps

1. ✅ Test with real data
2. ✅ Monitor AI response quality
3. ✅ Adjust prompt if needed
4. ✅ Track video relevance metrics

---

**Status**: ✅ Ready for testing
**Impact**: High - Videos now match exact learning objectives
**Risk**: Low - Has fallback and retry logic
