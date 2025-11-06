# ChemBot - Technical Implementation Guide

**Complete Technical Deep Dive & Developer Reference**

This document provides exhaustive technical details about ChemBot's architecture, implementation, database schema, API specifications, and operational procedures.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack Deep Dive](#technology-stack-deep-dive)
3. [Database Schema & Operations](#database-schema--operations)
4. [API Implementation Details](#api-implementation-details)
5. [RAG Pipeline Architecture](#rag-pipeline-architecture)
6. [Caching Strategy](#caching-strategy)
7. [Authentication & Security](#authentication--security)
8. [Frontend Architecture](#frontend-architecture)
9. [Configuration Management](#configuration-management)
10. [Deployment & Operations](#deployment--operations)
11. [Testing Strategy](#testing-strategy)
12. [Performance Optimization](#performance-optimization)
13. [Troubleshooting & Debugging](#troubleshooting--debugging)

---

## Architecture Overview

### System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                          │
│  React 18.3 + TypeScript + Tailwind CSS + React Router       │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS/REST
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                        │
│  FastAPI 0.109 (Async) + JWT Middleware + CORS              │
└────────┬────────────┬──────────────┬────────────────┬────────┘
         │            │              │                │
         ▼            ▼              ▼                ▼
    ┌────────┐  ┌─────────┐   ┌──────────┐    ┌───────────┐
    │ Auth   │  │ Content │   │ ChatBot  │    │ Analytics │
    │ Routes │  │ Routes  │   │  Engine  │    │  Service  │
    └────────┘  └─────────┘   └─────┬────┘    └───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
            ┌──────────────┐  ┌─────────────┐  ┌──────────┐
            │ Query Engine │  │   Cache     │  │  Query   │
            │     (RAG)    │  │  Manager    │  │ Classifier│
            └──────┬───────┘  └──────┬──────┘  └──────────┘
                   │                 │
        ┌──────────┼─────────────────┤
        │          │                 │
        ▼          ▼                 ▼
┌────────────┐ ┌─────────┐    ┌──────────┐
│  Pinecone  │ │ OpenAI  │    │  Redis   │
│  (Vectors) │ │  (LLM)  │    │ (Cache)  │
└────────────┘ └─────────┘    └──────────┘
        │
        ▼
┌──────────────────────────────────────┐
│          MongoDB 7.0 (Data)          │
│  Collections: users, content,        │
│  questions, analytics                │
└──────────────────────────────────────┘
```

### Request Flow Diagram

```
User Question → Frontend
    ↓
FastAPI Endpoint (/api/content/{id}/question)
    ↓
ChatbotEngine.ask_question() / ask_question_stream()
    ↓
┌─→ Cache Check (Redis)
│       ↓ MISS
│   Query Classifier (LLM)
│       ↓
│   Conversation Manager (Load History)
│       ↓
│   Query Engine (RAG)
│       ├→ Vector Search (Pinecone)
│       ├→ Retrieve Chunks
│       ├→ Generate Answer (LLM)
│       └→ Cache Answer (Redis) ───┐
│           ↓                      │
│   Store in MongoDB               │
│       ↓                         │
│   Update Conversation History    │
│       ↓                         │
│   Track Analytics               │
│       ↓                         │
└── Return Answer ◄────────────────┘
         HIT
```

---

## Technology Stack Deep Dive

### Backend Stack

#### FastAPI (Web Framework)
- **Version:** 0.109+
- **Purpose:** Async REST API server
- **Key Features:**
  - Type hints validation via Pydantic
  - Async/await support throughout
  - Dependency injection for auth, database
  - Exception handling middleware

**File:** `src/backend/main.py`
```python
app = FastAPI(title="ChemBot API", version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(content_router, prefix="/api/content", tags=["content"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
```

#### Motor (MongoDB Driver)
- **Version:** 3.3+
- **Purpose:** Async MongoDB operations
- **Connection:** Connection pooling, lazy initialization
- **File:** `src/backend/database.py`

```python
class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect_db(cls):
        cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
        cls.db = cls.client[settings.MONGODB_DB_NAME]
        await cls.create_indexes()  # Ensure indexes exist
```

#### LiteLLM (LLM Abstraction)
- **Version:** 1.24+
- **Purpose:** Unified interface for 100+ LLM providers
- **Supported Providers:**
  - OpenAI (GPT-4, GPT-3.5, GPT-4o)
  - Anthropic (Claude 3)
  - Google (Gemini Pro)
  - Local (Ollama, LM Studio)
  - Azure OpenAI
  - Hugging Face
  - Many more...

**Usage in Code:**
```python
import litellm

response = await litellm.acompletion(
    model=self.llm_model,  # "gpt-4o-mini" or "claude-3-sonnet"
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=self.temperature,
    max_tokens=self.max_tokens
)
```

#### Redis (Caching Layer)
- **Version:** 7.0+ (redis.asyncio)
- **Purpose:** Q&A response caching
- **TTL:** 7 days (604,800 seconds)
- **Key Format:** `chembot:qa:<sha256_hash>`
- **File:** `src/backend/cache/redis_cache.py`

**Cache Key Generation:**
```python
def _generate_cache_key(self, question: str, content_id: str, **kwargs) -> str:
    # Normalize question
    normalized_question = question.lower().strip()

    # Create cache string with all parameters
    cache_string = f"{content_id}:{normalized_question}"

    # Include other parameters (top_k, model, etc.)
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        cache_string += ":" + json.dumps(sorted_kwargs, sort_keys=True)

    # Generate SHA256 hash
    cache_key = hashlib.sha256(cache_string.encode()).hexdigest()

    return f"chembot:qa:{cache_key}"
```

#### Pinecone (Vector Database)
- **Version:** 3.0+
- **Purpose:** Semantic search over document chunks
- **Index Configuration:**
  - Dimension: 1536 (OpenAI text-embedding-3-small)
  - Metric: Cosine similarity
  - Cloud: Serverless (AWS us-east-1) or Pod-based
- **File:** `src/backend/rag/vector_store.py`

**Vector Operations:**
```python
class VectorStoreManager:
    async def upsert_vectors(self, vectors: List[Dict], content_id: str):
        # Batch upsert with metadata
        self.index.upsert(
            vectors=[(v["id"], v["values"], v["metadata"])
                    for v in vectors],
            namespace=content_id
        )

    async def search_similar(self, query: str, content_id: str, top_k: int = 5):
        # Generate query embedding
        query_embedding = await self._get_embedding(query)

        # Search Pinecone
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=content_id,
            include_metadata=True
        )
        return results.matches
```

---

## Database Schema & Operations

### MongoDB Collections

#### 1. **users** Collection

**Purpose:** Store user authentication and profile data

**Schema:**
```python
{
    "_id": ObjectId("..."),
    "email": "student@example.com",  # Unique index
    "password_hash": "$2b$12$...",   # Bcrypt hashed
    "name": "John Doe",
    "role": "student",               # "student" | "teacher"
    "created_at": ISODate("2024-01-15T10:30:00Z"),
    "updated_at": ISODate("2024-01-15T10:30:00Z")
}
```

**Indexes:**
```javascript
db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "created_at": 1 })
db.users.createIndex({ "role": 1 })
```

**Common Queries:**
```javascript
// Find user by email
db.users.findOne({ email: "student@example.com" })

// Get all students
db.users.find({ role: "student" })

// Count users by role
db.users.aggregate([
    { $group: { _id: "$role", count: { $sum: 1 } } }
])
```

#### 2. **content** Collection

**Purpose:** Store uploaded documents and processing metadata

**Schema:**
```python
{
    "_id": ObjectId("690beb184671fca6ed94593d"),
    "title": "IB Chemistry Notes.pdf",
    "file_name": "IB Chemistry Notes.pdf",
    "file_path": "/uploads/690beb184671fca6ed94593d.pdf",
    "file_size": 2458632,  # Bytes
    "file_type": "pdf",
    "file_hash": "sha256:abc123...",  # For duplicate detection
    "user_id": "67890...",
    "status": "completed",  # "pending" | "processing" | "completed" | "failed"
    "text_content": "Full extracted text...",
    "chunks_count": 45,
    "embeddings_count": 45,
    "vector_store_id": "chembot",  # Pinecone namespace
    "metadata": {
        "pages": 12,
        "word_count": 5432,
        "chunking_strategy": "semantic",
        "chunk_size": 800,
        "chunk_overlap": 150
    },
    "is_duplicate": false,
    "original_content_id": null,  # If duplicate, ID of original
    "created_at": ISODate("2024-01-15T10:30:00Z"),
    "updated_at": ISODate("2024-01-15T10:35:00Z"),
    "processed_at": ISODate("2024-01-15T10:35:00Z"),
    "error_message": null
}
```

**Indexes:**
```javascript
db.content.createIndex({ "user_id": 1, "created_at": -1 })
db.content.createIndex({ "file_hash": 1, "user_id": 1 })
db.content.createIndex({ "status": 1 })
db.content.createIndex({ "created_at": -1 })
```

**Common Queries:**
```javascript
// Get user's content
db.content.find({ user_id: "67890..." }).sort({ created_at: -1 })

// Find duplicate file
db.content.findOne({
    file_hash: "sha256:abc123...",
    user_id: "67890...",
    status: "completed"
})

// Get processing status
db.content.findOne({ _id: ObjectId("690beb184671fca6ed94593d") },
                   { status: 1, error_message: 1 })

// Count by status
db.content.aggregate([
    { $group: { _id: "$status", count: { $sum: 1 } } }
])
```

#### 3. **questions** Collection

**Purpose:** Store question-answer interactions

**Schema:**
```python
{
    "_id": ObjectId("..."),
    "question": "What are covalent bonds?",
    "answer": "Covalent bonds are chemical bonds...",
    "content_id": "690beb184671fca6ed94593d",
    "user_id": "67890...",
    "confidence_score": 0.92,
    "response_time_ms": 1542,
    "model_used": "gpt-4o-mini",
    "tokens_used": 342,
    "source_chunks": [
        {
            "text": "A covalent bond is formed when...",
            "chunk_index": 12,
            "relevance_score": 0.89,
            "page": 5
        }
    ],
    "cached": false,  # Was this answer from cache?
    "classification": {
        "question_type": "factual",
        "is_question": true,
        "is_relevant": true,
        "confidence": 0.95
    },
    "created_at": ISODate("2024-01-15T11:20:00Z")
}
```

**Indexes:**
```javascript
db.questions.createIndex({ "content_id": 1, "created_at": -1 })
db.questions.createIndex({ "user_id": 1, "created_at": -1 })
db.questions.createIndex({ "created_at": -1 })
db.questions.createIndex({ "content_id": 1, "user_id": 1, "created_at": -1 })
db.questions.createIndex({ "question": "text" })  // Full-text search
```

**Common Queries:**
```javascript
// Get questions for a content
db.questions.find({ content_id: "690beb184671fca6ed94593d" })
            .sort({ created_at: -1 })
            .limit(50)

// Get user's question history
db.questions.find({ user_id: "67890..." })
            .sort({ created_at: -1 })

// Find most asked questions
db.questions.aggregate([
    { $group: {
        _id: "$question",
        count: { $sum: 1 },
        avg_confidence: { $avg: "$confidence_score" }
    }},
    { $sort: { count: -1 } },
    { $limit: 10 }
])

// Average response time
db.questions.aggregate([
    { $group: {
        _id: null,
        avg_response_time: { $avg: "$response_time_ms" },
        cached_count: { $sum: { $cond: ["$cached", 1, 0] } }
    }}
])
```

#### 4. **analytics** Collection

**Purpose:** Track user interactions and events

**Schema:**
```python
{
    "_id": ObjectId("..."),
    "event_type": "question_asked",  # "question_asked" | "content_uploaded" | "login"
    "user_id": "67890...",
    "content_id": "690beb184671fca6ed94593d",  # Optional
    "question_id": "...",  # Optional
    "metadata": {
        "response_time_ms": 1542,
        "question_type": "factual",
        "cached": false,
        "confidence": 0.92
    },
    "duration_ms": 1542,
    "timestamp": ISODate("2024-01-15T11:20:00Z")
}
```

**Indexes:**
```javascript
db.analytics.createIndex({ "user_id": 1, "timestamp": -1 })
db.analytics.createIndex({ "content_id": 1, "timestamp": -1 })
db.analytics.createIndex({ "event_type": 1, "timestamp": -1 })
db.analytics.createIndex({ "timestamp": -1 })
```

**Analytics Queries:**

```javascript
// Student engagement (questions per user)
db.analytics.aggregate([
    { $match: { event_type: "question_asked" } },
    { $group: {
        _id: "$user_id",
        total_questions: { $sum: 1 },
        avg_response_time: { $avg: "$metadata.response_time_ms" }
    }},
    { $sort: { total_questions: -1 } }
])

// Content popularity
db.analytics.aggregate([
    { $match: { event_type: "question_asked" } },
    { $group: {
        _id: "$content_id",
        question_count: { $sum: 1 },
        unique_users: { $addToSet: "$user_id" }
    }},
    { $project: {
        question_count: 1,
        unique_user_count: { $size: "$unique_users" }
    }},
    { $sort: { question_count: -1 } }
])

// Daily active users
db.analytics.aggregate([
    { $match: {
        timestamp: { $gte: ISODate("2024-01-01") }
    }},
    { $group: {
        _id: { $dateToString: { format: "%Y-%m-%d", date: "$timestamp" } },
        unique_users: { $addToSet: "$user_id" }
    }},
    { $project: {
        date: "$_id",
        user_count: { $size: "$unique_users" }
    }},
    { $sort: { _id: 1 } }
])

// Cache hit rate
db.analytics.aggregate([
    { $match: { event_type: "question_asked" } },
    { $group: {
        _id: null,
        total: { $sum: 1 },
        cached: { $sum: { $cond: ["$metadata.cached", 1, 0] } }
    }},
    { $project: {
        total: 1,
        cached: 1,
        hit_rate: { $multiply: [{ $divide: ["$cached", "$total"] }, 100] }
    }}
])
```

### Database Utility Functions

**File:** `src/backend/utils/db_utils.py`

Key functions:
- `create_user()` - Create new user with hashed password
- `get_user_by_email()` - Find user for authentication
- `create_content()` - Create content record
- `get_content_by_id()` - Retrieve content details
- `get_contents_by_user()` - List user's content
- `delete_content()` - Delete content and related data
- `create_question()` - Store Q&A interaction
- `get_questions_by_content()` - Get questions for content
- `create_analytics_event()` - Track analytics event
- `find_duplicate_content()` - Check for duplicate files
- `calculate_file_hash()` - Generate SHA-256 hash

---

## API Implementation Details

### Authentication Endpoints

**File:** `src/backend/routes/auth.py`

#### POST `/api/auth/register`

**Purpose:** Register new user account

**Request Body:**
```json
{
    "email": "student@example.com",
    "password": "securepass123",
    "name": "John Doe",
    "role": "student"
}
```

**Response:**
```json
{
    "user": {
        "id": "67890...",
        "email": "student@example.com",
        "name": "John Doe",
        "role": "student"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

**Implementation:**
```python
@router.post("/register")
async def register(user_data: UserRegister):
    # Check if email already exists
    existing_user = await db_utils.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user with hashed password
    user = await db_utils.create_user(db, user_data)

    # Generate JWT token
    access_token = jwt_handler.create_access_token(data={"sub": user.email})

    return {"user": user, "access_token": access_token, "token_type": "bearer"}
```

#### POST `/api/auth/login`

**Purpose:** Authenticate user and return JWT token

**Request Body:**
```json
{
    "email": "student@example.com",
    "password": "securepass123"
}
```

**Response:**
```json
{
    "user": {
        "id": "67890...",
        "email": "student@example.com",
        "name": "John Doe",
        "role": "student"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

**Implementation:**
```python
@router.post("/login")
async def login(credentials: UserLogin):
    # Find user by email
    user = await db_utils.get_user_by_email(db, credentials.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate JWT token
    access_token = jwt_handler.create_access_token(data={"sub": user.email})

    return {"user": user, "access_token": access_token, "token_type": "bearer"}
```

### Content Management Endpoints

**File:** `src/backend/routes/content.py`

#### POST `/api/content/upload`

**Purpose:** Upload and process document

**Request:** Multipart form data with file

**Response:**
```json
{
    "content": {
        "id": "690beb184671fca6ed94593d",
        "title": "Chemistry Notes.pdf",
        "fileName": "Chemistry Notes.pdf",
        "fileSize": 2458632,
        "uploadedAt": "2024-01-15T10:30:00Z",
        "status": "processing",
        "userId": "67890...",
        "isDuplicate": false,
        "originalContentId": null
    },
    "message": "File uploaded successfully. Processing started."
}
```

**Implementation:**
```python
@router.post("/upload")
async def upload_content(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    # Validate file type and size
    allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(400, "File type not supported")

    # Save file
    temp_file_path = UPLOAD_DIR / f"{ObjectId()}{file_ext}"
    async with aiofiles.open(temp_file_path, 'wb') as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)

    # Check for duplicates
    file_hash = calculate_file_hash(str(temp_file_path))
    duplicate = await find_duplicate_content(db, file_hash, user_id)

    # Create content record
    content = await create_content(db, content_data, user_id, file_info)

    # Process in background
    if duplicate:
        background_tasks.add_task(copy_content_from_original, ...)
    else:
        background_tasks.add_task(process_content_background, ...)

    return {"content": content, "message": "..."}
```

**Background Processing:**
```python
async def process_content_background(content_id: str, file_path: str, user_id: str):
    # Initialize RAG pipeline
    pipeline = RAGPipeline()

    # Process document
    result = await pipeline.process_document(
        file_path=file_path,
        file_type=mime_type,
        content_id=content_id
    )
    # Steps: Extract text → Chunk → Generate embeddings → Store in Pinecone

    # Update database
    await db.content.update_one(
        {"_id": ObjectId(content_id)},
        {"$set": {
            "status": "completed",
            "chunks_count": result["chunks_count"],
            "embeddings_count": result["embeddings_count"]
        }}
    )
```

#### POST `/api/content/{content_id}/question`

**Purpose:** Ask question about content (streaming or non-streaming)

**Request Body:**
```json
{
    "question": "What are covalent bonds?",
    "stream": false,
    "clear_history": false
}
```

**Response (Non-Streaming):**
```json
{
    "answer": "Covalent bonds are chemical bonds formed by sharing electron pairs between atoms...",
    "message": {
        "id": "...",
        "contentId": "690beb184671fca6ed94593d",
        "question": "What are covalent bonds?",
        "answer": "...",
        "timestamp": "2024-01-15T11:20:00Z",
        "userId": "67890..."
    },
    "cached": false,
    "confidence_score": 0.92,
    "sources": [...]
}
```

**Response (Streaming):**
```
data: {"chunk": "Covalent"}
data: {"chunk": " bonds are"}
data: {"chunk": " chemical"}
...
data: {"done": true, "full_answer": "Covalent bonds are..."}
```

**Implementation:**
```python
@router.post("/{content_id}/question")
async def ask_question(content_id: str, request: dict, current_user = Depends(get_current_user)):
    question = request.get("question")
    stream = request.get("stream", False)
    clear_history = request.get("clear_history", False)

    # Initialize chatbot
    chatbot = ChatbotEngine(db)
    await chatbot.initialize()

    # Load or clear conversation history
    if clear_history:
        chatbot.clear_conversation_history(content_id, user_id)
    else:
        await chatbot.load_conversation_history(user_id, content_id)

    # Handle streaming
    if stream:
        async def generate_stream():
            async for chunk in chatbot.ask_question_stream(
                question=question,
                content_id=content_id,
                user_id=user_id
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    # Non-streaming
    result = await chatbot.ask_question(question, content_id, user_id)
    return {"answer": result["answer"], "message": {...}, ...}
```

---

## RAG Pipeline Architecture

### Document Processing Pipeline

**File:** `src/backend/rag/pipeline.py`

**Flow:**
```
Upload PDF → Extract Text → Chunk Text → Generate Embeddings → Store Vectors
```

**Implementation:**
```python
class RAGPipeline:
    async def process_document(self, file_path: str, file_type: str, content_id: str):
        # Step 1: Extract text
        text_content = await self.document_processor.process_document(
            file_path, file_type
        )

        # Step 2: Chunk text
        chunks = await self.chunker.chunk_text(
            text_content,
            strategy=settings.CHUNKING_STRATEGY
        )

        # Step 3: Generate embeddings
        embeddings = await self.embedder.generate_embeddings(chunks)

        # Step 4: Store in vector database
        await self.vector_store.upsert_vectors(
            vectors=embeddings,
            content_id=content_id
        )

        return {
            "chunks_count": len(chunks),
            "embeddings_count": len(embeddings)
        }
```

### Chunking Strategies

**File:** `src/backend/rag/chunking.py`

#### 1. Heuristic Chunking
- Fixed-size chunks with overlap
- Simple and fast
- Good for uniform content

```python
def heuristic_chunk(text: str, chunk_size: int = 800, overlap: int = 150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks
```

#### 2. Semantic Chunking
- Chunk by semantic boundaries (sentences, paragraphs)
- Better context preservation
- More accurate retrieval

```python
def semantic_chunk(text: str, chunk_size: int = 800):
    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        if current_length + len(sentence) > chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = len(sentence)
        else:
            current_chunk.append(sentence)
            current_length += len(sentence)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
```

#### 3. Intelligent Chunking
- Preserves document structure (sections, headings)
- Best quality, higher complexity
- Ideal for academic content

### Query Processing

**File:** `src/backend/rag/query_engine.py`

**Flow:**
```
Question → Check Cache → Generate Embedding → Search Vectors → Retrieve Chunks → Generate Answer → Cache
```

**Implementation:**
```python
class QueryEngine:
    async def answer_question(self, question: str, content_id: str, top_k: int = 5):
        # Cache is checked in ChatbotEngine before this

        # Step 1: Retrieve relevant chunks
        relevant_chunks = await self.vector_manager.search_similar(
            query=question,
            content_id=content_id,
            top_k=top_k
        )

        # Step 2: Prepare context
        context = self._prepare_context(relevant_chunks)

        # Step 3: Generate answer using LLM
        answer_data = await self._generate_answer(question, context)

        # Step 4: Cache answer
        await self.cache_manager.cache_answer(
            question=question,
            content_id=content_id,
            answer_data=answer_data,
            top_k=top_k,
            model=self.llm_model
        )

        return answer_data
```

**Prompt Engineering:**

**File:** `src/backend/prompts.yaml`

```yaml
chatbot_system_prompt: |
  You are an intelligent educational assistant helping students learn from their uploaded materials.

  Rules:
  1. Answer ONLY based on the provided context
  2. If information is not in the context, say "I don't have that information"
  3. Use clear, educational language
  4. Break down complex concepts
  5. Provide examples when helpful
  6. Be encouraging and supportive

chatbot_user_prompt: |
  Context from the learning material:
  {context}

  Student's Question: {question}

  Provide a clear, accurate answer based ONLY on the above context.
```

---

## Caching Strategy

### Redis Cache Architecture

**Purpose:** Cache LLM responses to avoid redundant API calls

**Benefits:**
- **Speed:** 5-10ms response time (vs 1500-2000ms without cache)
- **Cost:** 60-80% reduction in LLM API costs
- **Scalability:** Handle 40x more requests

**File:** `src/backend/cache/redis_cache.py`

### Cache Key Generation

**Formula:**
```
cache_key = "chembot:qa:" + SHA256(content_id + normalized_question + parameters)
```

**Example:**
```python
# Question: "What are Covalent Bonds?"
# Normalized: "what are covalent bonds?"
# Content ID: "690beb184671fca6ed94593d"
# Parameters: top_k=5, model="gpt-4o-mini"

cache_string = "690beb184671fca6ed94593d:what are covalent bonds?:{\"model\":\"gpt-4o-mini\",\"top_k\":5}"
cache_key = "chembot:qa:" + sha256(cache_string).hexdigest()
# Result: "chembot:qa:a7f3c2d8e1b4f6a9..."
```

**Why SHA-256?**
- Consistent key length (64 hex chars)
- Case-insensitive (after normalization)
- Same question → Same key
- Different parameters → Different key

### Cache Operations

#### Get Cached Answer
```python
async def get_cached_answer(self, question: str, content_id: str, **kwargs):
    if not self.enabled:
        return None

    # Generate cache key
    cache_key = self._generate_cache_key(question, content_id, **kwargs)

    # Get from Redis
    cached_data = await self.client.get(cache_key)

    if cached_data:
        logger.info(f"Cache hit for: '{question[:70]}...'")
        return json.loads(cached_data)
    else:
        logger.info(f"Cache miss for: '{question[:70]}...'")
        return None
```

#### Cache Answer
```python
async def cache_answer(self, question: str, content_id: str, answer_data: Dict, **kwargs):
    if not self.enabled:
        return

    cache_key = self._generate_cache_key(question, content_id, **kwargs)

    # Add cache metadata
    cache_data = {
        **answer_data,
        "cached": True,
        "cache_key": cache_key
    }

    # Store with TTL (7 days)
    await self.client.setex(
        cache_key,
        self.ttl,  # 604800 seconds
        json.dumps(cache_data)
    )
```

### Cache in Streaming Mode

**Challenge:** Streaming responses are generated progressively, but cache needs full answer

**Solution:**
1. **Before streaming:** Check cache, if HIT → stream cached answer in chunks
2. **During streaming:** Collect full answer as chunks arrive
3. **After streaming:** Store complete answer in cache

**Implementation:**
```python
async def ask_question_stream(self, question: str, content_id: str, user_id: str):
    # Check cache first
    if use_cache:
        cached_answer = await self.cache_manager.get_cached_answer(
            question=question,
            content_id=content_id,
            top_k=5,
            model=self.query_engine.llm_model
        )

        if cached_answer:
            # Stream cached answer in chunks
            answer = cached_answer.get("answer", "")
            chunk_size = 10

            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.01)  # Simulate streaming
            return

    # Generate fresh answer
    full_answer = ""
    async for chunk in self.query_engine.answer_question_stream(...):
        full_answer += chunk
        yield chunk

    # Cache for future requests
    if use_cache and full_answer:
        cache_data = {
            "answer": full_answer,
            "confidence_score": 0.8,
            "model_used": self.query_engine.llm_model,
            ...
        }
        await self.cache_manager.cache_answer(
            question=question,
            content_id=content_id,
            answer_data=cache_data,
            top_k=5,
            model=self.query_engine.llm_model
        )
```

### Cache Invalidation

**When to invalidate:**
- Content is deleted
- Content is re-processed
- Manual cache clear

**Implementation:**
```python
async def invalidate_content_cache(self, content_id: str):
    pattern = f"chembot:qa:*{content_id}*"
    cursor = 0
    deleted_count = 0

    while True:
        cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
        if keys:
            await self.client.delete(*keys)
            deleted_count += len(keys)

        if cursor == 0:
            break

    logger.info(f"Invalidated {deleted_count} cached answers for content {content_id}")
```

### Monitoring Cache

**Check cache stats:**
```bash
# Connect to Redis
redis-cli

# View all cache keys
KEYS "chembot:qa:*"

# Count cache entries
DBSIZE

# Get cache hit/miss stats
INFO stats

# Monitor cache operations in real-time
MONITOR
```

**Get stats programmatically:**
```python
async def get_cache_stats(self):
    info = await self.client.info()

    return {
        "enabled": True,
        "connected": True,
        "total_keys": info.get("db0", {}).get("keys", 0),
        "used_memory_human": info.get("used_memory_human", "N/A"),
        "hits": info.get("keyspace_hits", 0),
        "misses": info.get("keyspace_misses", 0),
        "hit_rate": self._calculate_hit_rate(
            info.get("keyspace_hits", 0),
            info.get("keyspace_misses", 0)
        )
    }
```

---

## Authentication & Security

### JWT Implementation

**File:** `src/backend/auth/jwt_handler.py`

**Token Generation:**
```python
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # 7-day expiry

    to_encode.update({"exp": expire})

    # Sign with HS256
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm="HS256"
    )

    return encoded_jwt
```

**Token Verification:**
```python
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Decode JWT
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )

        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(401, "Invalid authentication credentials")

        # Get user from database
        user = await db_utils.get_user_by_email(db, email)
        if user is None:
            raise HTTPException(401, "User not found")

        return user

    except JWTError:
        raise HTTPException(401, "Invalid authentication credentials")
```

**Usage in Routes:**
```python
@router.get("/protected")
async def protected_route(current_user = Depends(get_current_user)):
    return {"message": f"Hello {current_user.name}"}
```

### Password Security

**Hashing with bcrypt:**
```python
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )
```

### CORS Configuration

**File:** `src/backend/main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Environment Variable:**
```env
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","https://your-domain.com"]
```

---

## Frontend Architecture

### Project Structure

```
src/frontend/
├── main.tsx                 # React entry point
├── App.tsx                  # Root component + routing
├── index.css                # Global styles
├── api/                     # API client layer
│   ├── client.ts           # Axios base client
│   ├── auth.ts             # Auth API calls
│   ├── content.ts          # Content API calls
│   ├── chat.ts             # Chat API calls
│   └── analytics.ts        # Analytics API calls
├── components/
│   ├── auth/
│   │   ├── LoginForm.tsx
│   │   └── ProtectedRoute.tsx
│   ├── chat/
│   │   ├── ChatBox.tsx
│   │   ├── InputBox.tsx
│   │   └── Message.tsx
│   ├── content/
│   │   ├── ContentCard.tsx
│   │   ├── ContentList.tsx
│   │   └── FileUpload.tsx
│   └── shared/
│       ├── ErrorMessage.tsx
│       ├── Loader.tsx
│       └── Toast.tsx
├── context/                 # React Context
│   ├── AuthContext.tsx
│   ├── ChatContext.tsx
│   └── ContentContext.tsx
├── pages/
│   ├── LoginPage.tsx
│   ├── ContentListPage.tsx
│   ├── ChatbotPage.tsx
│   └── AnalyticsPage.tsx
└── utils/
    ├── constants.ts
    ├── types.ts
    └── validators.ts
```

### State Management

**Authentication Context:**

**File:** `src/frontend/context/AuthContext.tsx`

```typescript
interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (email: string, password: string) => Promise<void>;
    register: (data: RegisterData) => Promise<void>;
    logout: () => void;
    isAuthenticated: boolean;
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(
        localStorage.getItem('token')
    );

    const login = async (email: string, password: string) => {
        const response = await authAPI.login({ email, password });
        setUser(response.user);
        setToken(response.access_token);
        localStorage.setItem('token', response.access_token);
    };

    const logout = () => {
        setUser(null);
        setToken(null);
        localStorage.removeItem('token');
    };

    return (
        <AuthContext.Provider value={{ user, token, login, register, logout, isAuthenticated: !!token }}>
            {children}
        </AuthContext.Provider>
    );
};
```

### API Client Layer

**File:** `src/frontend/api/client.ts`

```typescript
import axios from 'axios';

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default apiClient;
```

### Routing

**File:** `src/frontend/App.tsx`

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';

function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route
                        path="/contents"
                        element={
                            <ProtectedRoute>
                                <ContentListPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/chat/:contentId"
                        element={
                            <ProtectedRoute>
                                <ChatbotPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route path="/" element={<Navigate to="/contents" />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}
```

---

## Configuration Management

### Environment Variables

**Backend:** `.env` file in project root

**Frontend:** `.env` or `vite.config.ts`

**Key Variables:**

```env
# === BACKEND ===

# Database
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=chembot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_CACHE_ENABLED=true
REDIS_CACHE_TTL=604800

# LLM
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Vector Database
VECTOR_DB_PROVIDER=pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=chembot

# Auth
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7

# Chunking
CHUNK_SIZE=800
CHUNK_OVERLAP=150
CHUNKING_STRATEGY=semantic

# Rate Limiting
LLM_MAX_CONCURRENT_REQUESTS=5
LLM_MAX_RETRIES=3

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# === FRONTEND ===

# API URL
VITE_API_URL=http://localhost:8000
```

### Config Loading

**File:** `src/backend/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "chembot"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_CACHE_ENABLED: bool = True
    REDIS_CACHE_TTL: int = 604800

    # OpenAI
    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

---

## Deployment & Operations

### Docker Deployment

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7.0
    container_name: chembot-mongo
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: chembot

  redis:
    image: redis:7.0-alpine
    container_name: chembot-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: .
    container_name: chembot-backend
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URL=mongodb://mongodb:27017
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - mongodb
      - redis
    volumes:
      - ./uploads:/app/uploads
    env_file:
      - .env

volumes:
  mongodb_data:
  redis_data:
```

### Database Initialization

**File:** `src/backend/init_db.py`

```python
async def init_database():
    # Connect to MongoDB
    await Database.connect_db()
    db = Database.get_db()

    # Create collections
    collections = ["users", "content", "questions", "analytics"]
    for collection in collections:
        if collection not in await db.list_collection_names():
            await db.create_collection(collection)

    # Create indexes
    await db.users.create_index([("email", 1)], unique=True)
    await db.content.create_index([("user_id", 1), ("created_at", -1)])
    await db.questions.create_index([("content_id", 1), ("created_at", -1)])
    await db.analytics.create_index([("user_id", 1), ("timestamp", -1)])

    print("✅ Database initialized successfully")

if __name__ == "__main__":
    asyncio.run(init_database())
```

### Health Checks

**Endpoint:** `GET /health`

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected" if Database.db else "disconnected",
        "redis": "connected" if await cache.ping() else "disconnected",
        "version": "1.0.0"
    }
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_rate_limiter.py`

```python
import pytest
from src.backend.utils.rate_limiter import RateLimiter

@pytest.mark.asyncio
async def test_rate_limiter_basic():
    limiter = RateLimiter(max_concurrent=2)

    async def mock_task(delay: float):
        await asyncio.sleep(delay)
        return "success"

    result = await limiter.execute_with_retry(mock_task, delay=0.1)
    assert result == "success"

@pytest.mark.asyncio
async def test_rate_limiter_concurrent():
    limiter = RateLimiter(max_concurrent=2)

    # Should allow 2 concurrent, queue 3rd
    tasks = [limiter.execute_with_retry(mock_task, delay=0.5) for _ in range(3)]
    results = await asyncio.gather(*tasks)

    assert all(r == "success" for r in results)
```

### Integration Tests

**File:** `tests/test_auth.py`

```python
@pytest.mark.asyncio
async def test_register_and_login(test_client):
    # Register
    response = await test_client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "name": "Test User",
        "role": "student"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Login
    response = await test_client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/backend --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v

# Run async tests only
pytest -k asyncio -v
```

---

## Performance Optimization

### Database Optimization

1. **Indexes:** All collections have appropriate indexes
2. **Connection Pooling:** Motor manages connection pool automatically
3. **Aggregation Pipelines:** Complex queries use optimized pipelines
4. **Projection:** Only fetch needed fields

```python
# Good - with projection
await db.content.find(
    {"user_id": user_id},
    {"_id": 1, "title": 1, "status": 1}  # Only needed fields
)

# Bad - fetch everything
await db.content.find({"user_id": user_id})
```

### API Optimization

1. **Async/Await:** All I/O operations are async
2. **Background Tasks:** File processing happens in background
3. **Streaming:** Large responses use streaming
4. **Caching:** Redis caches LLM responses

### Frontend Optimization

1. **Code Splitting:** React.lazy() for route-based code splitting
2. **Memoization:** Use React.memo() for expensive components
3. **Debouncing:** Search inputs debounced to avoid excessive API calls
4. **Virtual Scrolling:** For long lists (if needed)

---

## Troubleshooting & Debugging

### Common Issues

#### 1. MongoDB Connection Refused

**Error:**
```
MongoNetworkError: connect ECONNREFUSED 127.0.0.1:27017
```

**Solution:**
```bash
# Check if MongoDB is running
ps aux | grep mongod

# Start MongoDB
# macOS
brew services start mongodb-community

# Linux
sudo systemctl start mongod

# Verify
mongosh
```

#### 2. Redis Connection Failed

**Error:**
```
Redis connection failed: Error: connect ECONNREFUSED 127.0.0.1:6379
```

**Solution:**
```bash
# Check if Redis is running
ps aux | grep redis

# Start Redis
# macOS
brew services start redis

# Linux
sudo systemctl start redis

# Verify
redis-cli ping
# Should return: PONG
```

#### 3. OpenAI API Key Error

**Error:**
```
openai.error.AuthenticationError: Incorrect API key provided
```

**Solution:**
1. Check `.env` file has correct key
2. Ensure no extra quotes or spaces
3. Verify key is active on OpenAI dashboard
4. Restart server after changing .env

#### 4. Pinecone Index Not Found

**Error:**
```
PineconeException: Index 'chembot' not found
```

**Solution:**
1. Go to [Pinecone Console](https://app.pinecone.io/)
2. Create index:
   - Name: `chembot`
   - Dimensions: `1536`
   - Metric: `cosine`
   - Cloud: Serverless (AWS us-east-1)
3. Update `.env` with correct index name

#### 5. Cache Not Working

**Debug Steps:**
```bash
# Check Redis is running
redis-cli ping

# Check cache keys exist
redis-cli KEYS "chembot:qa:*"

# Monitor cache operations
redis-cli MONITOR

# Check .env
grep REDIS_CACHE_ENABLED .env
# Should be: REDIS_CACHE_ENABLED=true
```

### Logging

**Enable Debug Logging:**

```python
# In config.py
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**View Logs:**
```bash
# Docker logs
docker-compose logs -f backend

# Local logs
# Logs appear in terminal where server is running
```

---

## Advanced Topics

### Custom LLM Providers

**Add Ollama (local LLM):**

```env
# .env
LLM_MODEL=ollama/llama2
# No API key needed
```

**Add Claude:**

```env
# .env
LLM_MODEL=claude-3-sonnet-20240229
ANTHROPIC_API_KEY=sk-ant-...
```

### Custom Chunking Strategy

**File:** `src/backend/rag/chunking.py`

```python
class CustomChunker:
    def chunk_by_topic(self, text: str) -> List[str]:
        # Your custom logic
        chunks = []
        # ... implementation
        return chunks
```

### Database Backups

```bash
# Backup MongoDB
mongodump --uri="mongodb://localhost:27017" --out=/backups/$(date +%Y%m%d)

# Restore MongoDB
mongorestore --uri="mongodb://localhost:27017" /backups/20240115

# Backup Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb /backups/redis-$(date +%Y%m%d).rdb
```

---

## Appendix

### Useful Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild images
docker-compose up --build

# Access MongoDB shell
mongosh

# Access Redis CLI
redis-cli

# Run tests
pytest

# Check cache stats
redis-cli INFO stats

# Clear cache
redis-cli FLUSHDB

# Check Pinecone stats
# (Use Pinecone dashboard)
```

### API Testing with cURL

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","name":"Test","role":"student"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Upload file
curl -X POST http://localhost:8000/api/content/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"

# Ask question
curl -X POST http://localhost:8000/api/content/CONTENT_ID/question \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is this about?"}'
```

---

## Conclusion

This implementation guide covers all technical aspects of ChemBot. For user-facing documentation, see [README.md](README.md). For API reference, see [API_ENDPOINTS_REFERENCE.md](API_ENDPOINTS_REFERENCE.md).

**Questions or issues?** Check the troubleshooting section or create an issue on GitHub.

---

**Document Version:** 1.0
**Last Updated:** January 2025
**Maintainer:** ChemBot Development Team
