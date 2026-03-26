"""
Curriculum Background Processor

This module provides a unified background task that:
1. Extracts text and chunks from curriculum files
2. Generates embeddings for the chunks
3. Performs retrieval to get relevant syllabus content
4. Builds a prompt and sends to AI for semester plan generation
5. Stores the result in the Strand/Substrand/ContentStandard/Indicator tables

This allows creating a semester plan from just a curriculum file when no
semester plan file is available.
"""

import os
import sys
import json
import logging
import traceback
import asyncio
from datetime import datetime
from uuid import UUID
from typing import Dict, List, Optional, Any

# Configure base logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create dedicated file logger for curriculum processing
curri_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")
file_handler = logging.FileHandler(curri_log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Create a separate logger for detailed curriculum logging
detail_logger = logging.getLogger("curriculum_detail")
detail_logger.setLevel(logging.INFO)
detail_logger.addHandler(file_handler)
detail_logger.propagate = False  # Don't propagate to root logger

def log_separator():
    """Log a separator line for readability"""
    detail_logger.info("=" * 100)

def log_section(title: str):
    """Log a section header"""
    detail_logger.info("")
    detail_logger.info("=" * 100)
    detail_logger.info(f"  {title}")
    detail_logger.info("=" * 100)

# Import database and models
try:
    from app.core.database import get_db, async_engine
    from app.models.model import KnowledgeMetadata, KnowledgeEmbedding, Strand, Substrand, ContentStandard, Indicator
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, and_, delete
    logger.info("✅ Database imports successful")
except ImportError as e:
    logger.error(f"❌ Database import error: {e}")
    raise

# Import RAG components - handle each import separately
TEXT_EXTRACTION_AVAILABLE = False
EMBEDDING_AVAILABLE = False
RETRIEVAL_AVAILABLE = False

try:
    from app.rag.text import extract_text_from_pdf_pymupdf, chunk_text_with_langchain
    TEXT_EXTRACTION_AVAILABLE = True
    logger.info("✅ Text extraction imports successful")
except ImportError as e:
    logger.warning(f"⚠️ Text extraction not available: {e}")
    extract_text_from_pdf_pymupdf = None
    chunk_text_with_langchain = None

try:
    from app.rag.embedding import generate_embeddings_with_gemini
    EMBEDDING_AVAILABLE = True
    logger.info("✅ Embedding imports successful")
except ImportError as e:
    logger.warning(f"⚠️ Embedding not available (Vertex AI may not be installed): {e}")
    generate_embeddings_with_gemini = None

try:
    from app.rag.retrieval_task import perform_retrieval
    RETRIEVAL_AVAILABLE = True
    logger.info("✅ Retrieval imports successful")
except ImportError as e:
    logger.error(f"❌ Retrieval import error (required): {e}")
    raise

# Import AI service
try:
    from app.services.external_service import send_semester_plan_to_ai
    logger.info("✅ AI service import successful")
except ImportError as e:
    logger.error(f"❌ AI service import error: {e}")
    raise

# Import WebSocket functions
try:
    from app.sch_ground.background import publish_ws_message, save_notification
    logger.info("✅ WebSocket imports successful")
except ImportError as e:
    logger.error(f"❌ WebSocket import error: {e}")
    # Create mock functions if not available
    async def publish_ws_message(teacher_id: str, message: dict):
        logger.info(f"[MOCK WS] {teacher_id}: {message}")
    async def save_notification(**kwargs):
        logger.info(f"[MOCK NOTIF] {kwargs}")

# Import GCS utilities
try:
    from app.services.gcs_utils import get_file_from_gcs
    from app.core.config import settings
    GCS_AVAILABLE = True
    logger.info("✅ GCS utilities import successful")
except ImportError as e:
    logger.error(f"❌ GCS utilities import error: {e}")
    GCS_AVAILABLE = False
    get_file_from_gcs = None


async def download_file_from_gcs(gcs_file_name: str) -> str:
    """
    Download a file from GCS to local temp storage.
    
    Args:
        gcs_file_name: The GCS file path (e.g., "curriculum/teacher_id/class/subject.pdf")
        
    Returns:
        Local file path where the file was saved
    """
    import tempfile
    
    if not GCS_AVAILABLE or not get_file_from_gcs:
        raise RuntimeError("GCS utilities not available")
    
    # Create a temp file with the same extension
    file_ext = os.path.splitext(gcs_file_name)[1]
    temp_fd, local_path = tempfile.mkstemp(suffix=file_ext)
    os.close(temp_fd)
    
    try:
        logger.info(f"📥 Downloading file from GCS: {gcs_file_name}")
        
        # Download file content
        content = get_file_from_gcs(settings.GCS_BUCKET_NAME, gcs_file_name)
        
        if content is None:
            raise RuntimeError(f"Failed to download file from GCS: {gcs_file_name}")
        
        # Save to local file
        with open(local_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"✅ Successfully downloaded file to: {local_path}")
        return local_path
        
    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(local_path):
            os.remove(local_path)
        raise RuntimeError(f"Error downloading file from GCS: {e}")



def build_curriculum_prompt(
    retrieval_chunks: List[Dict[str, Any]],
    session_data: dict = None,
    class_name: str = None,
    subject: str = None,
    education_system: str = None,
    education_level: str = None,
    semester_name: str = None,
    term: str = None
) -> str:
    """
    Build a structured prompt for processing curriculum data using AI with web search.
    Uses retrieved RAG chunks instead of extracted text and instructs AI to use web search for additional context.
    
    Args:
        retrieval_chunks: Top chunks retrieved from the RAG system (syllabus)
        session_data: Session data including academic calendar and class sessions
        class_name: The specific class name to focus on
        subject: The specific subject to focus on
        education_system: Education system (e.g., "Ghana", "Cambridge")
        education_level: Education level (e.g., "Primary", "JHS")
        semester_name: Current semester name (e.g., "First Semester 2025")
        term: Current term (e.g., "Term 1", "Term 2")
        
    Returns:
        A structured prompt for the AI model with web search instructions
    """
    # Format retrieved chunks into text
    chunks_text = "\n\n---\n\n".join([
        f"[Chunk {i+1} - Similarity: {chunk.get('similarity', 0):.2f}]\n{chunk.get('chunk_text', '')}"
        for i, chunk in enumerate(retrieval_chunks)
    ])
    
    # Validate session_data structure
    available_weeks = []
    week_details = []
    
    if session_data and 'weekly_sessions' in session_data:
        available_weeks = list(session_data['weekly_sessions'].keys())
        for week_key, week_data in session_data['weekly_sessions'].items():
            session_count = len(week_data.get('sessions', []))
            week_details.append(f"{week_key}: {session_count} sessions")
    
    # Create the example JSON structure
    example_json = '''{
  "strand_data": [
    {
      "strand_name": "Example Strand Name",
      "weeks": []
    }
  ],
  "substrand_data": [
    {
      "strand_name": "Example Strand Name",
      "substrand_name": "Example Substrand Name",
      "weeks": []
    }
  ],
  "content_standard_data": [
    {
      "strand_name": "Example Strand Name",
      "substrand_name": "Example Substrand Name",
      "content_standard_code": "EXAMPLE.CODE.1",
      "content_standard_text": "Example content standard description"
    }
  ],
  "indicator_data": [
    {
      "strand_name": "Example Strand Name",
      "substrand_name": "Example Substrand Name",
      "content_standard_code": "EXAMPLE.CODE.1",
      "indicator_code": "EXAMPLE.CODE.1.1",
      "indicator_text": "Example indicator description"
    }
  ]
}'''
    
    prompt = f"""You are an Educational Curriculum Mapping AI with web search capabilities. Analyze syllabus/curriculum content and map it to actual teaching sessions.

IMPORTANT WEB SEARCH INSTRUCTION:
The curriculum content provided below may NOT be sufficient to fully map out all strands, substrands, content standards, and indicators for the entire semester.
If the retrieved content is incomplete or lacks detail, you MUST perform a web search to find additional curriculum information.

USE WEB SEARCH to find:
- Official curriculum documents for {education_system if education_system else ''} {education_level if education_level else ''} education system
- Detailed {subject if subject else ''} syllabus for {class_name if class_name else ''} 
- Strands, substrands, content standards, and indicators for {semester_name if semester_name else 'this semester'} {term if term else ''}
- Week-by-week teaching plans and learning outcomes

EDUCATIONAL CONTEXT:
- Education System: {education_system if education_system else "Not specified"}
- Education Level: {education_level if education_level else "Not specified"}  
- Class Name: {class_name if class_name else "Not specified"}
- Subject: {subject if subject else "Not specified"}
- Semester: {semester_name if semester_name else "Not specified"}
- Term: {term if term else "Not specified"}

RETRIEVED CURRICULUM CONTENT (from local syllabus database):
Use this as a GUIDE, but supplement with web search for missing information.
{chunks_text}

AVAILABLE TEACHING SESSIONS:
- WeeklySessions: {json.dumps(session_data, indent=2) if session_data else "No session data provided"}

AVAILABLE WEEKS: {', '.join(available_weeks) if available_weeks else "None"}
WEEK DETAILS: {', '.join(week_details) if week_details else "No weeks available"}

STRICT INSTRUCTIONS - READ CAREFULLY:
1. Use the curriculum content above AND web search results to identify strands, substrands, content standards, and indicators
2. Map these elements to the available teaching sessions from WeeklySessions
3. You MUST ONLY use the weeks and sessions provided in the WeeklySessions data
4. ALL curriculum elements (strands, substrands, content standards, indicators) MUST be for the specified Class Name and Subject only
5. CRITICAL FORMAT REQUIREMENT: Week numbers MUST be provided as NUMERIC VALUES ONLY (e.g., [1, 2, 3])
6. CRITICAL FORMAT REQUIREMENT: You MUST return FLAT STRUCTURES for all curriculum elements
7. For strand_data: use strand_name (NOT name)
8. For substrand_data: use substrand_name (NOT name)
9. For content_standard_data: use content_standard_text (NOT name)
10. For indicator_data: use indicator_text (NOT name)

CONTENT STANDARD AND INDICATOR ASSIGNMENT RULES:
1. EACH content standard MUST be assigned to at least one session from its parent substrand
2. EACH indicator MUST be assigned to at least one session from its parent content standard's sessions
3. A session CAN have at most TWO indicators assigned to it
4. When assigning sessions, ensure even distribution of indicators across available sessions

EXPECTED OUTPUT FORMAT:
{example_json}

Return ONLY the JSON, nothing else. DO NOT wrap the output in markdown code blocks.
"""
    
    return prompt



async def process_curriculum_task(
    ctx: dict,
    teacher_id: str,
    gcs_file_name: str,
    subject: str,
    class_name: str,
    session_data: Dict = None,
    knowledge_id: int = None,
    education_system: str = None,
    education_level: str = None
):
    """
    Main background task for curriculum processing.
    
    This combines:
    1. Text extraction and chunking (if not already embedded)
    2. Embedding generation (if not already embedded)
    3. Retrieval of relevant syllabus chunks (with semester context)
    4. AI prompt building and processing (with web search)
    5. Storing results in Strand/Substrand/ContentStandard/Indicator tables
    
    Args:
        ctx: ARQ context
        teacher_id: Teacher UUID string
        gcs_file_name: GCS path to the curriculum file
        subject: Subject name
        class_name: Class name
        session_data: Session data including academic calendar and class sessions
        knowledge_id: ID of the KnowledgeMetadata record (optional)
        education_system: Education system (e.g., "Ghana", "Cambridge")
        education_level: Education level (e.g., "Primary", "JHS")
    
    Returns:
        Dict with processing results
    """
    logger.info("=" * 60)
    logger.info(f"🚀 [CURRI] Starting curriculum processing for teacher {teacher_id}")
    logger.info(f"📚 Subject: {subject}, Class: {class_name}")
    logger.info(f"🏫 Education System: {education_system}, Level: {education_level}")
    logger.info(f"📁 GCS File: {gcs_file_name}")
    logger.info("=" * 60)
    
    # Get file name from GCS path for logging
    file_name = os.path.basename(gcs_file_name) if gcs_file_name else "curriculum_file"
    
    # Detailed logging to file
    log_section(f"CURRICULUM PROCESSING STARTED - {datetime.now().isoformat()}")
    detail_logger.info(f"Teacher ID: {teacher_id}")
    detail_logger.info(f"Subject: {subject}")
    detail_logger.info(f"Class: {class_name}")
    detail_logger.info(f"Education System: {education_system}")
    detail_logger.info(f"Education Level: {education_level}")
    detail_logger.info(f"GCS File: {gcs_file_name}")
    detail_logger.info(f"File Name: {file_name}")
    detail_logger.info(f"Knowledge ID: {knowledge_id}")
    
    # Log session data structure
    log_section("INPUT: SESSION DATA")
    if session_data:
        detail_logger.info(f"Session Data Structure:")
        detail_logger.info(json.dumps(session_data, indent=2, default=str))
        detail_logger.info(f"Semester Start: {session_data.get('semester_start_date', 'Not provided')}")
        detail_logger.info(f"Semester End: {session_data.get('semester_end_date', 'Not provided')}")
        weekly_sessions = session_data.get('weekly_sessions', {})
        detail_logger.info(f"Number of Weeks: {len(weekly_sessions)}")
        for week_key, week_data in weekly_sessions.items():
            detail_logger.info(f"  {week_key}: {len(week_data.get('sessions', []))} sessions")
    else:
        detail_logger.info("⚠️ No session data provided")
    
    try:
        # Send initial status (same format as semplan)
        await publish_ws_message(teacher_id, {
            "type": "semplan_processing",  # Use same type as semplan for frontend compatibility
            "status": "started",
            "message": f"Starting curriculum-based semester plan generation for {subject} - {class_name}",
            "file_name": file_name,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "source": "curriculum"  # Indicate this is from curriculum processing
        })
        
        # Step 1: Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Step 1.5: Fetch semester_name and term from AcademicCalendar
            semester_name = None
            term = None
            
            log_section("FETCHING SEMESTER METADATA from AcademicCalendar")
            try:
                from app.models.model import AcademicCalendar
                calendar_result = await db.execute(
                    select(AcademicCalendar).where(AcademicCalendar.teacher_id == UUID(teacher_id))
                )  
                calendar = calendar_result.scalar_one_or_none()
                
                if calendar:
                    semester_name = calendar.semester_name if hasattr(calendar, 'semester_name') else None
                    term = calendar.term if hasattr(calendar, 'term') else None
                    
                    logger.info(f"📅 Retrieved from AcademicCalendar: Semester={semester_name}, Term={term}")
                    detail_logger.info(f"Semester Name: {semester_name}")
                    detail_logger.info(f"Term: {term}")
                else:
                    logger.warning(f"⚠️ No AcademicCalendar found for teacher {teacher_id}")
                    detail_logger.warning("No AcademicCalendar record found")
            except Exception as cal_err:
                logger.error(f"❌ Error fetching AcademicCalendar: {cal_err}")
                detail_logger.error(f"Error fetching semester metadata: {cal_err}")
            
            # Log all metadata for AI processing
            log_section("METADATA FOR AI & RETRIEVAL")
            detail_logger.info(f"Class Name: {class_name}")
            detail_logger.info(f"Subject: {subject}")
            detail_logger.info(f"Education System: {education_system}")
            detail_logger.info(f"Education Level: {education_level}")
            detail_logger.info(f"Semester Name: {semester_name}")
            detail_logger.info(f"Term: {term}")
            
            # Step 2: Check if file needs embedding
            needs_embedding = True
            if knowledge_id:
                result = await db.execute(
                    select(KnowledgeMetadata).where(KnowledgeMetadata.id == knowledge_id)
                )
                knowledge_record = result.scalar_one_or_none()
                if knowledge_record and knowledge_record.is_embedded:
                    needs_embedding = False
                    logger.info(f"✅ File already embedded, skipping extraction and embedding")
            
            # Step 3: If file needs embedding, extract and embed
            if needs_embedding:
                await publish_ws_message(teacher_id, {
                    "type": "semplan_processing",
                    "status": "extracting",
                    "message": "Extracting text from curriculum file...",
                    "file_name": file_name,
                    "teacher_id": teacher_id,
                    "subject": subject,
                    "class_name": class_name
                })
                
                # Download file from GCS and process
                if GCS_AVAILABLE and TEXT_EXTRACTION_AVAILABLE:
                    local_file_path = await download_file_from_gcs(gcs_file_name)
                    
                    try:
                        # Extract text (synchronous function)
                        extracted_text = extract_text_from_pdf_pymupdf(local_file_path)
                        
                        # Chunk the text
                        if chunk_text_with_langchain:
                            chunks = chunk_text_with_langchain(extracted_text, max_tokens=700)
                        else:
                            # Basic fallback chunking
                            chunk_size = 2000
                            chunks = [extracted_text[i:i+chunk_size] for i in range(0, len(extracted_text), chunk_size)]
                        
                        logger.info(f"📄 Extracted {len(extracted_text)} characters, {len(chunks)} chunks")
                        
                        # Generate embeddings only if available
                        if EMBEDDING_AVAILABLE and generate_embeddings_with_gemini:
                            await publish_ws_message(teacher_id, {
                                "type": "semplan_processing",
                                "status": "embedding",
                                "message": f"Generating embeddings for {len(chunks)} chunks...",
                                "file_name": file_name,
                                "teacher_id": teacher_id,
                                "subject": subject,
                                "class_name": class_name
                            })
                            
                            embeddings = generate_embeddings_with_gemini(chunks)
                            
                            # Store embeddings
                            if knowledge_id and embeddings:
                                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                                    if embedding is not None:
                                        embedding_record = KnowledgeEmbedding(
                                            knowledge_id=knowledge_id,
                                            chunk_text=chunk,
                                            embedding=embedding,
                                            chunk_order=i,
                                            subject=subject,
                                            pillar="curriculum"
                                        )
                                        db.add(embedding_record)
                                
                                await db.commit()
                                
                                # Update knowledge metadata
                                knowledge_record.is_embedded = True
                                knowledge_record.chunk_count = len(chunks)
                                await db.commit()
                                
                                logger.info(f"✅ Stored {len(embeddings)} embeddings")
                        else:
                            logger.warning("⚠️ Embedding not available, skipping embedding generation")
                    finally:
                        # Clean up temp file
                        if os.path.exists(local_file_path):
                            os.remove(local_file_path)
                            logger.info(f"🗑️ Cleaned up temp file: {local_file_path}")
                else:
                    logger.warning("⚠️ GCS or text extraction not available, skipping extraction")
            
            # Step 4: Perform retrieval to get relevant syllabus content
            log_section("STEP: RETRIEVAL - Searching for Syllabus Content")
            
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "retrieving",
                "message": "Retrieving relevant syllabus content...",
                "file_name": file_name,
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            
            # Build retrieval query - look for syllabus content with semester context
            # Include semester_name and term to help find relevant content for the specific semester
            query_parts = ["strand", "substrand", "content standard", "indicator", "syllabus", subject, class_name]
            if semester_name:
                query_parts.append(semester_name)
            if term:
                query_parts.append(term)
            
            retrieval_query = " ".join(query_parts)
            
            # Log retrieval parameters
            detail_logger.info("Retrieval Query Parameters:")
            detail_logger.info(f"  Query: {retrieval_query}")
            detail_logger.info(f"  Subject Filter: {subject}")
            detail_logger.info(f"  Pillar Filter: syllabus")
            detail_logger.info(f"  Class Level Filter: {class_name}")
            detail_logger.info(f"  Semester Context: {semester_name}")
            detail_logger.info(f"  Term Context: {term}")
            detail_logger.info(f"  Limit: 4")
            detail_logger.info(f"  Min Similarity: 0.3")
            detail_logger.info(f"  Use Hybrid Search: True")
            detail_logger.info(f"  Keyword Weight: 0.3")
            
            retrieval_results = await perform_retrieval(
                db,
                query=retrieval_query,
                subject=subject,
                pillar="syllabus",  # Search in syllabus pillar
                class_level=class_name,
                limit=4,  # Top 4 chunks
                min_similarity=0.3,
                use_hybrid_search=True,
                keyword_weight=0.3
            )
            
            logger.info(f"🔍 Retrieved {len(retrieval_results)} chunks from syllabus")
            detail_logger.info(f"Retrieved {len(retrieval_results)} chunks from syllabus pillar")
            
            if not retrieval_results:
                # Fallback: search in curriculum pillar if syllabus not found
                logger.info("⚠️ No syllabus results, trying curriculum pillar...")
                detail_logger.info("⚠️ No results from syllabus, attempting fallback to curriculum pillar")
                detail_logger.info("Fallback Retrieval Parameters:")
                detail_logger.info(f"  Pillar Filter: curriculum (changed from syllabus)")
                
                retrieval_results = await perform_retrieval(
                    db,
                    query=retrieval_query,
                    subject=subject,
                    pillar="curriculum",
                    class_level=class_name,
                    limit=4,
                    min_similarity=0.3,
                    use_hybrid_search=True,
                    keyword_weight=0.3
                )
                logger.info(f"🔍 Retrieved {len(retrieval_results)} chunks from curriculum")
                detail_logger.info(f"Retrieved {len(retrieval_results)} chunks from curriculum pillar")
            
            # Log detailed retrieval results
            log_section("RETRIEVAL RESULTS")
            if retrieval_results:
                detail_logger.info(f"Total Chunks Retrieved: {len(retrieval_results)}")
                for i, chunk in enumerate(retrieval_results):
                    detail_logger.info(f"\n--- Chunk {i+1} ---")
                    detail_logger.info(f"Similarity Score: {chunk.get('similarity', 0):.4f}")
                    detail_logger.info(f"Combined Score: {chunk.get('combined_score', 0):.4f}")
                    detail_logger.info(f"Keyword Score: {chunk.get('keyword_score', 0):.4f}")
                    detail_logger.info(f"Knowledge ID: {chunk.get('knowledge_id', 'N/A')}")
                    detail_logger.info(f"Subject: {chunk.get('subject', 'N/A')}")
                    detail_logger.info(f"Pillar: {chunk.get('pillar', 'N/A')}")
                    detail_logger.info(f"Chunk Order: {chunk.get('chunk_order', 'N/A')}")
                    detail_logger.info(f"Chunk Text (first 500 chars):")
                    chunk_text = chunk.get('chunk_text', '')
                    detail_logger.info(chunk_text[:500] + ("..." if len(chunk_text) > 500 else ""))
                detail_logger.info(f"\nFull Retrieval Results (JSON):")
                detail_logger.info(json.dumps(retrieval_results, indent=2, default=str))
            else:
                detail_logger.info("⚠️ No chunks retrieved")
            
            if not retrieval_results:
                error_msg = f"No relevant curriculum content found for {subject} - {class_name}"
                logger.error(f"❌ {error_msg}")
                await publish_ws_message(teacher_id, {
                    "type": "semplan_processing",
                    "status": "error",
                    "message": error_msg,
                    "file_name": file_name,
                    "teacher_id": teacher_id,
                    "subject": subject,
                    "class_name": class_name
                })
                return {"status": "error", "message": error_msg}
            
            
            # Step 5: Build prompt and send to AI
            log_section("STEP: AI PROCESSING - Building Prompt and Sending to AI")
            
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "processing",
                "message": "🤖 Sending data to AI for semester plan processing...",
                "file_name": file_name,
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            # Log session data  being sent to AI (like semplan does)
            if session_data:
                weekly_sessions = session_data.get('weekly_sessions', {})
                logger.info(f"📅 SESSION DATA BEING SENT TO AI:")
                logger.info(f"   Semester Start: {session_data.get('semester_start_date', 'Not provided')}")
                logger.info(f"   Semester End: {session_data.get('semester_end_date', 'Not provided')}")
                logger.info(f"   Number of Weeks: {len(weekly_sessions)}")
                for week_key, week_data in weekly_sessions.items():
                    logger.info(f"     {week_key}: {len(week_data.get('sessions', []))} sessions")
            else:
                logger.warning("⚠️ NO SESSION DATA PROVIDED TO AI")
            
            # Build the prompt with all metadata for web search
            prompt = build_curriculum_prompt(
                retrieval_chunks=retrieval_results,
                session_data=session_data,
                class_name=class_name,
                subject=subject,
                education_system=education_system,
                education_level=education_level,
                semester_name=semester_name,
                term=term
            )
            
            # Log the complete prompt being sent to AI
            detail_logger.info("AI Prompt Built:")
            detail_logger.info(f"Prompt Length: {len(prompt)} characters")
            detail_logger.info(f"Prompt Content:\n{prompt}")
            
            # Log web search context
            log_section("WEB SEARCH CONFIGURATION")
            detail_logger.info("Web Search Enabled: YES (via prompt instructions)")
            detail_logger.info(f"Search Context - Education System: {education_system}")
            detail_logger.info(f"Search Context - Education Level: {education_level}")
            detail_logger.info(f"Search Context - Semester: {semester_name}")
            detail_logger.info(f"Search Context - Term: {term}")
            detail_logger.info(f"Search Context - Subject: {subject}")
            detail_logger.info(f"Search Context - Class: {class_name}")
            
            # Send to AI
            # NOTE: We pass the prompt as 'extracted_text' since we've built our own prompt
            # The AI function will use this along with potential web search
            detail_logger.info("Sending prompt to AI with web search capability...")
            from app.core.config import settings
            ai_response = await send_semester_plan_to_ai(
                prompt,  # Our custom prompt with web search instructions
                f"curriculum://retrieval/{subject}/{class_name}",  # Dummy path since we use retrieval
                settings.API_KEY,
                session_data,
                class_name,
                subject
            )
            
            # Log AI response
            log_section("AI RESPONSE")
            if not ai_response or "error" in ai_response:
                error_msg = ai_response.get("error", "AI processing failed - no response received") if ai_response else "AI processing failed - no response received"
                logger.error(f"❌ {error_msg}")
                detail_logger.error(f"AI Error: {error_msg}")
                detail_logger.error(f"Full AI Response: {json.dumps(ai_response, indent=2, default=str) if ai_response else 'None'}")
                
                await publish_ws_message(teacher_id, {
                    "type": "semplan_processing",
                    "status": "error",
                    "message": f"AI processing failed: {error_msg}",
                    "file_name": file_name,
                    "teacher_id": teacher_id,
                    "subject": subject,
                    "class_name": class_name
                })
                return {"status": "error", "message": error_msg}
            
            
            logger.info(f"🎉 AI processing successful")
            logger.info(f"🤖 COMPLETE AI RESPONSE: {json.dumps(ai_response, indent=2, default=str)}")
            
            # Log successful AI response in detail
            detail_logger.info("✅ AI Processing Successful")
            detail_logger.info(f"AI Response Length: {len(str(ai_response))} characters")
            detail_logger.info("AI Response Structure:")
            detail_logger.info(f"  - Strand Data: {len(ai_response.get('strand_data', []))} items")
            detail_logger.info(f"  - Substrand Data: {len(ai_response.get('substrand_data', []))} items")
            detail_logger.info(f"  - Content Standard Data: {len(ai_response.get('content_standard_data', []))} items")
            detail_logger.info(f"  - Indicator Data: {len(ai_response.get('indicator_data', []))} items")
            detail_logger.info("\nComplete AI Response (JSON):")
            detail_logger.info(json.dumps(ai_response, indent=2, default=str))
            
            # Step 6: Store AI response in tables
            log_section("STEP: DATABASE STORAGE - Storing Semester Plan Data")
            
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "storing",
                "message": "Storing semester plan data in database...",
                "file_name": file_name,
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            detail_logger.info("Starting database storage...")
            
            # RETRY CONFIGURATION
            max_db_retries = 3
            max_outline_retries = 3
            
            # Storage with retry logic
            db_attempt = 0
            db_retry_delay = 5  # Start with 5 seconds
            storage_success = False
            
            while db_attempt < max_db_retries and not storage_success:
                try:
                    if db_attempt > 0:
                        detail_logger.info(f"🔄 [DB RETRY] Attempt {db_attempt + 1}/{max_db_retries} after {db_retry_delay}s wait...")
                        await asyncio.sleep(db_retry_delay)
                        db_retry_delay *= 2  # Exponential backoff
                    
                    await store_ai_response_in_tables(teacher_id, class_name, subject, ai_response, db)
                    detail_logger.info("✅ Database storage completed successfully")
                    storage_success = True
                    
                except Exception as db_error:
                    db_attempt += 1
                    detail_logger.error(f"❌ DB Storage error (attempt {db_attempt}): {db_error}")
                    
                    if db_attempt < max_db_retries:
                        detail_logger.info(f"   Will retry in {db_retry_delay}s...")
                        await db.rollback()
                    else:
                        detail_logger.error(f"❌ DB Storage failed after {max_db_retries} attempts")
                        await db.rollback()
                        raise Exception(f"Database storage failed after {max_db_retries} attempts: {db_error}")
            
            logger.info("✅ Semester plan data stored successfully")
            
            # Generate outline INLINE with retry (same task, same transaction)
            log_section("INLINE OUTLINE GENERATION")
            detail_logger.info("Plan storage successful - generating course outline...")
            
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "generating_outline",
                "message": f"Generating course outline for {subject} - {class_name}...",
                "file_name": file_name,
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            from app.outline_back.inline_outline import generate_outline_inline
            
            # Outline generation with retry logic
            outline_attempt = 0
            outline_retry_delay = 10  # Start with 10 seconds
            outline_success = False
            outline_result = None
            
            while outline_attempt < max_outline_retries and not outline_success:
                try:
                    if outline_attempt > 0:
                        detail_logger.info(f"🔄 [OUTLINE RETRY] Attempt {outline_attempt + 1}/{max_outline_retries} after {outline_retry_delay}s wait...")
                        await asyncio.sleep(outline_retry_delay)
                        outline_retry_delay *= 2  # Exponential backoff
                    
                    outline_result = await generate_outline_inline(
                        db=db,
                        teacher_id=teacher_id,
                        subject=subject,
                        class_name=class_name,
                        education_system=education_system,
                        academic_level=education_level,
                        semester_name=semester_name if 'semester_name' in locals() else None,
                        term=term if 'term' in locals() else None
                    )
                    
                    detail_logger.info(f"✅ Outline generated: {outline_result}")
                    logger.info(f"📘 Outline generated for {subject} - {class_name}")
                    outline_success = True
                    
                except Exception as outline_error:
                    outline_attempt += 1
                    detail_logger.error(f"❌ Outline generation error (attempt {outline_attempt}): {outline_error}")
                    
                    if outline_attempt < max_outline_retries:
                        detail_logger.info(f"   Will retry in {outline_retry_delay}s...")
                    else:
                        detail_logger.error(f"❌ Outline generation failed after {max_outline_retries} attempts")
                        await db.rollback()  # Rollback plan if outline fails
                        raise Exception(f"Outline generation failed after {max_outline_retries} attempts: {outline_error}")
            
            # Commit both plan AND outline together (atomic operation)
            await db.commit()
            detail_logger.info("✅ Plan and outline committed to database")
            
        finally:
            await db_gen.aclose()
        
        # Send success notification - only if BOTH plan AND outline succeeded
        log_section("CURRICULUM PROCESSING + OUTLINE COMPLETED")
        detail_logger.info(f"Teacher ID: {teacher_id}")
        detail_logger.info(f"Subject: {subject}")
        detail_logger.info(f"Class: {class_name}")
        detail_logger.info(f"Processing Time: {datetime.now().isoformat()}")
        detail_logger.info("Status: SUCCESS")
        log_separator()
        
        await publish_ws_message(teacher_id, {
            "type": "semplan_processing",
            "status": "completed",
            "message": f"Plan and outline created successfully for {subject} - {class_name}",
            "file_name": file_name,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "ai_processed": True,
            "source": "curriculum",
            "outline_generated": True
        })
        
        await save_notification(
            teacher_id=teacher_id,
            title="Plan & Outline Created",
            message=f"Plan and outline for {subject} - {class_name} are ready",
            type_="success"
        )
        
        return {
            "status": "success",
            "message": f"Plan and outline created for {subject} - {class_name}",
            "subject": subject,
            "class_name": class_name,
            "outline_generated": True
        }
        
    except Exception as e:
        error_msg = f"Curriculum processing failed: {str(e)}"
        error_trace = traceback.format_exc()
        
        logger.error(f"❌ {error_msg}")
        logger.error(error_trace)
        
        # Detailed error logging
        log_section("CURRICULUM PROCESSING FAILED - ERROR")
        detail_logger.error(f"Error Message: {error_msg}")
        detail_logger.error(f"Error Type: {type(e).__name__}")
        detail_logger.error(f"Teacher ID: {teacher_id}")
        detail_logger.error(f"Subject: {subject}")
        detail_logger.error(f"Class: {class_name}")
        detail_logger.error(f"GCS File: {gcs_file_name}")
        detail_logger.error(f"Error Time: {datetime.now().isoformat()}")
        detail_logger.error(f"\nFull Traceback:\n{error_trace}")
        log_separator()
        
        await publish_ws_message(teacher_id, {
            "type": "semplan_processing",
            "status": "error",
            "message": error_msg,
            "file_name": file_name,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name
        })
        
        await save_notification(
            teacher_id=teacher_id,
            title="Curriculum Processing Failed",
            message=error_msg,
            type_="error"
        )
        
        raise RuntimeError(error_msg)


async def store_ai_response_in_tables(
    teacher_id: str,
    class_name: str,
    subject: str,
    ai_response: dict,
    db: AsyncSession
):
    """
    Store the AI response data directly in the Strand, Substrand, ContentStandard, and Indicator tables.
    
    Args:
        teacher_id: The UUID of the teacher
        class_name: The class name
        subject: The subject name
        ai_response: The AI response containing strand_data, substrand_data, content_standard_data, and indicator_data
        db: Database session
    """
    logger.info(f"[CURRI] Storing AI response in tables for teacher {teacher_id}")
    
    # Delete existing data for this teacher, class, and subject
    await db.execute(
        delete(Indicator).where(
            and_(
                Indicator.teacher_id == UUID(teacher_id),
                Indicator.class_name == class_name,
                Indicator.subject == subject
            )
        )
    )
    await db.execute(
        delete(ContentStandard).where(
            and_(
                ContentStandard.teacher_id == UUID(teacher_id),
                ContentStandard.class_name == class_name,
                ContentStandard.subject == subject
            )
        )
    )
    await db.execute(
        delete(Substrand).where(
            and_(
                Substrand.teacher_id == UUID(teacher_id),
                Substrand.class_name == class_name,
                Substrand.subject == subject
            )
        )
    )
    await db.execute(
        delete(Strand).where(
            and_(
                Strand.teacher_id == UUID(teacher_id),
                Strand.class_name == class_name,
                Strand.subject == subject
            )
        )
    )
    await db.flush()  # Flush only, don't commit - caller handles commit after outline
    logger.info(f"[CURRI] Deleted existing data for teacher {teacher_id}, class {class_name}, subject {subject}")
    
    # Process and store strand data
    strand_data_list = ai_response.get("strand_data", [])
    created_strands = {}  # strand_name -> {week_number -> strand_object}
    
    for strand_data in strand_data_list:
        strand_name = strand_data.get("strand_name", strand_data.get("name", "Unknown"))
        weeks = strand_data.get("weeks", [])
        session_ids = strand_data.get("session_ids", [])
        session_details = strand_data.get("session_details", strand_data.get("sessions", []))
        
        if strand_name not in created_strands:
            created_strands[strand_name] = {}
        
        for week in weeks:
            week_num = int(week) if isinstance(week, (int, str)) else 1
            if week_num not in created_strands[strand_name]:
                strand = Strand(
                    strand_name=strand_name,
                    subject=subject,
                    class_name=class_name,
                    teacher_id=UUID(teacher_id),
                    week_number=week_num,
                    session_ids=session_ids,
                    session_details=session_details
                )
                db.add(strand)
                created_strands[strand_name][week_num] = strand
    
    await db.flush()  # Flush only, don't commit - caller handles commit after outline
    logger.info(f"[CURRI] Created {len(created_strands)} strands")
    
    # Refresh strands to get IDs
    for strand_name in created_strands:
        for week_num in created_strands[strand_name]:
            await db.refresh(created_strands[strand_name][week_num])
    
    # Process substrand data
    substrand_data_list = ai_response.get("substrand_data", [])
    created_substrands = {}  # substrand_name -> substrand_object
    
    for substrand_data in substrand_data_list:
        strand_name = substrand_data.get("strand_name", "Unknown")
        substrand_name = substrand_data.get("substrand_name", substrand_data.get("name", "Unknown"))
        weeks = substrand_data.get("weeks", [])
        session_ids = substrand_data.get("session_ids", [])
        session_details = substrand_data.get("session_details", substrand_data.get("sessions", []))
        
        # Find parent strand
        strand_id = None
        if strand_name in created_strands and created_strands[strand_name]:
            first_week = list(created_strands[strand_name].keys())[0]
            strand_id = created_strands[strand_name][first_week].id
        
        if strand_id and substrand_name not in created_substrands:
            substrand = Substrand(
                substrand_name=substrand_name,
                strand_id=strand_id,
                subject=subject,
                class_name=class_name,
                teacher_id=UUID(teacher_id),
                week_numbers=[int(w) if isinstance(w, (int, str)) else 1 for w in weeks],
                session_ids=session_ids,
                session_details=session_details
            )
            db.add(substrand)
            created_substrands[substrand_name] = substrand
    
    await db.flush()  # Flush only, don't commit - caller handles commit after outline
    logger.info(f"[CURRI] Created {len(created_substrands)} substrands")
    
    # Refresh substrands to get IDs
    for substrand_name in created_substrands:
        await db.refresh(created_substrands[substrand_name])
    
    # Process content standard data
    content_standard_data_list = ai_response.get("content_standard_data", [])
    created_content_standards = {}  # content_standard_code -> content_standard_object
    
    for cs_data in content_standard_data_list:
        substrand_name = cs_data.get("substrand_name", "Unknown")
        cs_code = cs_data.get("content_standard_code", "")
        cs_text = cs_data.get("content_standard_text", cs_data.get("content_standard", ""))
        session_ids = cs_data.get("session_ids", [])
        session_details = cs_data.get("session_details", cs_data.get("sessions", []))
        
        # Find parent substrand
        substrand_id = None
        if substrand_name in created_substrands:
            substrand_id = created_substrands[substrand_name].id
        
        if substrand_id and cs_code not in created_content_standards:
            content_standard = ContentStandard(
                content_standard_code=cs_code,
                content_standard=cs_text,
                substrand_id=substrand_id,
                subject=subject,
                class_name=class_name,
                teacher_id=UUID(teacher_id),
                session_ids=session_ids,
                session_details=session_details
            )
            db.add(content_standard)
            created_content_standards[cs_code] = content_standard
    
    await db.flush()  # Flush only, don't commit - caller handles commit after outline
    logger.info(f"[CURRI] Created {len(created_content_standards)} content standards")
    
    # Refresh content standards to get IDs
    for cs_code in created_content_standards:
        await db.refresh(created_content_standards[cs_code])
    
    # Process indicator data
    indicator_data_list = ai_response.get("indicator_data", [])
    created_indicators = 0
    
    for ind_data in indicator_data_list:
        cs_code = ind_data.get("content_standard_code", "")
        ind_code = ind_data.get("indicator_code", "")
        ind_text = ind_data.get("indicator_text", ind_data.get("indicator", ""))
        session_ids = ind_data.get("session_ids", [])
        session_details = ind_data.get("session_details", ind_data.get("sessions", []))
        
        # Find parent content standard
        content_standard_id = None
        if cs_code in created_content_standards:
            content_standard_id = created_content_standards[cs_code].id
        
        if content_standard_id:
            indicator = Indicator(
                indicator_code=ind_code,
                indicator_text=ind_text,
                content_standard_id=content_standard_id,
                subject=subject,
                class_name=class_name,
                teacher_id=UUID(teacher_id),
                session_ids=session_ids,
                session_details=session_details
            )
            db.add(indicator)
            created_indicators += 1
    
    await db.flush()  # Flush only, don't commit - caller handles commit after outline
    logger.info(f"[CURRI] Created {created_indicators} indicators")
    
    logger.info(f"[CURRI] ✅ Successfully stored AI response in tables (NOT COMMITTED YET - awaiting outline)")
