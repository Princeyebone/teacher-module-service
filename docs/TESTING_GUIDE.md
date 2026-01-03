# Testing Guide - Complete Flow Test

## Overview

This guide explains how to test the complete slide generation and student lesson pack flow.

---

## Quick Start

### Option 1: Run Everything (Recommended)

```bash
python run_complete_test.py
```

This will:
1. ✅ Clear old test data
2. ✅ Run complete flow test
3. ✅ Show results

### Option 2: Manual Steps

```bash
# Step 1: Clear test data
python slide_builder/clear_test_data.py

# Step 2: Run test
python slide_builder/test_complete_flow.py
```

---

## What Gets Tested

### 1. **Database Connection** ✅
- Verifies PostgreSQL connection
- Tests basic queries

### 2. **Session Finding** ✅
- Finds active class sessions
- Locates sessions with curriculum data

### 3. **Curriculum Retrieval** ✅
- Fetches strand, substrand, content standard
- Retrieves indicator text

### 4. **RAG Retrieval** ✅
- Searches uploaded documents
- Retrieves relevant content chunks

### 5. **AI Slide Generation** ✅
- Calls Vertex AI Gemini
- Generates structured slides
- Creates assessments (MCQ + Essay)

### 6. **Slide Saving** ✅
- Saves to database
- Stores content_json

### 7. **Image Prompt Saving** ✅
- Extracts image prompts from slides
- Saves to slide_images table

### 8. **Image Generation** ✅
- Generates images using Imagen
- Updates slide_images with URLs

### 9. **Student Lesson Pack Generation** ⭐ NEW
- Generates simplified notes (ELI10 style)
- Fetches 5 educational videos
- Creates 10-minute podcast audio
- Extracts assessments (MCQ + Essay)
- Builds structured slide format
- Stores in student_lesson_packs table

---

## Test Output

### Console Output

The test will show progress for each step:

```
======================================================================
  TEST 1: Database Connection
======================================================================
✅ Database connection works

======================================================================
  TEST 2: Find Session with Curriculum
======================================================================
   Found 10 total sessions
✅ Found session with curriculum:
      Session ID: 1618
      Subject: Physics
      Class: Class 11A
      Date: 2025-12-28
      Strand: Mechanics

... (more tests)

======================================================================
  TEST 9: Student Lesson Pack Generation
======================================================================
   Generating student lesson pack...
      Slide ID: 8cc2a1ab-8870-47b0-8f44-fb18f788f441
      Session ID: 1618
      Subject: Physics
      Class: Class 11A
✅ Student Lesson Pack created successfully

   📦 Pack Details:
      Pack ID: 743ef846-a7d4-4a3e-8116-eccb2f3938de
      Session ID: 1618
      Status: completed

   📝 Legacy Fields:
      Simplified Notes: ✅ Yes
      Video Resources: 5 videos
      Podcast Audio: ✅ Yes
         URL: https://storage.googleapis.com/bucket/student_packs/teacher_id/1618/podcast.mp3...

   🎯 Structured Content (NEW):
      Pack ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
      Topic: Motion
      Total Slides: 8
      Slide Types: ['title', 'notes', 'video_resources', 'podcast', 'assessment_mcq', 'assessment_essay', 'answer_key_mcq', 'answer_key_essay']

   📊 Summary:
      Has Notes: True
      Video Count: 5
      Has Podcast: True
      Podcast Duration: 11.1 minutes
      MCQ Count: 15
      Essay Count: 5

   🔑 Assessment Verification:
      MCQ Assessment: ✅
      Essay Assessment: ✅
      MCQ Answer Key: ✅
      Essay Answer Key: ✅
      Answer Keys at End: ✅

   🔒 Security Check (Assessments):
      Assessments Secure: ✅ (No answers in questions)

✅ All verifications passed!

======================================================================
  TEST SUMMARY
======================================================================
   Total time: 245.3 seconds

   Results:
   • Database connection: ✅
   • Session found: ✅
   • Curriculum: ✅
   • RAG retrieval: ✅
   • AI generation: ✅
   • Slide saved: ✅
   • Images saved: 3
   • Images generated: 3
   • Student pack: ✅

   🎉 SUCCESS! Slide ID: 8cc2a1ab-8870-47b0-8f44-fb18f788f441
```

### Log File

Detailed logs are saved to: `slide_builder/test_flow.log`

---

## Verification Checklist

After the test completes, verify:

