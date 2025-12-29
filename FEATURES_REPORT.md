# Novel RAG - AI-Powered Novel Writing Assistant

## Comprehensive Feature Report & Methodology Analysis

### Executive Summary

**Novel RAG** is an advanced AI-powered writing assistant designed specifically for **long-form fiction writers**. It combines Retrieval-Augmented Generation (RAG), knowledge graph technologies, and local LLM integration to help authors maintain consistency, track complex narratives, and receive intelligent writing assistance throughout the novel-writing process.

---

## 🏠 Core Architecture

### Technology Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React + TypeScript + Vite | Modern, responsive UI |
| **Backend** | FastAPI (Python) | Async API services |
| **Vector DB** | Qdrant | Semantic search & RAG |
| **Graph DB** | Neo4j | Character relationships |
| **SQL DB** | PostgreSQL | Structured data storage |
| **Cache** | Redis | Session & context caching |
| **LLM** | DeepSeek / Ollama / LM Studio | AI-powered responses |

---

## 📚 Feature Analysis

### 1. Story Workspace Portal (NEW)

**Purpose**: Provides a unified "project management" view for each novel series.

**Key Capabilities**:
- **Series Selection Sidebar**: Quick access to all your story series
- **Statistics Dashboard**: Real-time metrics on books, chapters, words, characters, knowledge entries, foreshadowing seeds, world rules, and story facts
- **Tabbed Navigation**: Overview, Chapters, Characters, Knowledge, Chat Sessions, Analysis
- **Quick Actions**: One-click access to Chat with AI, Write Chapter, and Story Graph
- **Cross-linking**: Link knowledge base entries and chat sessions to specific series

**How it helps**:
> For long novels spanning multiple books, the workspace provides a single view of all related content. Authors can see at a glance how many chapters are complete, how many foreshadowing seeds are planted, and jump directly to relevant chat sessions about the story.

---

### 2. AI Chat with RAG Context

**Purpose**: Intelligent conversation about your novel with full context awareness.

**Key Capabilities**:
- **Context-Aware Responses**: Uses RAG to pull relevant novel excerpts
- **Multi-Provider Support**: DeepSeek, Ollama, or LM Studio
- **Streaming Responses**: Real-time text generation
- **Knowledge Graph Integration**: Includes character relationships in context
- **Like/Dislike Feedback**: Mark helpful responses to improve future context
- **Automatic Context Caching**: Liked Q&A pairs are sent with new questions
- **Session Management**: Organize conversations by topic
- **Multi-language Support**: English, Traditional Chinese, Simplified Chinese

**How it helps**:
> When asking "What does Character A know about the prophecy?", the AI searches through all uploaded chapters, finds relevant passages, checks the knowledge graph for relationships, and provides an answer based on actual story content rather than making things up.

---

### 3. Story Management

**Purpose**: Track series, books, foreshadowing, and world rules.

**Key Capabilities**:

#### Series & Books
- Create multiple series with planned book counts
- Track each book's status (planning, drafting, editing, published)
- Monitor word count progress toward targets
- Define themes and premises

#### Foreshadowing Tracker
- **Plant Seeds**: Record foreshadowing elements with:
  - Location (book, chapter)
  - Subtlety level (1-5 stars)
  - Intended payoff description
- **Track Status**: planted → reinforced → paid_off
- **AI Analysis**: Detect unfired Chekhov's guns

#### World Rules Engine
- Define hard rules (magic systems, physics)
- Track exceptions to rules
- Consistency checking against new content
- Categories: magic, social, physical, temporal

**How it helps**:
> In a 500,000-word fantasy series, it's easy to forget that you established in Book 1 that teleportation requires blood sacrifice. The world rules engine flags inconsistencies when you write a scene where a character teleports casually.

---

### 4. Chapter Management

**Purpose**: Write and organize chapters with AI assistance.

**Key Capabilities**:
- **Chapter Outline**: Plan chapters before writing
- **POV Character Tracking**: Know whose perspective each chapter uses
- **Word Count Monitoring**: Track progress per chapter and book
- **Summary Generation**: AI-generated chapter summaries
- **Import from Documents**: Upload existing chapter drafts
- **Auto-extraction**: AI extracts characters, facts, and foreshadowing from chapter content

**How it helps**:
> Upload a rough draft, and the system automatically identifies new characters mentioned, extracts story facts, and suggests potential foreshadowing elements for you to review and approve.

