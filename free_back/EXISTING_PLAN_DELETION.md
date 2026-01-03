# Existing Plan Deletion - Implementation Complete

## ✅ Feature Added!

The Free Plan processor now **automatically checks for and deletes existing plans** before storing new ones, preventing duplicates and ensuring clean replacement.

---

## 🎯 What It Does

### Flow

```
1. AI generates plan successfully
   ↓
2. Check for existing plan
   ↓
3. If exists → Delete old plan first
   ↓
4. Store new plan
   ↓
5. Send completion notification
```

---

## 📝 Implementation Details

### Check Logic

```python
# After AI success, check if plan exists
existing_strands = await db.execute(
    select(Strand).where(
        and_(
            Strand.teacher_id == UUID(teacher_id),
            Strand.subject == subject,
            Strand.class_name == class_name
        )
    )
)
```

**Checks for**: Existing strands matching:
- ✅ Same `teacher_id`
- ✅ Same `subject`
- ✅ Same `class_name`

---

### Delete Logic (If Plan Exists)

Deletes in **correct order** to avoid FK constraint issues:

```python
1. Delete Indicators       (child)
   ↓
2. Delete Content Standards (child)
   ↓
3. Delete Substrands       (child)
   ↓
4. Delete Strands          (parent)
   ↓
5. Commit transaction
```

**Query for each**:
```python
delete(TableName).where(
    and_(
        TableName.teacher_id == UUID(teacher_id),
        TableName.subject == subject,
        TableName.class_name == class_name
    )
)
```

---

## 🔍 Example Scenarios

### Scenario 1: First Time Generation

**Input**:
- Teacher: 123
- Subject: Mathematics
- Class: Grade 4

**Process**:
```
✓ Check for existing plan
✓ No existing plan found
✓ Proceeding with fresh storage
→ Store new plan
✅ Complete
```

**Log Output**:
```
====================================================================================================
  CHECKING FOR EXISTING PLAN
====================================================================================================
✓ No existing plan found for Mathematics - Grade 4
   Proceeding with fresh storage

====================================================================================================
  DATABASE STORAGE
====================================================================================================
Storing new plan in database...
✅ Storage completed
```

---

### Scenario 2: Regenerating Existing Plan

**Input**:
- Teacher: 123
- Subject: Mathematics
- Class: Grade 4 (already has a plan)

**Process**:
```
✓ Check for existing plan
⚠️ Found existing plan!
   - 3 strands
   - 5 substrands
   - 12 content standards
   - 36 indicators
→ Delete old plan
   ✓ Deleted 36 indicators
   ✓ Deleted 12 content standards
   ✓ Deleted 5 substrands
   ✓ Deleted 3 strands
   ✓ Committed
→ Store new plan
✅ Complete
```

**Log Output**:
```
====================================================================================================
  CHECKING FOR EXISTING PLAN
====================================================================================================
⚠️ Found existing plan for Mathematics - Grade 4
   Existing strands: 3

====================================================================================================
  DELETING EXISTING PLAN
====================================================================================================
Deleting existing plan for teacher=123, subject=Mathematics, class=Grade 4
   Deleted 36 indicators
   Deleted 12 content standards
   Deleted 5 substrands
   Deleted 3 strands
✅ Old plan deleted successfully

====================================================================================================
  DATABASE STORAGE
====================================================================================================
Storing new plan in database...
✅ Storage completed
```

---

## 📊 WebSocket Updates

The frontend receives progress updates:

### Update 1: Checking
```json
{
  "type": "semplan_processing",
  "status": "checking",
  "message": "Checking for existing plan...",
  "subject": "Mathematics",
  "class_name": "Grade 4"
}
```

### Update 2: Deleting (if exists)
```json
{
  "type": "semplan_processing",
  "status": "deleting_old",
  "message": "Deleting existing plan for Mathematics - Grade 4...",
  "subject": "Mathematics",
  "class_name": "Grade 4"
}
```

### Update 3: Storing
```json
{
  "type": "semplan_processing",
  "status": "storing",
  "message": "Storing new plan in database...",
  "subject": "Mathematics",
  "class_name": "Grade 4"
}
```

---

## 🛡️ Error Handling

If deletion fails, processing continues:

```python
try:
    # Check and delete
    ...
except Exception as e:
    detail_logger.error(f"❌ Error checking/deleting existing plan: {e}")
    detail_logger.error(f"   Will proceed with storage anyway")
    logger.warning(f"Error checking existing plan: {e}")
# Continue with storage
```

**Why**: Even if deletion fails, storing the new plan is better than failing completely. The new plan will still be stored (though duplicates might exist).

---

## 📋 Benefits

