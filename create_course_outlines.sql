-- Enable pgcrypto for UUID generation if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop the old 'outline' table if it exists
DROP TABLE IF EXISTS outline;

-- Drop the 'course_outlines' table if it exists to start fresh
DROP TABLE IF EXISTS course_outlines;

-- Create the new 'course_outlines' table
CREATE TABLE course_outlines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    
    -- Terminology Settings
    terminology_type VARCHAR(20) DEFAULT 'Course',
    terminology_role VARCHAR(20) DEFAULT 'Lecturer',
    
    -- Dynamic Sections (JSONB)
    school_info_headers JSONB DEFAULT '[]'::jsonb,
    lecture_info JSONB DEFAULT '{"left": [], "right": []}'::jsonb,
    course_objectives JSONB DEFAULT '[""]'::jsonb,
    course_description TEXT DEFAULT '',
    learning_outcomes JSONB DEFAULT '[""]'::jsonb,
    course_delivery TEXT DEFAULT '',
    course_content JSONB DEFAULT '[]'::jsonb,
    policies JSONB DEFAULT '[""]'::jsonb,
    
    -- Metadata / Integration
    subject_name VARCHAR(255),
    class_name VARCHAR(255),
    academic_year VARCHAR(50),
    semester VARCHAR(50),
    
    -- Status & Versioning
    status VARCHAR(20) DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    last_auto_save TIMESTAMP WITHOUT TIME ZONE,

    -- Foreign Key Constraint
    CONSTRAINT fk_course_outlines_teacher 
        FOREIGN KEY(teacher_id) 
        REFERENCES teacherprofile(id) 
        ON DELETE CASCADE
);

-- Create Indexes for performance
CREATE INDEX idx_course_outlines_teacher_id ON course_outlines (teacher_id);
CREATE INDEX idx_course_outlines_subject_name ON course_outlines (subject_name);
CREATE INDEX idx_course_outlines_class_name ON course_outlines (class_name);
