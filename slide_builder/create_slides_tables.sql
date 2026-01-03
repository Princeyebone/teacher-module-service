-- Slide Builder Tables
-- Run this to create the slides and slide_images tables

-- Main slides table
CREATE TABLE IF NOT EXISTS slides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES teacherprofile(id) ON DELETE CASCADE,
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    topic VARCHAR(500),
    indicator_ids JSONB DEFAULT '[]'::jsonb,
    content_json JSONB NOT NULL,
    generation_status VARCHAR(50) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NOTE: We removed the unique constraint to allow multiple slides per teacher+subject+class+topic
-- History is preserved by creating new entries each day

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_slides_teacher_id ON slides(teacher_id);
CREATE INDEX IF NOT EXISTS idx_slides_subject ON slides(subject);
CREATE INDEX IF NOT EXISTS idx_slides_class_name ON slides(class_name);
CREATE INDEX IF NOT EXISTS idx_slides_created_at ON slides(created_at);
CREATE INDEX IF NOT EXISTS idx_slides_date ON slides(DATE(created_at));

-- Slide images table for tracking image generation
CREATE TABLE IF NOT EXISTS slide_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slide_id UUID NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    slide_item_id VARCHAR(255) NOT NULL,
    prompt TEXT NOT NULL,
    style VARCHAR(100),
    alt_text TEXT,
    image_url TEXT,
    gcs_path TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_slide_images_slide_id ON slide_images(slide_id);
CREATE INDEX IF NOT EXISTS idx_slide_images_status ON slide_images(status);

-- Add trigger to update updated_at on slides
CREATE OR REPLACE FUNCTION update_slides_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_slides_updated_at ON slides;
CREATE TRIGGER trigger_slides_updated_at
    BEFORE UPDATE ON slides
    FOR EACH ROW
    EXECUTE FUNCTION update_slides_updated_at();

-- Add trigger to update updated_at on slide_images
DROP TRIGGER IF EXISTS trigger_slide_images_updated_at ON slide_images;
CREATE TRIGGER trigger_slide_images_updated_at
    BEFORE UPDATE ON slide_images
    FOR EACH ROW
    EXECUTE FUNCTION update_slides_updated_at();

-- Drop old unique constraint if it exists (for existing databases)
ALTER TABLE slides DROP CONSTRAINT IF EXISTS unique_slide_per_teacher_subject_class_topic;

-- Grant permissions (adjust user as needed)
-- GRANT ALL ON slides TO your_app_user;
-- GRANT ALL ON slide_images TO your_app_user;

COMMENT ON TABLE slides IS 'Stores AI-generated lesson slides as structured JSON';
COMMENT ON TABLE slide_images IS 'Tracks image generation status for slide images';
COMMENT ON COLUMN slides.content_json IS 'Full slide deck content conforming to the slide schema';
COMMENT ON COLUMN slides.indicator_ids IS 'Array of indicator IDs this slide deck covers';
COMMENT ON COLUMN slide_images.status IS 'pending, generating, generated, failed';
