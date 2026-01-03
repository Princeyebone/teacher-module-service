-- Create table for Student Support Packs
-- Personalized learning packs tailored to individual student needs

CREATE TABLE IF NOT EXISTS student_support_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES teacherprofile(id),
    
    -- Student information
    student_name VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    
    -- Education context
    edu_sys VARCHAR(100),  -- Education system (e.g., "Cambridge", "IB")
    edu_lvl VARCHAR(100),  -- Education level (e.g., "Primary", "Secondary")
    
    -- Lesson details
    topic VARCHAR(500) NOT NULL,
    interests JSONB DEFAULT '[]'::jsonb,  -- Student's interests for personalization
    health_considerations TEXT,  -- Special needs, health issues, etc.
    
    -- Generated content
    content_json JSONB,  -- Full structured pack with slides
    teacher_instructions TEXT,  -- Special instructions for the teacher
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_support_packs_teacher ON student_support_packs(teacher_id);
CREATE INDEX IF NOT EXISTS idx_support_packs_status ON student_support_packs(status);
CREATE INDEX IF NOT EXISTS idx_support_packs_subject_class ON student_support_packs(teacher_id, subject, class_name);
CREATE INDEX IF NOT EXISTS idx_support_packs_created ON student_support_packs(created_at DESC);

-- Comment on table
COMMENT ON TABLE student_support_packs IS 'Personalized learning packs for individual students with specific needs and interests';
