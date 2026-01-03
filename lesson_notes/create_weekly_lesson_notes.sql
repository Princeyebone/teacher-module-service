-- Create the 'weekly_lesson_notes' table for storing generated lesson notes
-- Run this in your PostgreSQL terminal

-- Enable pgcrypto for UUID generation if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop existing table if it exists (for development)
-- DROP TABLE IF EXISTS weekly_lesson_notes;

-- Create the weekly_lesson_notes table
CREATE TABLE weekly_lesson_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    
    -- Identifiers
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    indicator_id INT,  -- Reference to indicator table
    
    -- Header Fields
    week_date DATE NOT NULL,                    -- Friday of the week (current week's Friday)
    duration VARCHAR(50),                       -- e.g., "12:00 - 13:00" from timetable
    strand VARCHAR(255),
    substrand VARCHAR(255),
    content_standard TEXT,
    content_standard_code VARCHAR(50),
    indicator_text TEXT,                        -- The indicator text
    indicator_code VARCHAR(50),                 -- The indicator code
    class_size VARCHAR(50),                     -- Empty for teacher to fill
    week_number INT,                            -- Calculated from semester dates
    semester_name VARCHAR(255),
    lesson_number VARCHAR(20),                  -- e.g., "1 of 2"
    performance_indicator TEXT,                 -- AI-generated
    core_competency TEXT,                       -- AI-generated
    reference_page VARCHAR(255),                -- "{subject} curriculum"
    
    -- Table Section (3 phases) - Learner Activities and Resources
    phase1_activity TEXT,                       -- Phase 1: Starter - Learner Activity
    phase1_resources TEXT,                      -- Phase 1: Starter - Resources
    phase2_activity TEXT,                       -- Phase 2: New Learning - Learner Activity
    phase2_resources TEXT,                      -- Phase 2: New Learning - Resources
    phase3_activity TEXT,                       -- Phase 3: Reflection - Learner Activity
    phase3_resources TEXT,                      -- Phase 3: Reflection - Resources
    
    -- Tracking
    generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    generation_status VARCHAR(20) DEFAULT 'completed',  -- 'completed', 'failed', 'pending'
    
    -- Foreign Key Constraint
    CONSTRAINT fk_weekly_lesson_notes_teacher 
        FOREIGN KEY(teacher_id) 
        REFERENCES teacherprofile(id) 
        ON DELETE CASCADE,
    
    -- Unique constraint for idempotency: ONE lesson note per teacher+subject+class+indicator+week
    CONSTRAINT unique_weekly_lesson_note 
        UNIQUE(teacher_id, subject, class_name, indicator_id, week_date)
);

-- Create Indexes for performance
CREATE INDEX idx_weekly_lesson_notes_teacher_id ON weekly_lesson_notes(teacher_id);
CREATE INDEX idx_weekly_lesson_notes_subject ON weekly_lesson_notes(subject);
CREATE INDEX idx_weekly_lesson_notes_class_name ON weekly_lesson_notes(class_name);
CREATE INDEX idx_weekly_lesson_notes_week_date ON weekly_lesson_notes(week_date);
CREATE INDEX idx_weekly_lesson_notes_generated_at ON weekly_lesson_notes(generated_at);
CREATE INDEX idx_weekly_lesson_notes_indicator_id ON weekly_lesson_notes(indicator_id);

-- Verify table was created
SELECT 'weekly_lesson_notes table created successfully!' as status;
