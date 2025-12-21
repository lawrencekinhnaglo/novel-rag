"""
Story Analysis Service - LLM-powered analysis for novel development.

This service uses the LLM to make intelligent judgments about:
- Consistency checking (character knowledge, world rules, timeline)
- Foreshadowing suggestions
- Character voice analysis
- Plot hole detection
- Pacing analysis
- Chapter position context
"""

from typing import List, Dict, Any, Optional
from app.services.llm_service import get_llm_service
from app.database.postgres import AsyncSessionLocal
from sqlalchemy import text
import json
import logging

logger = logging.getLogger(__name__)


class StoryAnalysisService:
    """LLM-powered story analysis and consistency checking."""
    
    def __init__(self, provider: str = None):
        self.llm = get_llm_service(provider)
    
    # =========================================================================
    # CHAPTER POSITION CONTEXT (Improvement #4)
    # =========================================================================
    
    async def get_chapter_position_context(
        self,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> Dict[str, Any]:
        """Get context about where we are in the story for better AI responses."""
        async with AsyncSessionLocal() as db:
            # Get series info
            series_result = await db.execute(
                text("""
                    SELECT title, total_planned_books, themes, premise
                    FROM series WHERE id = :series_id
                """),
                {"series_id": series_id}
            )
            series = series_result.fetchone()
            
            # Get book info
            book_result = await db.execute(
                text("""
                    SELECT book_number, title, theme, status,
                           (SELECT COUNT(*) FROM chapters WHERE book_id = :book_id) as total_chapters
                    FROM books WHERE id = :book_id
                """),
                {"book_id": book_id}
            )
            book = book_result.fetchone()
            
            if not series or not book:
                return {}
            
            # Calculate position percentages
            series_progress = (book.book_number / series.total_planned_books) * 100
            book_progress = (chapter_number / max(book.total_chapters, 1)) * 100
            
            # Determine story phase
            if series_progress <= 20:
                series_phase = "opening"
                series_guidance = "Focus on world introduction, character establishment, planting seeds"
            elif series_progress <= 40:
                series_phase = "rising_action"
                series_guidance = "Deepen conflicts, develop relationships, reinforce foreshadowing"
            elif series_progress <= 60:
                series_phase = "midpoint"
                series_guidance = "Major revelations, turning points, stakes escalation"
            elif series_progress <= 80:
                series_phase = "climax_approach"
                series_guidance = "Begin resolving minor threads, build toward major confrontations"
            else:
                series_phase = "resolution"
                series_guidance = "Pay off foreshadowing, resolve arcs, deliver emotional conclusions"
            
            return {
                "series": {
                    "title": series.title,
                    "total_books": series.total_planned_books,
                    "current_book": book.book_number,
                    "progress_percent": round(series_progress, 1),
                    "phase": series_phase,
                    "themes": series.themes or [],
                    "premise": series.premise
                },
                "book": {
                    "title": book.title,
                    "theme": book.theme,
                    "chapter_number": chapter_number,
                    "total_chapters": book.total_chapters,
                    "progress_percent": round(book_progress, 1),
                    "status": book.status
                },
                "writing_guidance": series_guidance,
                "position_summary": f"Book {book.book_number}/{series.total_planned_books}, Chapter {chapter_number}"
            }
    
    # =========================================================================
    # CHARACTER KNOWLEDGE CHECK (Improvement #2)
    # =========================================================================
    
    async def check_character_knowledge(
        self,
        character_name: str,
        proposed_action: str,
        current_chapter: int,
        series_id: int
    ) -> Dict[str, Any]:
        """
        Use LLM to check if a character's action is consistent with what they know.
        """
        async with AsyncSessionLocal() as db:
            # Get character info
            char_result = await db.execute(
                text("""
                    SELECT id, name, personality, secrets
                    FROM character_profiles 
                    WHERE series_id = :series_id AND name ILIKE :name
                """),
                {"series_id": series_id, "name": f"%{character_name}%"}
            )
            character = char_result.fetchone()
            
            if not character:
                return {"error": f"Character '{character_name}' not found"}
            
            # Get what this character knows
            knowledge_result = await db.execute(
                text("""
                    SELECT sf.fact_description, ck.learned_in_chapter, ck.certainty
                    FROM character_knowledge ck
                    JOIN story_facts sf ON ck.fact_id = sf.id
                    WHERE ck.character_id = :char_id
                    AND ck.learned_in_chapter <= :current_chapter
                    ORDER BY ck.learned_in_chapter DESC
                """),
                {"char_id": character.id, "current_chapter": current_chapter}
            )
            known_facts = knowledge_result.fetchall()
            
            # Get facts they DON'T know yet (only approved facts)
            unknown_result = await db.execute(
                text("""
                    SELECT sf.fact_description, sf.established_in_chapter
                    FROM story_facts sf
                    WHERE sf.series_id = :series_id
                    AND sf.id NOT IN (
                        SELECT fact_id FROM character_knowledge 
                        WHERE character_id = :char_id
                    )
                    AND sf.is_secret = TRUE
                    AND (sf.verification_status = 'approved' OR sf.verification_status IS NULL)
                """),
                {"series_id": series_id, "char_id": character.id}
            )
            unknown_facts = unknown_result.fetchall()
        
        # Build prompt for LLM analysis
        prompt = f"""Analyze if this character action is consistent with their knowledge.

CHARACTER: {character.name}
PERSONALITY: {character.personality or 'Not specified'}

PROPOSED ACTION/DIALOGUE:
"{proposed_action}"

CURRENT CHAPTER: {current_chapter}

WHAT {character.name.upper()} KNOWS (as of Chapter {current_chapter}):
{self._format_facts(known_facts) if known_facts else "No specific facts recorded yet."}

SECRETS {character.name.upper()} DOES NOT KNOW:
{self._format_unknown_facts(unknown_facts) if unknown_facts else "None recorded."}

ANALYSIS REQUIRED:
1. Is this action/dialogue consistent with what the character knows?
2. Does it accidentally reveal information they shouldn't have?
3. Is it in character with their personality?
4. Any suggestions to make it more authentic?

Respond in JSON format:
{{
    "is_consistent": true/false,
    "knowledge_issues": ["list of any knowledge inconsistencies"],
    "personality_match": true/false,
    "personality_notes": "notes on personality fit",
    "suggestions": ["list of improvement suggestions"],
    "overall_verdict": "APPROVED" or "NEEDS_REVISION" or "WARNING"
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3  # Lower temperature for more consistent analysis
        )
        
        try:
            # Try to parse JSON from response
            result = self._extract_json(response)
            result["character"] = character.name
            result["chapter"] = current_chapter
            return result
        except:
            return {
                "character": character.name,
                "chapter": current_chapter,
                "raw_analysis": response,
                "parse_error": True
            }
    
    # =========================================================================
    # FORESHADOWING ANALYSIS (Improvement #3)
    # =========================================================================
    
    async def analyze_foreshadowing_opportunities(
        self,
        chapter_content: str,
        series_id: int,
        current_book: int,
        current_chapter: int
    ) -> Dict[str, Any]:
        """
        Use LLM to identify foreshadowing opportunities and check for payoffs.
        """
        async with AsyncSessionLocal() as db:
            # Get planted seeds that haven't paid off (only approved ones)
            planted_result = await db.execute(
                text("""
                    SELECT id, title, planted_text, intended_payoff, subtlety, status
                    FROM foreshadowing
                    WHERE series_id = :series_id
                    AND status IN ('planted', 'reinforced')
                    AND (payoff_book IS NULL OR payoff_book >= :current_book)
                    AND (verification_status = 'approved' OR verification_status IS NULL)
                    ORDER BY planted_book, planted_chapter
                """),
                {"series_id": series_id, "current_book": current_book}
            )
            pending_seeds = planted_result.fetchall()
            
            # Get series themes
            series_result = await db.execute(
                text("SELECT themes, premise FROM series WHERE id = :series_id"),
                {"series_id": series_id}
            )
            series = series_result.fetchone()
        
        prompt = f"""Analyze this chapter for foreshadowing opportunities.

CHAPTER CONTENT (excerpt):
{chapter_content[:3000]}...

SERIES THEMES: {series.themes if series else 'Not specified'}
CURRENT POSITION: Book {current_book}, Chapter {current_chapter}

PENDING FORESHADOWING SEEDS TO POTENTIALLY REINFORCE OR PAY OFF:
{self._format_seeds(pending_seeds) if pending_seeds else "No pending seeds recorded."}

ANALYSIS REQUIRED:
1. Identify any existing foreshadowing in this chapter
2. Suggest opportunities to plant new seeds
3. Identify opportunities to reinforce existing seeds
4. Check if any seeds could be paid off here

Respond in JSON format:
{{
    "existing_foreshadowing": [
        {{"text": "quoted text", "foreshadows": "what it hints at", "subtlety": 1-5}}
    ],
    "new_seed_opportunities": [
        {{"suggestion": "what to plant", "how": "suggested text", "payoff_timing": "when to pay off"}}
    ],
    "reinforcement_opportunities": [
        {{"seed_title": "which seed", "suggestion": "how to reinforce"}}
    ],
    "potential_payoffs": [
        {{"seed_title": "which seed", "how": "how to pay it off naturally"}}
    ],
    "overall_foreshadowing_health": "rating and notes"
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        
        try:
            return self._extract_json(response)
        except:
            return {"raw_analysis": response, "parse_error": True}
    
    # =========================================================================
    # CONSISTENCY CHECK (Uses World Rules)
    # =========================================================================
    
    async def check_consistency(
        self,
        content: str,
        series_id: int,
        check_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive consistency check using LLM.
        check_types: ['world_rules', 'character', 'timeline', 'plot']
        """
        if check_types is None:
            check_types = ['world_rules', 'character', 'timeline']
        
        async with AsyncSessionLocal() as db:
            context = {}
            
            if 'world_rules' in check_types:
                rules_result = await db.execute(
                    text("""
                        SELECT rule_category, rule_name, rule_description, exceptions, is_hard_rule
                        FROM world_rules
                        WHERE series_id = :series_id
                        AND (verification_status = 'approved' OR verification_status IS NULL)
                        ORDER BY rule_category
                    """),
                    {"series_id": series_id}
                )
                context['world_rules'] = rules_result.fetchall()
            
            if 'character' in check_types:
                chars_result = await db.execute(
                    text("""
                        SELECT name, personality, speech_patterns
                        FROM character_profiles
                        WHERE series_id = :series_id
                        AND (verification_status = 'approved' OR verification_status IS NULL)
                    """),
                    {"series_id": series_id}
                )
                context['characters'] = chars_result.fetchall()
        
        prompt = f"""Perform a consistency check on this content.

CONTENT TO CHECK:
{content[:4000]}

ESTABLISHED WORLD RULES:
{self._format_world_rules(context.get('world_rules', []))}

CHARACTER PROFILES:
{self._format_characters(context.get('characters', []))}

CHECK FOR:
1. World rule violations (magic system, technology, society rules)
2. Character inconsistencies (behavior, speech patterns, knowledge)
3. Timeline impossibilities
4. Plot contradictions

Respond in JSON format:
{{
    "issues": [
        {{
            "type": "world_rule|character|timeline|plot",
            "severity": "minor|moderate|major|critical",
            "description": "what's wrong",
            "location": "where in the text",
            "suggestion": "how to fix"
        }}
    ],
    "warnings": ["potential issues that might not be problems"],
    "all_clear": true/false,
    "summary": "overall assessment"
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            result = self._extract_json(response)
            # Store analysis in database
            await self._save_analysis(
                series_id=series_id,
                analysis_type="consistency_check",
                query=content[:500],
                result=result
            )
            return result
        except:
            return {"raw_analysis": response, "parse_error": True}
    
    # =========================================================================
    # "WHAT DOES X KNOW?" QUERY (Improvement #2)
    # =========================================================================
    
    async def query_character_knowledge(
        self,
        character_name: str,
        question: str,
        as_of_chapter: int,
        series_id: int
    ) -> Dict[str, Any]:
        """
        Ask what a character knows about something at a specific point.
        """
        async with AsyncSessionLocal() as db:
            # Get character
            char_result = await db.execute(
                text("""
                    SELECT id, name, personality, background, secrets
                    FROM character_profiles 
                    WHERE series_id = :series_id AND name ILIKE :name
                """),
                {"series_id": series_id, "name": f"%{character_name}%"}
            )
            character = char_result.fetchone()
            
            if not character:
                return {"error": f"Character '{character_name}' not found"}
            
            # Get all knowledge up to this chapter
            knowledge_result = await db.execute(
                text("""
                    SELECT sf.fact_description, sf.fact_category, 
                           ck.learned_in_chapter, ck.certainty, ck.learned_how
                    FROM character_knowledge ck
                    JOIN story_facts sf ON ck.fact_id = sf.id
                    WHERE ck.character_id = :char_id
                    AND ck.learned_in_chapter <= :chapter
                """),
                {"char_id": character.id, "chapter": as_of_chapter}
            )
            knowledge = knowledge_result.fetchall()
            
            # Get character state at this chapter
            state_result = await db.execute(
                text("""
                    SELECT emotional_state, physical_state, location
                    FROM character_states
                    WHERE character_id = :char_id AND as_of_chapter <= :chapter
                    ORDER BY as_of_chapter DESC LIMIT 1
                """),
                {"char_id": character.id, "chapter": as_of_chapter}
            )
            state = state_result.fetchone()
        
        prompt = f"""Answer this question about what a character knows.

CHARACTER: {character.name}
QUESTION: "{question}"
AS OF: Chapter {as_of_chapter}

CHARACTER BACKGROUND:
{character.background or 'Not specified'}

CHARACTER'S SECRETS (things they know but hide):
{character.secrets or 'None recorded'}

FACTS {character.name.upper()} KNOWS BY CHAPTER {as_of_chapter}:
{self._format_knowledge(knowledge)}

CHARACTER'S CURRENT STATE:
{f"Emotional: {state.emotional_state}, Location: {state.location}" if state else "Not recorded"}

Based on this information, answer the question from the character's perspective.
Consider:
1. What they definitely know
2. What they might suspect or deduce
3. What they definitely don't know
4. How they would feel about this topic

Respond in JSON format:
{{
    "knows": ["facts they definitely know relevant to this question"],
    "suspects": ["things they might guess or deduce"],
    "doesnt_know": ["relevant things they don't know"],
    "emotional_reaction": "how they'd feel about this topic",
    "would_share": true/false,
    "reasoning": "explanation of the analysis",
    "answer_summary": "direct answer to the question"
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        
        try:
            result = self._extract_json(response)
            result["character"] = character.name
            result["as_of_chapter"] = as_of_chapter
            return result
        except:
            return {
                "character": character.name,
                "as_of_chapter": as_of_chapter,
                "raw_analysis": response
            }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _format_facts(self, facts) -> str:
        if not facts:
            return "None"
        return "\n".join([
            f"- {f.fact_description} (learned Ch.{f.learned_in_chapter}, {f.certainty})"
            for f in facts
        ])
    
    def _format_unknown_facts(self, facts) -> str:
        if not facts:
            return "None"
        return "\n".join([
            f"- {f.fact_description} (established Ch.{f.established_in_chapter})"
            for f in facts[:10]  # Limit to 10
        ])
    
    def _format_seeds(self, seeds) -> str:
        if not seeds:
            return "None"
        return "\n".join([
            f"- [{s.status}] {s.title}: {s.planted_text[:100]}... → {s.intended_payoff or 'payoff TBD'}"
            for s in seeds
        ])
    
    def _format_world_rules(self, rules) -> str:
        if not rules:
            return "No world rules established."
        return "\n".join([
            f"- [{r.rule_category}] {r.rule_name}: {r.rule_description}" +
            (f" (Exceptions: {', '.join(r.exceptions)})" if r.exceptions else "")
            for r in rules
        ])
    
    def _format_characters(self, chars) -> str:
        if not chars:
            return "No characters profiled."
        return "\n".join([
            f"- {c.name}: {c.personality or 'No personality defined'}" +
            (f" (Speech: {c.speech_patterns})" if c.speech_patterns else "")
            for c in chars
        ])
    
    def _format_knowledge(self, knowledge) -> str:
        if not knowledge:
            return "No facts recorded."
        return "\n".join([
            f"- [{k.fact_category}] {k.fact_description} " +
            f"(Ch.{k.learned_in_chapter}, {k.learned_how or 'unknown how'}, {k.certainty})"
            for k in knowledge
        ])
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        import re
        # Try to find JSON block
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No JSON found in response")
    
    async def _save_analysis(
        self,
        series_id: int,
        analysis_type: str,
        query: str,
        result: Dict,
        book_id: int = None,
        chapter_id: int = None
    ):
        """Save analysis to database for reference."""
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("""
                        INSERT INTO story_analyses 
                        (series_id, book_id, chapter_id, analysis_type, query, 
                         analysis_result, issues_found, suggestions, severity)
                        VALUES (:series_id, :book_id, :chapter_id, :analysis_type, :query,
                                :result, :issues, :suggestions, :severity)
                    """),
                    {
                        "series_id": series_id,
                        "book_id": book_id,
                        "chapter_id": chapter_id,
                        "analysis_type": analysis_type,
                        "query": query,
                        "result": json.dumps(result),
                        "issues": json.dumps(result.get("issues", [])),
                        "suggestions": json.dumps(result.get("suggestions", [])),
                        "severity": "warning" if result.get("issues") else "info"
                    }
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")


def get_story_analysis_service(provider: str = None) -> StoryAnalysisService:
    """Get story analysis service instance."""
    return StoryAnalysisService(provider)

