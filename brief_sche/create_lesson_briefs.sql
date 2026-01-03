-- Create the 'lesson_briefs' table for storing generated lesson briefs
-- Run this in your PostgreSQL terminal

-- Enable pgcrypto for UUID generation if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop existing table if it exists (for development)
DROP TABLE IF EXISTS lesson_briefs;

-- Create the lesson_briefs table
CREATE TABLE lesson_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    
    -- Session References
    session_date DATE NOT NULL,
    session_id INTEGER,  -- The session this brief is for
    previous_session_id INTEGER,  -- The previous session
    
    -- Lesson Context Data (stored as JSONB for flexibility)
    previous_lesson JSONB DEFAULT '{}'::jsonb,  -- {strand, substrand, content_standard, indicators[]}
    todays_lesson JSONB DEFAULT '{}'::jsonb,    -- {strand, substrand, content_standard, indicators[]}
    weekly_activity JSONB DEFAULT '{}'::jsonb,  -- {week_number, topic, activity}
    
    -- Generated Content
    brief_content TEXT NOT NULL,  -- The AI-generated lesson brief
    
    -- Tracking
    generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    generation_status VARCHAR(20) DEFAULT 'completed',  -- 'completed', 'failed', 'pending'
    
    -- Foreign Key Constraint
    CONSTRAINT fk_lesson_briefs_teacher 
        FOREIGN KEY(teacher_id) 
        REFERENCES teacherprofile(id) 
        ON DELETE CASCADE,
    
    -- Unique constraint for idempotency: ONE brief per teacher+subject+class
    -- New generations update the existing brief with latest session info
    CONSTRAINT unique_lesson_brief 
        UNIQUE(teacher_id, subject, class_name)
);

-- Create Indexes for performance
CREATE INDEX idx_lesson_briefs_teacher_id ON lesson_briefs (teacher_id);
CREATE INDEX idx_lesson_briefs_subject ON lesson_briefs (subject);
CREATE INDEX idx_lesson_briefs_class_name ON lesson_briefs (class_name);
CREATE INDEX idx_lesson_briefs_session_date ON lesson_briefs (session_date);
CREATE INDEX idx_lesson_briefs_generated_at ON lesson_briefs (generated_at);
