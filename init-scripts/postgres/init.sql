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
    chat_session_id UUID, -- Links to originating chat session (for chat-saved entries)
    is_synced_session BOOLEAN DEFAULT FALSE, -- If TRUE, this entry auto-updates with new messages
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
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
    knowledge_sync_enabled BOOLEAN DEFAULT FALSE, -- Auto-sync new messages to knowledge
    synced_knowledge_id INTEGER, -- ID of the knowledge_base entry being synced to
    last_synced_message_id INTEGER, -- Last message ID that was synced
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

-- Message feedback (like/dislike) for Q&A pairs
-- This tracks user feedback on assistant responses and their corresponding user questions
CREATE TABLE IF NOT EXISTS message_feedback (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    assistant_message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('like', 'dislike')),
    user_question TEXT NOT NULL, -- Cached copy of the user's question
    assistant_response TEXT NOT NULL, -- Cached copy of the assistant's response
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(assistant_message_id) -- One feedback per assistant message
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
CREATE INDEX IF NOT EXISTS message_feedback_session_idx ON message_feedback(session_id);
CREATE INDEX IF NOT EXISTS message_feedback_type_idx ON message_feedback(session_id, feedback_type);
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

-- =====================================================
-- ENHANCEMENT: PLOT STRUCTURE & BEAT SHEETS
-- =====================================================

