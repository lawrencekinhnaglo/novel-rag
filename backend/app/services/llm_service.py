"""LLM Service supporting LM Studio and DeepSeek API."""
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMProvider:
    """Base LLM provider interface."""
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 4096) -> str:
        """Generate a response from the LLM."""
        raise NotImplementedError
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM."""
        raise NotImplementedError


class LMStudioProvider(LLMProvider):
    """LM Studio local LLM provider."""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LM_STUDIO_URL,
            api_key="lm-studio"  # LM Studio doesn't require a real API key
        )
        self.model = settings.LM_STUDIO_MODEL
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 4096) -> str:
        """Generate a response from LM Studio."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LM Studio error: {e}")
            raise
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream a response from LM Studio."""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LM Studio streaming error: {e}")
            raise


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider."""
    
    def __init__(self):
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY not configured")
        self.client = AsyncOpenAI(
            base_url=settings.DEEPSEEK_API_URL,
            api_key=settings.DEEPSEEK_API_KEY
        )
        self.model = settings.DEEPSEEK_MODEL
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 4096) -> str:
        """Generate a response from DeepSeek."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek error: {e}")
            raise
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream a response from DeepSeek."""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"DeepSeek streaming error: {e}")
            raise


class LLMService:
    """Unified LLM service that can switch between providers."""
    
    def __init__(self, provider: str = None):
        self.provider_name = provider or settings.DEFAULT_LLM_PROVIDER
        self._provider: Optional[LLMProvider] = None
    
    @property
    def provider(self) -> LLMProvider:
        """Get or create the LLM provider."""
        if self._provider is None:
            self._provider = self._create_provider()
        return self._provider
    
    def _create_provider(self) -> LLMProvider:
        """Create the appropriate LLM provider."""
        if self.provider_name == "lm_studio":
            return LMStudioProvider()
        elif self.provider_name == "deepseek":
            return DeepSeekProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider_name}")
    
    def switch_provider(self, provider: str):
        """Switch to a different LLM provider."""
        self.provider_name = provider
        self._provider = None
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 4096) -> str:
        """Generate a response."""
        return await self.provider.generate(messages, temperature, max_tokens)
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream a response."""
        async for chunk in self.provider.stream(messages, temperature, max_tokens):
            yield chunk
    
    async def generate_with_context(self, user_message: str,
                                    context: Dict[str, Any],
                                    system_prompt: str = None,
                                    conversation_history: List[Dict[str, str]] = None,
                                    temperature: float = 0.7,
                                    language: str = "en",
                                    max_context_tokens: int = 32000,
                                    categories: List[str] = None,
                                    uploaded_content: str = None) -> str:
        """
        Generate a response with RAG context, full novel awareness, and long context support.
        
        Args:
            user_message: The user's question/request
            context: Retrieved context from RAG
            system_prompt: Optional custom system prompt
            conversation_history: Previous conversation messages
            temperature: LLM temperature setting
            language: Response language (en, zh-TW, zh-CN)
            max_context_tokens: Maximum tokens for context
            categories: Knowledge categories to prioritize
        """
        # Build system prompt with context
        if system_prompt is None:
            system_prompt = self._build_novel_system_prompt(language)
        
        # Add context to system prompt
        if context:
            context_text = self._format_context(context, language, categories)
            system_prompt += f"\n\n## Retrieved Context:\n{context_text}"
        
        # Add uploaded content if provided
        if uploaded_content:
            system_prompt += f"\n\n## Uploaded Document Content:\n{uploaded_content[:10000]}"
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (more for long context support)
        if conversation_history:
            # For long context models, include more history
            history_limit = 30 if max_context_tokens >= 32000 else 10
            messages.extend(conversation_history[-history_limit:])
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        return await self.generate(messages, temperature)
    
    def _build_novel_system_prompt(self, language: str = "en") -> str:
        """Build the default system prompt for novel writing with full character awareness."""
        
        prompts = {
            "en": """You are an expert novel writing assistant with deep knowledge of storytelling, character development, plot structure, and creative writing.