---

### 5. Knowledge Base

**Purpose**: Store and retrieve any information about your novel world.

**Key Capabilities**:
- **Multiple Source Types**: character notes, world-building, plot outlines, research
- **Categorization**: Organize by category and tags
- **Semantic Search**: Find information by meaning, not just keywords
- **Vector Embeddings**: All content is vectorized for RAG retrieval
- **Save from Chat**: One-click save AI responses to knowledge base
- **Series Linking**: Connect knowledge entries to specific series

**How it helps**:
> You can store detailed information about your magic system, then when chatting with the AI, it automatically retrieves relevant rules when you ask about magical limitations.

---

### 6. Story Graph (Neo4j)

**Purpose**: Visualize and query character relationships.

**Key Capabilities**:
- **Character Nodes**: Create characters with descriptions
- **Relationship Edges**: Define relationships (family, rivalry, romance, etc.)
- **Interactive Visualization**: Force-directed graph display
- **Query Relationships**: "Find all enemies of Character A"
- **AI-Assisted Analysis**: Detect relationship patterns

**How it helps**:
> In complex novels with large casts, the story graph helps track who knows whom, family trees, faction allegiances, and political alliances that would be impossible to keep straight manually.

---

### 7. Verification Hub

**Purpose**: Review and approve AI-extracted content.

**Key Capabilities**:
- **Pending Queue**: All AI extractions go through verification
- **Approval Workflow**: Accept, modify, or reject suggestions
- **Categories**: Characters, World Rules, Foreshadowing, Story Facts
- **Batch Operations**: Approve multiple items at once
- **Edit Before Approval**: Modify AI suggestions before accepting

**How it helps**:
> When AI extracts that "Sarah is John's sister" from your chapter, you can verify it's correct before it becomes part of the knowledge graph. This prevents AI hallucinations from corrupting your story data.

---

### 8. Document Upload

**Purpose**: Import existing manuscripts and research.

**Key Capabilities**:
- **Supported Formats**: PDF, DOCX, TXT, EPUB
- **Automatic Processing**: Extract text and create embeddings
- **Chapter Detection**: Identify chapter boundaries
- **Metadata Extraction**: Pull title, author, creation date
- **Chunking Strategies**: Intelligent text segmentation for RAG

**How it helps**:
> Import your existing 50-chapter manuscript, and the system processes it into searchable chunks, making all previous content available for AI context.

---

### 9. AI Analysis Tools

**Purpose**: Use LLM to analyze your writing.

**Key Capabilities**:

#### Consistency Checker
- Detects contradictions with established world rules
- Flags timeline inconsistencies
- Identifies character behavior anomalies

#### Character Knowledge Query
- "What does Character X know at Chapter Y?"
- Considers only events character has witnessed
- Tracks information flow between characters

#### Foreshadowing Analysis
- Suggests payoff opportunities for planted seeds
- Identifies potential foreshadowing in new chapters
- Recommends reinforcement timing

**How it helps**:
> Before publishing a chapter where a character reveals secret information, query the system to ensure that character could actually know that secret at that point in the story.

---

### 10. Settings & Configuration

**Purpose**: Customize the writing environment.

**Key Capabilities**:
- **LLM Provider Selection**: Switch between DeepSeek, Ollama, LM Studio
- **Temperature Control**: Adjust creativity vs. consistency
- **Token Limits**: Configure response length
- **Language Preference**: Set default language
- **RAG Settings**: Enable/disable knowledge retrieval
- **Graph Integration**: Toggle character graph context

---

## 📊 Methodology: How Novel RAG Helps Write Long Novels

### The Challenge of Long-Form Fiction

Writing a long novel (100,000+ words) presents unique challenges:

1. **Consistency**: Tracking details across hundreds of pages
2. **Continuity**: Remembering what characters know when
3. **Complexity**: Managing multiple plotlines and character arcs
4. **Coherence**: Maintaining tone and style throughout
5. **Completeness**: Paying off foreshadowing and resolving threads

### The Novel RAG Approach

#### 1. **Centralized Knowledge Repository**

Instead of scattered notes across files and notebooks, Novel RAG centralizes all story information in a searchable, interconnected database.

```
Traditional Approach:
- Notes in Word docs
- Character sheets in Excel
- Research in browser bookmarks
- Memory for everything else

Novel RAG Approach:
- Knowledge Base (semantic search)
- Character Graph (relationship queries)
- World Rules Engine (consistency checking)
- Everything searchable by AI
```

