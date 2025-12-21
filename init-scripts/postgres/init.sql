-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create enum for knowledge categories
DO $$ BEGIN
    CREATE TYPE knowledge_category AS ENUM (
        'draft', 'concept', 'character', 'chapter', 
        'settings', 'worldbuilding', 'plot', 'dialogue', 'research', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create tables for novel RAG system

-- Chapters/Content storage
CREATE TABLE IF NOT EXISTS chapters (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    chapter_number INTEGER,
    word_count INTEGER,
    embedding vector(1536),
    language VARCHAR(10) DEFAULT 'en', -- 'en', 'zh-TW', 'zh-CN'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Knowledge base with categories
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL, -- 'chat', 'document', 'idea', 'upload'
    category VARCHAR(50) DEFAULT 'other', -- draft, concept, character, chapter, settings, etc.
    title VARCHAR(500),
    content TEXT NOT NULL,
    summary TEXT, -- AI-generated summary for long content
    embedding vector(1536),
    language VARCHAR(10) DEFAULT 'en',
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Uploaded documents
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- 'pdf', 'docx', 'txt'
    file_size INTEGER,
    category VARCHAR(50) DEFAULT 'other',
    content TEXT, -- Extracted text content
    chunk_count INTEGER DEFAULT 0,
    language VARCHAR(10) DEFAULT 'en',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document chunks for long context support
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Character profiles (detailed tracking)
CREATE TABLE IF NOT EXISTS character_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    aliases TEXT[],
    description TEXT,
    personality TEXT,
    appearance TEXT,
    background TEXT,
    goals TEXT,
    relationships_summary TEXT,
    first_appearance INTEGER, -- chapter number
    language VARCHAR(10) DEFAULT 'en',
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) DEFAULT 'New Chat',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Chat messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ideas and notes
CREATE TABLE IF NOT EXISTS ideas (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    embedding vector(1536),
    tags TEXT[],
    related_chapters INTEGER[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for vector similarity search
CREATE INDEX IF NOT EXISTS chapters_embedding_idx ON chapters 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx ON knowledge_base 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS chat_messages_embedding_idx ON chat_messages 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS ideas_embedding_idx ON ideas 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx ON document_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS character_profiles_embedding_idx ON character_profiles 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS chat_sessions_updated_idx ON chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS chapters_number_idx ON chapters(chapter_number);
CREATE INDEX IF NOT EXISTS knowledge_base_category_idx ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS document_chunks_doc_idx ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS documents_category_idx ON documents(category);