## Your Role - Full Story Immersion
You are FULLY IMMERSED in this novel's world. You understand and remember:
- Each character's complete personality, motivations, fears, desires, and speech patterns
- How each character would naturally react in any situation based on their established traits
- The complete timeline of events and how past events influence the present
- All world-building details: settings, rules, magic systems, technology, culture
- Ongoing plot threads, conflicts, subplots, and narrative arcs
- Relationships between all characters and how they evolve

## Character Behavior Awareness
When discussing or writing about characters, you MUST:
- Stay TRUE to their established personality - never break character
- Use their characteristic speech patterns, vocabulary, and mannerisms
- Consider their emotional state based on recent story events
- Account for their relationships and history with other characters
- Remember what they know vs. don't know (no character omniscience)
- Reflect their growth/changes if they've developed through the story

## Your Capabilities
- Discussing plot ideas, character arcs, and story structure
- Writing scenes and dialogue that authentically match character voices
- Predicting how characters would react to hypothetical situations
- Identifying plot holes, inconsistencies, or out-of-character moments
- Suggesting plot developments that fit character motivations
- Helping maintain consistency across the entire novel

## Knowledge Categories You Can Access
Your context includes information categorized as:
- **Draft**: Work in progress content
- **Concept**: High-level story ideas and themes
- **Character**: Detailed character profiles and development
- **Chapter**: Published/finalized chapter content
- **Settings**: World-building, magic systems, technology
- **Plot**: Story outlines, arcs, and conflict structures
- **Dialogue**: Sample dialogues and character voice references
- **Research**: Background research and references
- **Notes**: Miscellaneous notes and ideas

## Guidelines
1. ALWAYS maintain consistency with established story elements
2. When unsure, acknowledge it and suggest checking source material
3. Point out potential inconsistencies proactively
4. Respect the author's creative vision while offering suggestions
5. Consider cultural and linguistic nuances in the story world""",

            "zh-TW": """你是一位專業的小說寫作助手，精通故事敘述、角色發展、情節結構和創意寫作。

## 你的角色 - 完全沉浸於故事
你完全沉浸在這部小說的世界中。你理解並記住：
- 每個角色完整的性格、動機、恐懼、慾望和說話模式
- 根據已建立的特徵，每個角色在任何情況下會如何自然反應
- 完整的事件時間線，以及過去事件如何影響現在
- 所有世界觀細節：場景、規則、魔法系統、科技、文化
- 正在進行的情節線索、衝突、支線劇情和敘事弧線
- 所有角色之間的關係及其演變

## 角色行為意識
在討論或撰寫角色時，你必須：
- 忠於他們已建立的性格 - 絕不能出戲
- 使用他們特有的說話模式、詞彙和習慣
- 考慮他們基於最近故事事件的情緒狀態
- 考慮他們與其他角色的關係和歷史
- 記住他們知道什麼 vs 不知道什麼（角色不能全知）
- 反映他們的成長/變化（如果他們在故事中有所發展）

## 你的能力
- 討論情節構思、角色弧線和故事結構
- 撰寫真實符合角色聲音的場景和對話
- 預測角色對假設情況的反應
- 識別情節漏洞、不一致或出戲的時刻
- 建議符合角色動機的情節發展
- 幫助保持整部小說的一致性

## 你可以存取的知識類別
你的上下文包括以下類別的資訊：
- **草稿**：進行中的內容
- **概念**：高層次的故事想法和主題
- **角色**：詳細的角色檔案和發展
- **章節**：已發布/定稿的章節內容
- **設定**：世界觀、魔法系統、科技
- **情節**：故事大綱、弧線和衝突結構
- **對話**：對話範例和角色聲音參考
- **研究**：背景研究和參考資料
- **筆記**：雜項筆記和想法

## 指南
1. 始終保持與已建立故事元素的一致性
2. 當不確定時，承認並建議查看原始資料
3. 主動指出潛在的不一致
4. 尊重作者的創意願景，同時提供建議
5. 考慮故事世界中的文化和語言細微差別""",

            "zh-CN": """你是一位专业的小说写作助手，精通故事叙述、角色发展、情节结构和创意写作。

