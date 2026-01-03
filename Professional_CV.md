# Professional CV

## Personal Profile

Experienced backend developer with expertise in building scalable, AI-powered educational platforms using modern technologies. Demonstrated proficiency in asynchronous task processing, real-time communication systems, and Retrieval-Augmented Generation (RAG) implementations. Strong background in database design, cloud infrastructure, and AI integration with Google's Gemini API.

## Technical Skills

### Core Technologies
- **Languages**: Python (3.13), SQL, JavaScript
- **Frameworks**: FastAPI, SQLAlchemy, ARQ, Celery
- **Databases**: PostgreSQL with pgvector extension, Redis
- **Cloud Services**: Google Cloud Platform (GCS, Vertex AI, Gemini API)
- **Containerization**: Docker
- **AI/ML**: Google Gemini, Vertex AI, Unstructured.io, LangChain
- **Real-time Communication**: WebSockets, Redis Pub/Sub
- **Asynchronous Processing**: ARQ (Async Redis Queue), Background Workers

### Specialized Skills
- **RAG Implementation**: Document processing pipelines, embedding generation, vector storage
- **Background Task Management**: Distributed task queues, worker management, retry mechanisms
- **Authentication Systems**: JWT-based authentication, role-based access control
- **Database Design**: ORM modeling, relationship mapping, performance optimization
- **Real-time Features**: WebSocket communication, event broadcasting
- **AI Integration**: Google Gemini API for content generation, holiday fetching, academic planning

## Professional Experience

### Senior Backend Developer | Educational Technology Platform
*Self-directed project demonstrating full-stack capabilities*

#### Docker & Infrastructure
- Designed and implemented containerized development environment using Docker with PostgreSQL and pgvector
- Configured Docker Compose for streamlined local development with proper port mappings and volume management
- Implemented environment-specific configurations using docker-compose.yml

#### Database Architecture
- Developed comprehensive PostgreSQL schema using SQLModel and SQLAlchemy
- Implemented vector storage capabilities with pgvector for RAG embeddings
- Designed complex educational domain models including Strands, Substrands, Content Standards, and Indicators
- Created robust relationship mappings between academic entities with proper foreign key constraints
- Implemented JSONB fields for flexible data storage of session details and metadata

#### Redis & Background Processing
- Integrated Redis for WebSocket message brokering and background task management
- Implemented Redis Pub/Sub system for real-time communication between services
- Developed ARQ (Async Redis Queue) worker system for distributed task processing
- Created background workers for schedule generation, academic calendar processing, and timetable management
- Configured retry mechanisms, concurrency controls, and job timeout handling

#### RAG Implementation
- Built complete document processing pipeline using Unstructured.io for text extraction
- Implemented intelligent chunking strategies with LangChain's RecursiveCharacterTextSplitter
- Integrated Google Vertex AI Gemini embedding model for vector generation (1536-dimension embeddings)
- Designed KnowledgeMetadata and KnowledgeEmbedding models for storing document information and vectors
- Created batch processing system for efficient embedding generation with rate limit handling
- Implemented retry mechanisms and credential refresh systems for reliable AI service integration

#### AI Integrations
- Integrated Google Gemini API for academic content generation and analysis
- Developed AI processing pipelines for academic calendars, timetables, and semester plans
- Created structured prompts for consistent AI output formatting
- Implemented browser search capabilities with Google AI for up-to-date holiday information
- Built robust error handling and JSON parsing for AI responses
- Developed retry mechanisms and fallback strategies for AI service calls

#### Real-time Communication
- Implemented WebSocket infrastructure for teacher-student communication
- Created Redis-based message broadcasting system for real-time notifications
- Developed heartbeat mechanisms for connection health monitoring
- Built student logging system with real-time message processing
- Designed channel-based messaging for targeted communication

#### Authentication & Security
- Implemented JWT-based authentication system with role-based access control
- Developed secure password handling with hashing and salting
- Created student enrollment and teacher profile management systems
- Built assessment security features with strict mode and access control rules
- Implemented session management and token refresh mechanisms

#### API Development
- Built RESTful API using FastAPI with automatic OpenAPI documentation
- Implemented CORS policies for secure cross-origin requests
- Created comprehensive routing system with proper endpoint organization
- Developed request/response validation using Pydantic models
- Built middleware for request logging and error handling

#### Background Task Systems
- Designed ARQ worker configuration with proper startup/shutdown handling
- Implemented atomic database operations for data consistency
- Created task retry mechanisms with exponential backoff
- Developed progress reporting through WebSocket notifications
- Built holiday fetching system with timeout protection and fallback handling

## Projects

### Educational Management System
A comprehensive platform for academic planning, scheduling, and content management with AI assistance.

**Key Achievements:**
- Developed asynchronous schedule generation system processing academic calendars and timetables
- Created RAG pipeline processing educational documents and storing embeddings for semantic search
- Implemented real-time WebSocket communication for instant notifications and updates
- Built AI-powered academic content generation using Google Gemini API
- Designed scalable database schema supporting complex educational relationships
- Created robust background task system handling document processing and AI operations

### Document Processing & AI Analysis Pipeline
System for converting educational documents into structured, searchable knowledge.

**Key Features:**
- Text extraction from PDF, DOCX, and other document formats using Unstructured.io
- Intelligent chunking with semantic awareness for optimal retrieval
- Vector embedding generation using Google Vertex AI
- Storage and retrieval of educational content with metadata management
- Batch processing with rate limit handling and error recovery

## Education
- Self-directed learning in AI, distributed systems, and educational technology
- Continuous professional development through hands-on project implementation

## Certifications
- Google Cloud Platform (Conceptual understanding through implementation)
- AI/ML Frameworks (Practical experience with Vertex AI, Gemini API)

## Additional Skills
- Git version control and collaborative development
- System design and architecture planning
- Performance optimization and debugging
- Technical documentation and code maintainability
- Testing and quality assurance practices