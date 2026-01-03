# Outline Generation Integration Summary

## Overview

Course/Subject outline generation is now **fully integrated** with semester planning. Instead of being a separate background task, outline generation runs **inline** within the same background task as plan creation.

**Key Benefits:**
- **Atomic Operation**: If outline fails, the entire plan creation fails - no orphan plans
- **Single Background Task**: One task per plan creation, not two
- **Simpler Worker Management**: No need for a separate outline worker

## Architecture Change

### Before (Separate Tasks)
```
User Action → Plan Task (Queue 1) → Success → Outline Task (Queue 2)
                                           ↘ Outline could fail independently
                                             (leaving orphan plan)
```

### After (Inline Integration)
```
User Action → Plan + Outline Task (Single Task)
              ├── Store Plan
              ├── Generate Outline (inline)
              └── Commit Both or Fail Both
```

## Implementation Details

### 1. Free Plan (`free_back/free_processor.py`)

**Flow:**
1. Generate plan via AI
2. Store plan in database (strands, substrands, etc.)
3. Verify storage
4. **Generate outline inline** (using `generate_outline_inline`)
5. Commit both plan AND outline together
6. Send success notification

**On Failure:** Rollback everything, send error notification

### 2. Curriculum Plan (`curri_back/curri_processor.py`)  

**Flow:**
1. Process curriculum file
2. Perform retrieval for syllabus content
3. Generate plan via AI
4. Store plan in database
5. **Generate outline inline** (using `generate_outline_inline`)
6. Commit both plan AND outline together
7. Send success notification

**On Failure:** Rollback everything, send error notification

### 3. Sem Plan (`semplan_ground/semplan_back.py`)

**Flow:**
1. Extract text from uploaded file
2. Generate plan via AI
3. Store plan in database
4. **Generate outline inline** (using `generate_outline_inline`)
5. Commit outline
6. Send success notification

**On Failure:** Send error notification, plan fails

## Core Utility

**File:** `outline_back/inline_outline.py`

**Function:** `generate_outline_inline()`

```python
async def generate_outline_inline(
    db,                    # Reuse existing database session
    teacher_id: str,
    subject: str,
    class_name: str,
    education_system: Optional[str] = None,
    academic_level: Optional[str] = None,
    semester_name: Optional[str] = None,
    term: Optional[str] = None
) -> Dict[str, Any]:
    # 1. Fetch curriculum data from just-stored plan
    # 2. Build AI prompt
    # 3. Call AI for outline generation
    # 4. Store outline in database
    # Returns result or raises exception
```

## WebSocket Status Messages

The frontend now receives these status updates in sequence:

1. `status: "started"` - Plan creation started
2. `status: "processing"` - AI processing
3. `status: "storing"` - Storing plan data
4. `status: "generating_outline"` - **NEW: Generating outline**
5. `status: "completed"` - Both plan AND outline completed
   - Includes `outline_generated: true`

## Worker Requirements

**No separate outline worker needed!**

Just run the existing workers:
- `python -m free_back.run_free_workers` - For free plan
- `python -m curri_back.run_curri_workers` - For curriculum plan
- `python -m semplan_ground.run_semplan_back_worker` - For semplan

## Error Handling

If outline generation fails:
1. Error is logged with full traceback
2. Database rollback is performed (where applicable)
3. Error notification sent to user
4. Task returns error status
5. **No orphan plans** - if outline fails, plan also fails

## Files Modified

1. `free_back/free_processor.py` - Inline outline generation added
2. `curri_back/curri_processor.py` - Inline outline generation added
3. `semplan_ground/semplan_back.py` - Inline outline generation added
4. `outline_back/inline_outline.py` - **NEW** shared utility

## Files That Can Be Deprecated

The following files are no longer needed for automatic outline generation:
- `outline_back/outline_worker.py` - Separate worker no longer needed
- `outline_back/run_outline_workers.py` - No separate worker to run
- `outline_back/enqueue_outline.py` - No longer enqueueing separate jobs

Note: Keep these files if you want to support manual/on-demand outline regeneration.

## Testing

To test the integration:
1. Create a semester plan using any of the three methods
2. Watch the worker logs for:
   - Plan storage success
   - "Generating course outline inline..." message
   - Outline generation success
3. Verify both plan AND outline exist in database
4. Test failure case: temporarily break outline generation to confirm entire task fails