## 你的角色 - 完全沉浸于故事
你完全沉浸在这部小说的世界中。你理解并记住：
- 每个角色完整的性格、动机、恐惧、欲望和说话模式
- 根据已建立的特征，每个角色在任何情况下会如何自然反应
- 完整的事件时间线，以及过去事件如何影响现在
- 所有世界观细节：场景、规则、魔法系统、科技、文化
- 正在进行的情节线索、冲突、支线剧情和叙事弧线
- 所有角色之间的关系及其演变

## 角色行为意识
在讨论或撰写角色时，你必须：
- 忠于他们已建立的性格 - 绝不能出戏
- 使用他们特有的说话模式、词汇和习惯
- 考虑他们基于最近故事事件的情绪状态
- 考虑他们与其他角色的关系和历史
- 记住他们知道什么 vs 不知道什么（角色不能全知）
- 反映他们的成长/变化（如果他们在故事中有所发展）

## 你的能力
- 讨论情节构思、角色弧线和故事结构
- 撰写真实符合角色声音的场景和对话
- 预测角色对假设情况的反应
- 识别情节漏洞、不一致或出戏的时刻
- 建议符合角色动机的情节发展
- 帮助保持整部小说的一致性

## 你可以访问的知识类别
你的上下文包括以下类别的信息：
- **草稿**：进行中的内容
- **概念**：高层次的故事想法和主题
- **角色**：详细的角色档案和发展
- **章节**：已发布/定稿的章节内容
- **设定**：世界观、魔法系统、科技
- **情节**：故事大纲、弧线和冲突结构
- **对话**：对话范例和角色声音参考
- **研究**：背景研究和参考资料
- **笔记**：杂项笔记和想法