### ✅ Slides Table
```sql
SELECT id, topic, generation_status, 
       jsonb_array_length(content_json->'slides') as slide_count
FROM slides
WHERE teacher_id = '7bed2b69-8000-4b36-8e91-7fe0b70c9d82'
ORDER BY created_at DESC
LIMIT 1;
```

### ✅ Student Lesson Packs Table
```sql
SELECT id, session_id, status, 
       simplified_notes IS NOT NULL as has_notes,
       podcast_audio_url IS NOT NULL as has_audio,
       content_json IS NOT NULL as has_structured_content
FROM student_lesson_packs
WHERE teacher_id = '7bed2b69-8000-4b36-8e91-7fe0b70c9d82'
ORDER BY created_at DESC
LIMIT 1;
```

### ✅ Structured Content
```sql
SELECT 
    content_json->'pack_id' as pack_id,
    content_json->'topic' as topic,
    jsonb_array_length(content_json->'slides') as slide_count,
    content_json->'summary' as summary
FROM student_lesson_packs
WHERE teacher_id = '7bed2b69-8000-4b36-8e91-7fe0b70c9d82'
ORDER BY created_at DESC
LIMIT 1;
```

### ✅ Slide Types
```sql
SELECT 
    jsonb_array_elements(content_json->'slides')->'type' as slide_type
FROM student_lesson_packs
WHERE teacher_id = '7bed2b69-8000-4b36-8e91-7fe0b70c9d82'
ORDER BY created_at DESC
LIMIT 1;
```

Expected result:
```
slide_type
-----------------
"title"
"notes"
"video_resources"
"podcast"
"assessment_mcq"
"assessment_essay"
"answer_key_mcq"
"answer_key_essay"
```

---

## Troubleshooting

### Issue: "No sessions found"

**Solution**: Create a class session in the database:
```sql
INSERT INTO classsession (teacher_id, subject, class_name, date, start_time, end_time, is_completed)
VALUES (
    '7bed2b69-8000-4b36-8e91-7fe0b70c9d82',
    'Physics',
    'Class 11A',
    CURRENT_DATE,
    '09:00:00',
    '10:00:00',
    false
);
```

### Issue: "No curriculum found"

**Solution**: The test will continue anyway. It will generate slides without curriculum context.

### Issue: "AI generation failed: CREDENTIAL ERROR"

**Solution**: Update your Google Cloud credentials:
1. Go to Google Cloud Console → IAM & Admin → Service Accounts
2. Find your Vertex AI service account
3. Click 'Keys' → 'Add Key' → 'Create new key' (JSON)
4. Update `GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI` in `.env`

### Issue: "Student pack generation failed"

**Solution**: Check the logs in `slide_builder/test_flow.log` for detailed error messages.

### Issue: "Audio synthesis failed"

**Possible causes**:
- Missing `pydub` library: `pip install pydub`
- Missing `ffmpeg`: Install from https://ffmpeg.org/
- GCS upload error: Check credentials and bucket permissions

---

## Expected Results

### Success Criteria

✅ All 9 tests pass
✅ Slide deck saved with 8+ slides
✅ Student pack created with status "completed"
✅ Structured content_json present
✅ 8 slide types in correct order
✅ Answer keys at end of slides
✅ Assessments don't contain answers
✅ Audio URL present
✅ 5 videos found

### Performance

- **Total time**: 3-5 minutes
- **Slide generation**: 30-60 seconds
- **Student pack**: 2-4 minutes
  - Notes: 10-20 seconds
  - Videos: 5-10 seconds
  - Podcast script: 15-30 seconds
  - Audio synthesis: 90-180 seconds

---

## Clean Up

### Clear Test Data

```bash
python slide_builder/clear_test_data.py
```

This will delete:
- All slides for test teacher
- All student packs for test teacher
- All slide images for test teacher

---

## Next Steps

After successful test:

1. **Test API Endpoints**
   - Visit `http://localhost:8001/api/docs`
   - Test `/api/teacher/student-packs` endpoints

2. **Frontend Integration**
   - Use `docs/STUDENT_LESSON_PACK_API.md`
   - Implement UI components

3. **Production Deployment**
   - Update environment variables
   - Configure GCS bucket
   - Set up monitoring

---

## Support

- **Logs**: `slide_builder/test_flow.log`
- **API Docs**: `http://localhost:8001/api/docs`
- **Documentation**: `docs/STUDENT_LESSON_PACK_API.md`

---

**Ready to test? Run:** `python run_complete_test.py` 🚀
