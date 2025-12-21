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

-- =====================================================
-- SERIES & BOOK HIERARCHY (Improvement #1)
-- =====================================================

-- Series (e.g., "Harry Potter Series")
CREATE TABLE IF NOT EXISTS series (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    premise TEXT, -- Overall series premise
    themes TEXT[], -- Major themes across series
    world_rules JSONB DEFAULT '{}', -- Magic system, technology rules, etc.
    total_planned_books INTEGER DEFAULT 1,
    language VARCHAR(10) DEFAULT 'en',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Books within a series
CREATE TABLE IF NOT EXISTS books (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    book_number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    theme TEXT, -- This book's specific theme
    synopsis TEXT,
    status VARCHAR(50) DEFAULT 'planning', -- planning, drafting, editing, published
    target_word_count INTEGER,
    current_word_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Story arcs spanning multiple books
CREATE TABLE IF NOT EXISTS story_arcs (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    arc_type VARCHAR(50) DEFAULT 'plot', -- plot, character, relationship, mystery
    start_book INTEGER,
    end_book INTEGER,
    status VARCHAR(50) DEFAULT 'active', -- planted, active, climaxing, resolved
    resolution_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chapters/Content storage (enhanced with book reference)
CREATE TABLE IF NOT EXISTS chapters (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    chapter_number INTEGER,
    pov_character VARCHAR(200), -- Point of view character
    story_timeline_position VARCHAR(100), -- e.g., "Year 1, September"
    word_count INTEGER,
    summary TEXT, -- AI-generated chapter summary
    embedding vector(384),
    language VARCHAR(10) DEFAULT 'en',
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
    embedding vector(384),
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
    embedding vector(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- CHARACTER KNOWLEDGE TRACKING (Improvement #2)
-- =====================================================

-- Character profiles (enhanced with knowledge tracking and verification)
CREATE TABLE IF NOT EXISTS character_profiles (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    aliases TEXT[],
    description TEXT,
    personality TEXT,
    appearance TEXT,
    background TEXT,
    goals TEXT,
    fears TEXT[], -- What the character fears
    secrets TEXT[], -- Secrets this character holds
    speech_patterns TEXT, -- How they talk (dialect, vocabulary)
    relationships_summary TEXT,
    first_appearance_book INTEGER,
    first_appearance_chapter INTEGER,
    is_pov_character BOOLEAN DEFAULT FALSE,
    -- Verification status: pending, approved, rejected
    verification_status VARCHAR(20) DEFAULT 'approved',
    auto_extracted BOOLEAN DEFAULT FALSE, -- TRUE if auto-generated
    extraction_source TEXT, -- Which chapter/content it was extracted from
    language VARCHAR(10) DEFAULT 'en',
    embedding vector(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(series_id, name)
);

-- Story facts (things that can be known by characters)
CREATE TABLE IF NOT EXISTS story_facts (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    fact_description TEXT NOT NULL,
    fact_category VARCHAR(50) DEFAULT 'plot', -- plot, world, character, secret
    established_in_chapter INTEGER,
    is_secret BOOLEAN DEFAULT FALSE, -- Hidden from most characters
    is_public BOOLEAN DEFAULT FALSE, -- Known to everyone
    importance VARCHAR(20) DEFAULT 'normal', -- trivial, normal, major, critical
    -- Verification status: pending, approved, rejected
    verification_status VARCHAR(20) DEFAULT 'approved',
    auto_extracted BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- What each character knows (knowledge tracking)
CREATE TABLE IF NOT EXISTS character_knowledge (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES character_profiles(id) ON DELETE CASCADE,
    fact_id INTEGER REFERENCES story_facts(id) ON DELETE CASCADE,
    learned_in_chapter INTEGER,
    learned_how TEXT, -- 'witnessed', 'told_by', 'discovered', 'deduced'
    certainty VARCHAR(20) DEFAULT 'knows', -- suspects, believes, knows, wrong_about
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(character_id, fact_id)
);

-- Character state at specific points in story
CREATE TABLE IF NOT EXISTS character_states (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES character_profiles(id) ON DELETE CASCADE,
    as_of_chapter INTEGER NOT NULL,
    emotional_state TEXT,
    physical_state TEXT, -- injuries, conditions
    location VARCHAR(200),
    possessions TEXT[], -- Important items they have
    relationship_changes JSONB DEFAULT '{}', -- Changes in relationships
    arc_stage VARCHAR(100), -- Where they are in their character arc
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- FORESHADOWING & PAYOFF REGISTRY (Improvement #3)
-- =====================================================

CREATE TABLE IF NOT EXISTS foreshadowing (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    title VARCHAR(500), -- Brief name for this seed
    planted_book INTEGER,
    planted_chapter INTEGER,
    planted_text TEXT, -- The actual text that plants the seed
    seed_type VARCHAR(50) DEFAULT 'plot', -- plot, character, thematic, world, chekhov_gun
    subtlety INTEGER DEFAULT 3 CHECK (subtlety BETWEEN 1 AND 5), -- 1=obvious, 5=very subtle
    intended_payoff TEXT, -- What this should lead to
    payoff_book INTEGER,
    payoff_chapter INTEGER,
    payoff_text TEXT, -- The text that pays it off
    status VARCHAR(50) DEFAULT 'planted', -- planted, reinforced, paid_off, abandoned
    reinforcement_count INTEGER DEFAULT 0,
    -- Verification status: pending, approved, rejected
    verification_status VARCHAR(20) DEFAULT 'approved',
    auto_extracted BOOLEAN DEFAULT FALSE,
    extraction_confidence FLOAT DEFAULT 1.0, -- AI confidence score 0-1
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Track reinforcements of foreshadowing
CREATE TABLE IF NOT EXISTS foreshadowing_reinforcements (
    id SERIAL PRIMARY KEY,
    foreshadowing_id INTEGER REFERENCES foreshadowing(id) ON DELETE CASCADE,
    book_number INTEGER,
    chapter_number INTEGER,
    reinforcement_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- LLM STORY ANALYSIS (Improvement #5)
-- =====================================================

-- Store LLM analysis results for caching and reference
CREATE TABLE IF NOT EXISTS story_analyses (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    analysis_type VARCHAR(100) NOT NULL, -- consistency_check, pacing, character_voice, plot_holes, etc.
    query TEXT, -- The question asked
    analysis_result TEXT NOT NULL, -- LLM's analysis
    issues_found JSONB DEFAULT '[]', -- Structured list of issues
    suggestions JSONB DEFAULT '[]', -- Structured list of suggestions
    severity VARCHAR(20) DEFAULT 'info', -- info, warning, error, critical
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- World rules for consistency checking
CREATE TABLE IF NOT EXISTS world_rules (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    rule_category VARCHAR(100) NOT NULL, -- magic, technology, society, geography, biology
    rule_name VARCHAR(500) NOT NULL,
    rule_description TEXT NOT NULL,
    exceptions TEXT[], -- Known exceptions to the rule
    source_book INTEGER,
    source_chapter INTEGER,
    source_text TEXT, -- Where this rule was established
    is_hard_rule BOOLEAN DEFAULT TRUE, -- FALSE = can be bent, TRUE = must never break
    -- Verification status: pending, approved, rejected
    verification_status VARCHAR(20) DEFAULT 'approved',
    auto_extracted BOOLEAN DEFAULT FALSE,
    extraction_confidence FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
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
    embedding vector(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ideas and notes
CREATE TABLE IF NOT EXISTS ideas (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    embedding vector(384),
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
CREATE INDEX IF NOT EXISTS chapters_book_idx ON chapters(book_id);
CREATE INDEX IF NOT EXISTS knowledge_base_category_idx ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS document_chunks_doc_idx ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS documents_category_idx ON documents(category);

-- New indexes for series/book structure
CREATE INDEX IF NOT EXISTS books_series_idx ON books(series_id);
CREATE INDEX IF NOT EXISTS story_arcs_series_idx ON story_arcs(series_id);
CREATE INDEX IF NOT EXISTS character_profiles_series_idx ON character_profiles(series_id);

-- Indexes for character knowledge tracking
CREATE INDEX IF NOT EXISTS story_facts_series_idx ON story_facts(series_id);
CREATE INDEX IF NOT EXISTS character_knowledge_character_idx ON character_knowledge(character_id);
CREATE INDEX IF NOT EXISTS character_knowledge_fact_idx ON character_knowledge(fact_id);
CREATE INDEX IF NOT EXISTS character_states_character_idx ON character_states(character_id);
CREATE INDEX IF NOT EXISTS character_states_chapter_idx ON character_states(as_of_chapter);

-- Indexes for foreshadowing
CREATE INDEX IF NOT EXISTS foreshadowing_series_idx ON foreshadowing(series_id);
CREATE INDEX IF NOT EXISTS foreshadowing_status_idx ON foreshadowing(status);
CREATE INDEX IF NOT EXISTS foreshadowing_planted_idx ON foreshadowing(planted_book, planted_chapter);

-- Indexes for story analysis
CREATE INDEX IF NOT EXISTS story_analyses_series_idx ON story_analyses(series_id);
CREATE INDEX IF NOT EXISTS story_analyses_type_idx ON story_analyses(analysis_type);
CREATE INDEX IF NOT EXISTS story_analyses_resolved_idx ON story_analyses(is_resolved);
CREATE INDEX IF NOT EXISTS world_rules_series_idx ON world_rules(series_id);
CREATE INDEX IF NOT EXISTS world_rules_category_idx ON world_rules(rule_category);