-- Plot beat templates (three-act, hero's journey, etc.)
CREATE TABLE IF NOT EXISTS plot_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    beat_count INTEGER,
    structure JSONB NOT NULL, -- Array of beat definitions
    genre_tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default plot templates
INSERT INTO plot_templates (name, description, beat_count, structure, genre_tags) VALUES
('Three-Act Structure', 'Classic three-act dramatic structure', 12, 
 '[{"name":"Hook","act":1,"percentage":0},{"name":"Setup","act":1,"percentage":5},{"name":"Inciting Incident","act":1,"percentage":10},{"name":"First Plot Point","act":1,"percentage":25},{"name":"Rising Action","act":2,"percentage":30},{"name":"Midpoint","act":2,"percentage":50},{"name":"Complications","act":2,"percentage":60},{"name":"Second Plot Point","act":2,"percentage":75},{"name":"Dark Night of Soul","act":3,"percentage":80},{"name":"Climax","act":3,"percentage":90},{"name":"Resolution","act":3,"percentage":95},{"name":"Denouement","act":3,"percentage":100}]',
 ARRAY['general', 'drama', 'thriller']),
('Hero''s Journey', 'Joseph Campbell''s monomyth structure', 17,
 '[{"name":"Ordinary World","act":1,"percentage":0},{"name":"Call to Adventure","act":1,"percentage":8},{"name":"Refusal of Call","act":1,"percentage":12},{"name":"Meeting the Mentor","act":1,"percentage":17},{"name":"Crossing Threshold","act":1,"percentage":25},{"name":"Tests, Allies, Enemies","act":2,"percentage":30},{"name":"Approach to Inmost Cave","act":2,"percentage":45},{"name":"Ordeal","act":2,"percentage":50},{"name":"Reward","act":2,"percentage":60},{"name":"The Road Back","act":3,"percentage":70},{"name":"Resurrection","act":3,"percentage":85},{"name":"Return with Elixir","act":3,"percentage":95}]',
 ARRAY['fantasy', 'adventure', 'action']),
('Kishōtenketsu', 'Four-act East Asian narrative structure', 4,
 '[{"name":"Ki (Introduction)","act":1,"percentage":0},{"name":"Shō (Development)","act":2,"percentage":25},{"name":"Ten (Twist)","act":3,"percentage":50},{"name":"Ketsu (Conclusion)","act":4,"percentage":75}]',
 ARRAY['manga', 'light_novel', 'asian']),
('Seven-Point Story', 'Dan Wells seven-point story structure', 7,
 '[{"name":"Hook","act":1,"percentage":0},{"name":"Plot Turn 1","act":1,"percentage":15},{"name":"Pinch Point 1","act":2,"percentage":30},{"name":"Midpoint","act":2,"percentage":50},{"name":"Pinch Point 2","act":2,"percentage":70},{"name":"Plot Turn 2","act":3,"percentage":85},{"name":"Resolution","act":3,"percentage":100}]',
 ARRAY['general', 'fantasy'])
ON CONFLICT (name) DO NOTHING;

-- Plot beats for a specific series/book
CREATE TABLE IF NOT EXISTS plot_beats (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES plot_templates(id),
    beat_name VARCHAR(200) NOT NULL,
    beat_description TEXT,
    target_chapter INTEGER,
    actual_chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    order_index INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'planned', -- planned, drafted, completed
    notes TEXT,
    ai_suggestions TEXT, -- AI-generated suggestions for this beat
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Plot variations (what-if scenarios)
CREATE TABLE IF NOT EXISTS plot_variations (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    source_chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    variation_title VARCHAR(500) NOT NULL,
    what_if_premise TEXT NOT NULL, -- "What if the hero died here?"
    ai_analysis TEXT, -- AI-generated impact analysis
    consequences JSONB DEFAULT '[]', -- Structured list of consequences
    is_explored BOOLEAN DEFAULT FALSE, -- Has user explored this further?
    exploration_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- ENHANCEMENT: TIMELINE MANAGEMENT
-- =====================================================

-- Timeline events
CREATE TABLE IF NOT EXISTS timeline_events (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    event_name VARCHAR(500) NOT NULL,
    event_description TEXT,
    story_date VARCHAR(200), -- Flexible date format (e.g., "Year 1, Day 45")
    story_date_sortable INTEGER, -- Numeric for sorting (e.g., days from story start)
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    character_ids INTEGER[], -- Characters involved
    location VARCHAR(500),
    event_type VARCHAR(50) DEFAULT 'plot', -- plot, character, world, background
    importance VARCHAR(20) DEFAULT 'normal', -- minor, normal, major, critical
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Timeline tracks (for parallel storylines)
CREATE TABLE IF NOT EXISTS timeline_tracks (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    track_name VARCHAR(200) NOT NULL, -- e.g., "Main Plot", "Character A's Journey"
    track_color VARCHAR(20) DEFAULT '#8b5cf6', -- For UI display
    character_id INTEGER REFERENCES character_profiles(id) ON DELETE SET NULL,
    is_main_track BOOLEAN DEFAULT FALSE,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Link events to tracks
CREATE TABLE IF NOT EXISTS timeline_event_tracks (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES timeline_events(id) ON DELETE CASCADE,
    track_id INTEGER REFERENCES timeline_tracks(id) ON DELETE CASCADE,
    UNIQUE(event_id, track_id)
);

-- =====================================================
-- ENHANCEMENT: RESEARCH LIBRARY
-- =====================================================

-- Research items (external references)
CREATE TABLE IF NOT EXISTS research_items (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    source_url TEXT,
    source_type VARCHAR(50) DEFAULT 'web', -- web, book, article, personal_note
    content TEXT, -- Full content or notes
    summary TEXT, -- AI-generated summary
    category VARCHAR(100), -- historical, cultural, technical, inspiration
    tags TEXT[],
    embedding vector(384),
    is_verified BOOLEAN DEFAULT FALSE, -- User verified accuracy
    chat_session_id UUID, -- If saved from chat
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);-- Link research to story elements
CREATE TABLE IF NOT EXISTS research_links (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research_items(id) ON DELETE CASCADE,
    link_type VARCHAR(50) NOT NULL, -- character, location, world_rule, chapter
    linked_table VARCHAR(100) NOT NULL, -- Table name
    linked_id INTEGER NOT NULL, -- ID in linked table
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- ENHANCEMENT: STORY BRANCHES (Alternative Storylines)
-- =====================================================

-- Story branches (alternative timelines)
CREATE TABLE IF NOT EXISTS story_branches (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    branch_name VARCHAR(500) NOT NULL,
    branch_description TEXT,
    branch_point_chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    divergence_description TEXT, -- What's different in this branch?
    is_active BOOLEAN DEFAULT TRUE,
    is_merged BOOLEAN DEFAULT FALSE, -- Has been merged into main
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Branch chapters (chapters in alternative branches)
CREATE TABLE IF NOT EXISTS branch_chapters (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER REFERENCES story_branches(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    chapter_number INTEGER,
    word_count INTEGER,
    embedding vector(384),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- ENHANCEMENT: WRITING GOALS & PROGRESS
-- =====================================================

-- Writing goals
CREATE TABLE IF NOT EXISTS writing_goals (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    goal_type VARCHAR(50) NOT NULL, -- daily, weekly, monthly, total, deadline
    target_words INTEGER,
    target_chapters INTEGER,
    deadline DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Writing sessions (track writing activity)
CREATE TABLE IF NOT EXISTS writing_sessions (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    session_date DATE DEFAULT CURRENT_DATE,
    words_written INTEGER DEFAULT 0,
    duration_minutes INTEGER,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily word count tracking
CREATE TABLE IF NOT EXISTS daily_word_counts (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    count_date DATE NOT NULL,
    words_added INTEGER DEFAULT 0,
    words_deleted INTEGER DEFAULT 0,
    net_words INTEGER DEFAULT 0,
    chapters_worked_on INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(series_id, count_date)
);

-- =====================================================
-- ENHANCEMENT: CHARACTER VOICE & INTERVIEW
-- =====================================================

-- Character voice samples (dialogue examples)
CREATE TABLE IF NOT EXISTS character_voice_samples (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES character_profiles(id) ON DELETE CASCADE,
    sample_text TEXT NOT NULL,
    context TEXT, -- What situation is this dialogue from?
    emotion VARCHAR(50), -- angry, happy, sad, neutral
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    is_canonical BOOLEAN DEFAULT TRUE, -- Is this an approved voice sample?
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Character interview sessions
CREATE TABLE IF NOT EXISTS character_interviews (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES character_profiles(id) ON DELETE CASCADE,
    interview_transcript TEXT NOT NULL, -- Full Q&A transcript
    extracted_traits JSONB DEFAULT '{}', -- Traits discovered in interview
    interview_focus VARCHAR(100), -- background, relationships, goals, fears
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- ENHANCEMENT: AI SUGGESTIONS LOG
-- =====================================================

-- Track AI suggestions for review/learning
CREATE TABLE IF NOT EXISTS ai_suggestions (
    id SERIAL PRIMARY KEY,
    series_id INTEGER REFERENCES series(id) ON DELETE CASCADE,
    suggestion_type VARCHAR(100) NOT NULL, -- plot, character, dialogue, scene, etc.
    context TEXT, -- What prompted this suggestion
    suggestion_content TEXT NOT NULL,
    was_accepted BOOLEAN,
    was_modified BOOLEAN,
    user_feedback TEXT,
    chat_session_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- NEW INDEXES FOR ENHANCEMENT TABLES
-- =====================================================

CREATE INDEX IF NOT EXISTS plot_beats_series_idx ON plot_beats(series_id);
CREATE INDEX IF NOT EXISTS plot_beats_book_idx ON plot_beats(book_id);
CREATE INDEX IF NOT EXISTS plot_variations_series_idx ON plot_variations(series_id);

CREATE INDEX IF NOT EXISTS timeline_events_series_idx ON timeline_events(series_id);
CREATE INDEX IF NOT EXISTS timeline_events_date_idx ON timeline_events(story_date_sortable);
CREATE INDEX IF NOT EXISTS timeline_tracks_series_idx ON timeline_tracks(series_id);

CREATE INDEX IF NOT EXISTS research_items_series_idx ON research_items(series_id);
CREATE INDEX IF NOT EXISTS research_items_category_idx ON research_items(category);
CREATE INDEX IF NOT EXISTS research_items_embedding_idx ON research_items 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS story_branches_series_idx ON story_branches(series_id);
CREATE INDEX IF NOT EXISTS branch_chapters_branch_idx ON branch_chapters(branch_id);
CREATE INDEX IF NOT EXISTS branch_chapters_embedding_idx ON branch_chapters 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS writing_goals_series_idx ON writing_goals(series_id);
CREATE INDEX IF NOT EXISTS writing_sessions_series_idx ON writing_sessions(series_id);
CREATE INDEX IF NOT EXISTS writing_sessions_date_idx ON writing_sessions(session_date);
CREATE INDEX IF NOT EXISTS daily_word_counts_series_idx ON daily_word_counts(series_id);
CREATE INDEX IF NOT EXISTS daily_word_counts_date_idx ON daily_word_counts(count_date);

CREATE INDEX IF NOT EXISTS character_voice_samples_char_idx ON character_voice_samples(character_id);
CREATE INDEX IF NOT EXISTS character_interviews_char_idx ON character_interviews(character_id);

CREATE INDEX IF NOT EXISTS ai_suggestions_series_idx ON ai_suggestions(series_id);
CREATE INDEX IF NOT EXISTS ai_suggestions_type_idx ON ai_suggestions(suggestion_type);

-- =====================================================
-- CHAPTER VERSION CONTROL (Added for version history)
-- =====================================================

-- Chapter versions for tracking revisions
CREATE TABLE IF NOT EXISTS chapter_versions (
    id SERIAL PRIMARY KEY,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title VARCHAR(500),
    content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    change_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(chapter_id, version_number)
);

-- Index for fast version lookups
CREATE INDEX IF NOT EXISTS idx_chapter_versions_chapter_id ON chapter_versions(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chapter_versions_created_at ON chapter_versions(created_at DESC);