### Before This Feature
❌ Regenerating plan creates duplicates:
- 2x strands
- 2x substrands
- 2x content standards
- 2x indicators
❌ Confusion about which plan is current
❌ Database bloat
❌ Frontend shows duplicate data

### After This Feature
✅ Clean replacement:
- Old plan deleted first
- Only new plan exists
✅ Clear which plan is current (always the latest)
✅ No database bloat
✅ Frontend shows single, correct plan

---

## 🔍 Database Impact

### Query Pattern

**Check Query** (SELECT):
```sql
SELECT * FROM strand 
WHERE teacher_id = '123' 
  AND subject = 'Mathematics' 
  AND class_name = 'Grade 4'
```

**Delete Queries** (DELETE):
```sql
-- 1. Indicators
DELETE FROM indicator 
WHERE teacher_id = '123' 
  AND subject = 'Mathematics' 
  AND class_name = 'Grade 4';

-- 2. Content Standards
DELETE FROM contentstandard 
WHERE teacher_id = '123' 
  AND subject = 'Mathematics' 
  AND class_name = 'Grade 4';

-- 3. Substrands
DELETE FROM substrand 
WHERE teacher_id = '123' 
  AND subject = 'Mathematics' 
  AND class_name = 'Grade 4';

-- 4. Strands
DELETE FROM strand 
WHERE teacher_id = '123' 
  AND subject = 'Mathematics' 
  AND class_name = 'Grade 4';
```

**Performance**: Very fast, indexed on `(teacher_id, subject, class_name)`

---

## 📈 Use Cases

### Use Case 1: Refining a Plan
Teacher generates a plan, reviews it, and wants to regenerate with different parameters:
```
1. First generation: Success
2. Review: "I want more focus on fractions"
3. Add topic_description: "Fractions and Decimals"
4. Regenerate: Old plan deleted, new plan stored ✅
```

### Use Case 2: Semester Updates
Curriculum changes mid-semester:
```
1. Generated plan at semester start
2. Curriculum update announced
3. Regenerate plan with new info
4. Old plan deleted, updated plan stored ✅
```

### Use Case 3: Error Correction
AI generated incorrect plan:
```
1. First attempt: Wrong grade level content
2. Fix parameters
3. Regenerate: Old plan deleted, correct plan stored ✅
```

---

## 🎯 Matching Criteria

Plans are considered "existing" if they match **ALL THREE**:
1. ✅ Same `teacher_id`
2. ✅ Same `subject`  
3. ✅ Same `class_name`

**Different scenarios**:

| Scenario | Same Teacher | Same Subject | Same Class | Result |
|----------|--------------|--------------|------------|--------|
| Same plan regenerated | ✅ | ✅ | ✅ | **DELETE OLD** |
| Different subject | ✅ | ❌ | ✅ | Keep both |
| Different class | ✅ | ✅ | ❌ | Keep both |
| Different teacher | ❌ | ✅ | ✅ | Keep both |

---

## ✅ Testing Checklist

### Test 1: First Generation
- [ ] Generate plan for new subject/class
- [ ] Check logs: "No existing plan found"
- [ ] Verify plan stored
- [ ] Check DB: Only 1 plan exists

### Test 2: Regeneration
- [ ] Generate plan for existing subject/class
- [ ] Check logs: "Found existing plan"
- [ ] Check logs: "Deleted X strands/substrands/etc"
- [ ] Verify new plan stored
- [ ] Check DB: Only 1 plan exists (the new one)

### Test 3: Multiple Classes
- [ ] Generate plan for Math - Grade 4
- [ ] Generate plan for Math - Grade 5
- [ ] Verify both plans exist (different class_name)

### Test 4: Multiple Subjects
- [ ] Generate plan for Math - Grade 4
- [ ] Generate plan for Science - Grade 4
- [ ] Verify both plans exist (different subject)

---

## 📚 Summary

| Aspect | Implementation |
|--------|----------------|
| **Check Location** | After AI success, before storage |
| **Check Criteria** | teacher_id + subject + class_name |
| **Delete Order** | Indicators → Standards → Substrands → Strands |
| **Error Handling** | Continue with storage if delete fails |
| **Logging** | Full logging of check and delete operations |
| **WebSocket** | Real-time updates for checking and deleting |
| **Performance** | Fast (indexed queries) |

---

## 🚀 Status

**Feature Complete and Active!** ✅

Every free plan generation now:
- ✅ Checks for existing plan
- ✅ Deletes old plan if found
- ✅ Stores new plan cleanly
- ✅ Logs all operations
- ✅ Sends WebSocket updates
- ✅ Handles errors gracefully

**Result**: Clean, duplicate-free plan management! 🎯
