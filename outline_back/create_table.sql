-- SQL Statement to Create Outline Table
-- Run this in your PostgreSQL terminal

CREATE TABLE outline (
    id SERIAL PRIMARY KEY,
    teacher_id UUID NOT NULL REFERENCES teacherprofile(id),
    subject VARCHAR NOT NULL,
    class_name VARCHAR NOT NULL,
    
    -- Outline content (AI-generated)
    outline_content TEXT NOT NULL,
    
    -- Metadata
    education_system VARCHAR,
    academic_level VARCHAR,
    semester_name VARCHAR,
    term VARCHAR,
    
    -- Tracking
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Create indexes for faster queries
CREATE INDEX idx_outline_teacher_id ON outline(teacher_id);
CREATE INDEX idx_outline_subject ON outline(subject);
CREATE INDEX idx_outline_class_name ON outline(class_name);
CREATE INDEX idx_outline_teacher_subject_class ON outline(teacher_id, subject, class_name);

-- Add comment
COMMENT ON TABLE outline IS 'Stores AI-generated course/subject outlines for Teacher Lesson Pack';