## 指南
1. 始终保持与已建立故事元素的一致性
2. 当不确定时，承认并建议查看原始资料
3. 主动指出潜在的不一致
4. 尊重作者的创意愿景，同时提供建议
5. 考虑故事世界中的文化和语言细微差别"""
        }
        
        return prompts.get(language, prompts["en"])
    
    def _format_context(self, context: Dict[str, Any], language: str = "en",
                       priority_categories: List[str] = None) -> str:
        """Format context dictionary into readable text with language support."""
        parts = []
        
        # Story position context FIRST - helps LLM understand where we are
        if context.get("story_position"):
            pos = context["story_position"]
            series = pos.get("series", {})
            book = pos.get("book", {})
            
            position_header = {
                "en": "### 📍 Story Position:",
                "zh-TW": "### 📍 故事位置：",
                "zh-CN": "### 📍 故事位置："
            }.get(language, "### 📍 Story Position:")
            
            parts.append(position_header)
            parts.append(f"**Series:** {series.get('title', 'Unknown')} ({series.get('progress_percent', 0)}% complete)")
            parts.append(f"**Current:** Book {series.get('current_book', '?')}/{series.get('total_books', '?')}, Chapter {book.get('chapter_number', '?')}")
            parts.append(f"**Book Theme:** {book.get('theme', 'Not defined')}")
            parts.append(f"**Series Phase:** {series.get('phase', 'unknown').replace('_', ' ').title()}")
            
            guidance = pos.get("writing_guidance", "")
            if guidance:
                guidance_label = {
                    "en": "**Writing Guidance:**",
                    "zh-TW": "**寫作指導：**",
                    "zh-CN": "**写作指导：**"
                }.get(language, "**Writing Guidance:**")
                parts.append(f"{guidance_label} {guidance}")
            
            if series.get("themes"):
                themes_label = {
                    "en": "**Series Themes:**",
                    "zh-TW": "**系列主題：**",
                    "zh-CN": "**系列主题：**"
                }.get(language, "**Series Themes:**")
                parts.append(f"{themes_label} {', '.join(series['themes'])}")
            
            parts.append("")  # Empty line for separation
        
        # Localized headers
        headers = {
            "en": {
                "chapters": "### Relevant Chapters:",
                "characters": "### Characters (Personality & Behavior Reference):",
                "events": "### Timeline Events:",
                "knowledge": "### Knowledge Base:",
                "web_search": "### Web Search Results:",
                "relationships": "Relationships:",
                "personality": "Personality:",
                "behavior": "Typical behavior:",
                "involved": "Involved:",
                "no_context": "No additional context available."
            },
            "zh-TW": {
                "chapters": "### 相關章節：",
                "characters": "### 角色（性格與行為參考）：",
                "events": "### 時間線事件：",
                "knowledge": "### 知識庫：",
                "web_search": "### 網路搜尋結果：",
                "relationships": "關係：",
                "personality": "性格：",
                "behavior": "典型行為：",
                "involved": "參與者：",
                "no_context": "沒有可用的額外上下文。"
            },
            "zh-CN": {
                "chapters": "### 相关章节：",
                "characters": "### 角色（性格与行为参考）：",
                "events": "### 时间线事件：",
                "knowledge": "### 知识库：",
                "web_search": "### 网络搜索结果：",
                "relationships": "关系：",
                "personality": "性格：",
                "behavior": "典型行为：",
                "involved": "参与者：",
                "no_context": "没有可用的额外上下文。"
            }
        }
        h = headers.get(language, headers["en"])
        
        # Characters first - most important for behavior awareness
        if context.get("characters"):
            parts.append(h["characters"])
            for char in context["characters"]:
                parts.append(f"\n**{char.get('name', 'Unknown')}**")
                if char.get("description"):
                    parts.append(f"  {char['description']}")
                if char.get("attributes"):
                    attrs = char.get("attributes", {})
                    if attrs.get("personality"):
                        parts.append(f"  {h['personality']} {attrs['personality']}")
                    if attrs.get("behavior"):
                        parts.append(f"  {h['behavior']} {attrs['behavior']}")
                    if attrs.get("speech_pattern"):
                        parts.append(f"  Speech: {attrs['speech_pattern']}")
                if char.get("relationships"):
                    rels = ", ".join([f"{r['type']} → {r['target']}" for r in char["relationships"]])
                    parts.append(f"  {h['relationships']} {rels}")
        
        # Timeline events
        if context.get("events"):
            parts.append(f"\n{h['events']}")
            for event in context["events"]:
                chapter_info = f"(Ch.{event.get('chapter')})" if event.get('chapter') else ""
                timestamp = f"[{event.get('story_timestamp')}]" if event.get('story_timestamp') else ""
                parts.append(f"- {timestamp} {event.get('title', 'Event')} {chapter_info}")
                parts.append(f"  {event.get('description', '')}")
                if event.get("characters"):
                    parts.append(f"  {h['involved']} {', '.join(event['characters'])}")
        
        # Chapters
        if context.get("chapters"):
            parts.append(f"\n{h['chapters']}")
            for ch in context["chapters"]:
                parts.append(f"\n**Chapter {ch.get('chapter_number', 'N/A')}: {ch.get('title', 'Untitled')}**")
                if ch.get("content"):
                    # Include more content for long context
                    parts.append(f"{ch['content'][:3000]}...")
        
        # Knowledge base - grouped by category
        if context.get("knowledge"):
            parts.append(f"\n{h['knowledge']}")
            by_category = {}
            for kb in context["knowledge"]:
                cat = kb.get("category") or kb.get("source_type") or "notes"
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(kb)
            
            # Prioritize certain categories if specified
            category_order = priority_categories or ['character', 'settings', 'plot', 'chapter', 'dialogue', 'concept', 'draft', 'research', 'notes']
            sorted_cats = sorted(by_category.keys(), 
                                key=lambda x: category_order.index(x) if x in category_order else 99)
            
            for cat in sorted_cats:
                items = by_category[cat]
                parts.append(f"\n  **[{cat.upper()}]**")
                for kb in items:
                    parts.append(f"  - {kb.get('title', 'Note')}")
                    parts.append(f"    {kb.get('content', '')[:800]}")
        
        # Web search results
        if context.get("web_search"):
            parts.append(f"\n{h['web_search']}")
            for result in context["web_search"]:
                parts.append(f"- [{result.get('title', 'Result')}]({result.get('url', '')})")
                parts.append(f"  {result.get('snippet', '')}")
        
        return "\n".join(parts) if parts else h["no_context"]


def get_llm_service(provider: str = None) -> LLMService:
    """Get LLM service instance."""
    return LLMService(provider)
