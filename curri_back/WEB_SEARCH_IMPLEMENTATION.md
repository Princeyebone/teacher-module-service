# Curriculum Processing - Web Search Enhancement Implementation Plan

## ✅ Completed Changes

### 1. Upload Endpoint (`curri_file_handler.py`)
- ✅ Passing `education_system` and `education_level` to enqueue function

### 2. Enqueue Function (`curri_back/enqueue_curri.py`)
- ✅ Added `education_system` and `education_level` parameters
- ✅ Passing these to the background task

### 3. Background Task (`curri_back/curri_processor.py`)
 ⚠️ **PARTIALLY DONE - FILE CORRUPTED - NEEDS FIX**
- ✅ Updated function signature to accept new parameters
- ✅ Added logic to fetch `semester_name` and `term` from AcademicCalendar
- ✅ Enhanced retrieval query to include semester_name and term
- ✅ Updated prompt builder signature
- ⚠️ **INCOMPLETE**: Prompt text update (file syntax error)

## ❌ Remaining Tasks

### 1. Fix `curri_processor.py` Syntax Error
**Issue**: Triple-quoted string literal not properly closed around line 221
**Solution**: Need to properly close the prompt string and complete the web search instructions

### 2. Complete Prompt Builder
The prompt needs to include:
```
IMPORTANT WEB SEARCH INSTRUCTION:
If the retrieved content is incomplete, perform web search using:
- Education System: {education_system}
- Education Level: {education_level}
- Subject: {subject}
- Class: {class_name}
- Semester: {semester_name}
- Term: {term}
```

### 3. Update AI Call to Include Parameters
In `curri_processor.py`, when calling `build_curriculum_prompt`, pass:
- `education_system=education_system`
- `education_level=education_level`
- `semester_name=semester_name`
- `term=term`

Location: Around line 650 (after retrieval)

### 4. Enable Web Search in AI Service Call
**File**: `curri_processor.py` or `external_service.py`
**Change**: When calling `send_semester_plan_to_ai`, ensure web search is enabled

Check if `send_semester_plan_to_ai` has a parameter like:
- `enable_grounding=True`
- `use_web_search=True`
- or similar

### 5. Add Logging for Web Search
Add detail logging for:
- Whether web search is enabled
- Web search queries being made
- Web search results received

## File Recovery

The `curri_processor.py` file needs to be fixed. The prompt string starting around line 254 needs proper closure.

### The Prompt Should Look Like:
```python
prompt = f\"\"\"You are an Educational Curriculum Mapping AI with web search capabilities.

IMPORTANT WEB SEARCH INSTRUCTION:
The curriculum content provided below may NOT be sufficient...
{instructions continue}...

EXPECTED OUTPUT FORMAT:
{example_json}

Return ONLY the JSON, nothing else.
\"\"\"  # <-- This closing was missing

return prompt
```

## Testing Checklist

After fixes:
1. ✅ Upload endpoint passes edu_system and edu_level
2. ✅ Background task receives all parameters
3. ✅ Semester metadata is fetched from AcademicCalendar
4. ✅ Retrieval query includes semester context
5. ❌ AI prompt includes all metadata
6. ❌ AI prompt instructions web search
7. ❌ AI service call enables web search
8. ❌ All processes are logged to curri_back/log.txt
9. ❌ End-to-end test with actual curriculum file

## Priority Actions

1. **URGENT**: Fix syntax error in `curri_processor.py`
2. Update AI prompt call to pass new parameters
3. Verify web search is enabled in AI service
4. Test complete flow
