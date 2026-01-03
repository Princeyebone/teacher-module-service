-- Create table for Student Lesson Packs
CREATE TABLE IF NOT EXISTS student_lesson_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES teacherprofile(id),
    session_id INTEGER REFERENCES classsession(id),
    slide_id UUID REFERENCES slides(id),
    
    subject VARCHAR(255),
    class_name VARCHAR(255),
    
    -- Content
    simplified_notes TEXT,  -- HTML/Markdown content
    video_resources JSONB DEFAULT '[]'::jsonb, -- [{title, url, thumbnail, duration}]
    podcast_audio_url TEXT, -- URL to GCS
    
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one pack per session
    CONSTRAINT unique_pack_per_session UNIQUE (teacher_id, session_id)
);

-- Indexes
CREATE INDEX idx_student_packs_teacher ON student_lesson_packs(teacher_id);
CREATE INDEX idx_student_packs_session ON student_lesson_packs(session_id);
CREATE INDEX idx_student_packs_status ON student_lesson_packs(status);
