-- Migration: Update lesson_briefs unique constraint
-- From: (teacher_id, subject, class_name, session_date)
-- To: (teacher_id, subject, class_name)
-- This ensures ONE brief per teacher+subject+class (updated with each new generation)

-- Step 1: Drop the existing unique constraint
ALTER TABLE lesson_briefs DROP CONSTRAINT IF EXISTS unique_lesson_brief;

-- Step 2: Delete duplicate rows (keep only the most recent one per teacher+subject+class)
DELETE FROM lesson_briefs a
USING lesson_briefs b
WHERE a.teacher_id = b.teacher_id
  AND a.subject = b.subject
  AND a.class_name = b.class_name
  AND a.generated_at < b.generated_at;

-- Step 3: Add the new unique constraint
ALTER TABLE lesson_briefs 
ADD CONSTRAINT unique_lesson_brief UNIQUE(teacher_id, subject, class_name);

-- Verify the constraint was created
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'lesson_briefs'::regclass;