#### 2. **Context-Aware AI Assistance**

Unlike generic AI writing tools, Novel RAG's AI has access to your specific story context through RAG technology.

```
Generic AI:
"Write a scene where the hero confronts the villain"
→ Generic, disconnected scene

Novel RAG:
Same prompt + RAG context
→ Scene referencing established character traits, 
   past events, world rules, and relationships
```

#### 3. **Proactive Consistency Checking**

Rather than catching errors during editing, Novel RAG flags potential issues during writing.

```
Writing: "John teleported across the room"
System: ⚠️ World Rule Violation
        "Teleportation requires blood sacrifice" (Book 1, Ch 3)
        Did John perform the ritual?
```

#### 4. **Foreshadowing Management**

Track every seed you plant and ensure they all pay off.

```
Dashboard View:
├── Book 1: 12 seeds planted, 3 paid off, 9 pending
├── Book 2: 8 seeds planted, 5 paid off, 3 pending  
└── Book 3: 5 pending seeds need resolution before finale
```

#### 5. **Character Knowledge Tracking**

Prevent characters from knowing things they shouldn't.

```
Query: "What does Sarah know about the murder?"
At Chapter 10: 
- Sarah knows: victim was stabbed, found by gardener
- Sarah doesn't know: killer's identity, murder weapon location
```

---

## 🔄 Recommended Workflow

### Pre-Writing Phase
1. Create your **Series** in Story Workspace
2. Define **World Rules** for your setting
3. Create initial **Character Nodes** in Story Graph
4. Upload any existing **research or outlines**

### Writing Phase
1. Open **Story Workspace** for your series
2. Create chapter outline in **Chapters** page
3. Write with **AI Chat** for brainstorming
4. Plant **Foreshadowing Seeds** as you write
5. Use **Consistency Checker** before finalizing

### Post-Chapter
1. Upload chapter to **Document Upload**
2. Review AI extractions in **Verification Hub**
3. Update **Character Relationships** in Story Graph
4. Save useful AI insights to **Knowledge Base**
5. Check **Foreshadowing** status

### Revision Phase
1. Use **Knowledge Query** to verify facts
2. Run **Consistency Check** on edited sections
3. Review **Foreshadowing Dashboard** for loose threads
4. Update **World Rules** if story evolved

---

## 💡 Best Practices

### 1. Seed Your Knowledge Base Early
Upload outlines, character sheets, and world-building documents before starting. This gives the AI maximum context from day one.

### 2. Verify AI Extractions Promptly
Don't let the verification queue grow too large. Regular review prevents AI errors from propagating.

### 3. Use Tags Consistently
Create a tagging system (e.g., `magic-system`, `protagonist`, `book-2`) and apply it consistently for better retrieval.

### 4. Like Helpful AI Responses
The feedback system improves context quality. Consistently liking good responses builds a better context cache.

### 5. Regular Foreshadowing Audits
Before major plot points, review pending foreshadowing seeds to identify payoff opportunities.

---

## 🚀 Conclusion

Novel RAG transforms the challenging task of writing long-form fiction into a managed, supported process. By combining:

- **RAG technology** for context-aware AI assistance
- **Knowledge graphs** for relationship tracking  
- **Structured databases** for story metadata
- **Verification workflows** for accuracy assurance

...authors can focus on creativity while the system handles consistency, continuity, and complexity management.

The **Story Workspace Portal** serves as the central hub, bringing all these capabilities together in a unified interface where authors can see their entire novel project at a glance and navigate to any tool they need.

---

## 📈 Feature Summary Table

| Feature | Purpose | Key Benefit |
|---------|---------|-------------|
| Story Workspace | Project overview | Unified series management |
| AI Chat | Creative assistance | Context-aware brainstorming |
| Story Management | Series/book tracking | Progress monitoring |
| Foreshadowing | Seed tracking | Narrative completeness |
| World Rules | Consistency rules | Avoid contradictions |
| Knowledge Base | Information storage | Searchable world-building |
| Story Graph | Relationships | Character network clarity |
| Verification Hub | AI QA | Prevent AI errors |
| Chapter Management | Writing organization | Structured composition |
| Document Upload | Import content | Process existing work |

---

*Report generated: December 29, 2025*
*Version: 1.0*

