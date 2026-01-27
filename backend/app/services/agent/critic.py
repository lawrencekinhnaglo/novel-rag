"""
Self-Critic - Reviews and critiques agent output.

The critic evaluates generated content against quality criteria
and worldbuilding consistency, suggesting improvements.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CritiqueCategory(str, Enum):
    """Categories of critique."""
    CONSISTENCY = "consistency"      # Matches worldbuilding
    QUALITY = "quality"              # Writing quality
    FLOW = "flow"                    # Narrative flow
    CHARACTER = "character"          # Character consistency
    PLOT = "plot"                    # Plot logic
    PACING = "pacing"                # Narrative pacing
    DIALOGUE = "dialogue"            # Dialogue quality
    DESCRIPTION = "description"      # Scene descriptions


@dataclass
class CritiqueItem:
    """A single critique item."""
    category: CritiqueCategory
    severity: str  # minor, moderate, major, critical
    issue: str
    suggestion: str
    location: Optional[str] = None  # Where in the content
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "issue": self.issue,
            "suggestion": self.suggestion,
            "location": self.location
        }


@dataclass
class CritiqueResult:
    """Result of a critique session."""
    satisfactory: bool
    score: float  # 0-10
    items: List[CritiqueItem]
    summary: str
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "satisfactory": self.satisfactory,
            "score": self.score,
            "items": [item.to_dict() for item in self.items],
            "summary": self.summary,
            "recommendations": self.recommendations
        }


class SelfCritic:
    """
    Reviews and critiques agent-generated content.
    
    Uses LLM to evaluate content quality and consistency,
    providing actionable feedback for improvement.
    """
    
    def __init__(self, llm_service=None, min_score: float = 7.0):
        self.llm_service = llm_service
        self.min_score = min_score  # Minimum score to consider satisfactory
    
    async def review(self, 
                    content: str, 
                    content_type: str,
                    context: Dict[str, Any] = None,
                    focus_areas: List[CritiqueCategory] = None) -> CritiqueResult:
        """
        Review content and provide critique.
        
        Args:
            content: The content to review
            content_type: Type of content (chapter, scene, outline, etc.)
            context: Worldbuilding and character context
            focus_areas: Specific areas to focus on
        
        Returns:
            CritiqueResult with detailed feedback
        """
        if not self.llm_service:
            return CritiqueResult(
                satisfactory=True,
                score=7.0,
                items=[],
                summary="自動審查需要 LLM 服務",
                recommendations=[]
            )
        
        focus = focus_areas or [
            CritiqueCategory.CONSISTENCY,
            CritiqueCategory.QUALITY,
            CritiqueCategory.FLOW
        ]
        
        # Build critique prompt
        prompt = self._build_critique_prompt(content, content_type, context, focus)
        
        try:
            critique_response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": self._get_critic_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse critique response
            result = self._parse_critique_response(critique_response)
            
            # Determine if satisfactory
            result.satisfactory = result.score >= self.min_score
            
            return result
            
        except Exception as e:
            logger.error(f"Critique failed: {e}")
            return CritiqueResult(
                satisfactory=True,
                score=6.0,
                items=[],
                summary=f"審查過程出錯：{str(e)}",
                recommendations=["建議手動審查內容"]
            )
    
    async def quick_check(self, content: str, worldbuilding: List[Dict]) -> Dict[str, Any]:
        """
        Quick consistency check against worldbuilding.
        Returns potential issues without full critique.
        """
        if not self.llm_service or not worldbuilding:
            return {"issues": [], "consistent": True}
        
        worldbuilding_text = "\n".join([
            f"- {item.get('title', '')}: {item.get('content', '')[:200]}"
            for item in worldbuilding[:10]
        ])
        
        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": """你是一致性檢查器。
快速檢查內容是否與世界觀設定矛盾。
只列出明確的矛盾，不要推測。
格式：每個問題一行，用 "- " 開頭。如果沒有問題，回覆 "無矛盾"。"""},
                    {"role": "user", "content": f"""世界觀設定：
{worldbuilding_text}

要檢查的內容：
{content[:3000]}"""}
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            if "無矛盾" in response or not response.strip():
                return {"issues": [], "consistent": True}
            
            issues = [line.strip("- ").strip() for line in response.split("\n") if line.strip().startswith("-")]
            return {"issues": issues, "consistent": len(issues) == 0}
            
        except Exception as e:
            logger.error(f"Quick check failed: {e}")
            return {"issues": [], "consistent": True}
    
    async def compare_versions(self, 
                              original: str, 
                              improved: str, 
                              improvement_goal: str) -> Dict[str, Any]:
        """
        Compare original and improved versions.
        Determine if the improvement actually made it better.
        """
        if not self.llm_service:
            return {
                "improved": True,
                "analysis": "需要 LLM 服務進行比較",
                "keep_improved": True
            }
        
        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": """你是內容改進評估專家。
比較原始版本和改進版本，判斷改進是否成功。

評估：
1. 改進目標是否達成？
2. 是否有新問題產生？
3. 整體品質是提升還是下降？

最後給出建議：保留改進版本 或 保留原始版本。"""},
                    {"role": "user", "content": f"""改進目標：{improvement_goal}

原始版本：
{original[:2000]}

改進版本：
{improved[:2000]}"""}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            keep_improved = "保留改進" in response or "improved" in response.lower()
            
            return {
                "improved": keep_improved,
                "analysis": response,
                "keep_improved": keep_improved
            }
            
        except Exception as e:
            logger.error(f"Version comparison failed: {e}")
            return {
                "improved": True,
                "analysis": f"比較失敗：{str(e)}",
                "keep_improved": True
            }
    
    def _get_critic_system_prompt(self) -> str:
        """Get the system prompt for critique."""
        return """你是一個專業的小說編輯和批評家。你的任務是客觀、嚴格地評估小說內容。

評估維度：
1. **一致性** (Consistency): 是否符合已建立的世界觀和角色設定？
2. **品質** (Quality): 文筆、描寫、對話的整體品質
3. **流暢度** (Flow): 敘事是否流暢，過渡是否自然
4. **角色** (Character): 角色行為和對話是否符合其性格
5. **情節** (Plot): 情節是否合理，有無邏輯漏洞
6. **節奏** (Pacing): 敘事節奏是否恰當
7. **對話** (Dialogue): 對話是否自然、有特色
8. **描寫** (Description): 場景和動作描寫是否生動

評分標準（1-10）：
- 9-10: 優秀，可直接發布
- 7-8: 良好，小修即可
- 5-6: 一般，需要修改
- 3-4: 較差，需要大改
- 1-2: 很差，建議重寫

請提供：
1. 總評分（1-10）
2. 各維度的具體問題（標明嚴重程度：minor/moderate/major/critical）
3. 具體改進建議
4. 總結評語"""
    
    def _build_critique_prompt(self, 
                              content: str, 
                              content_type: str, 
                              context: Dict[str, Any],
                              focus: List[CritiqueCategory]) -> str:
        """Build the critique prompt."""
        parts = [f"請評估以下{content_type}內容："]
        
        # Add focus areas
        focus_text = "、".join([f.value for f in focus])
        parts.append(f"\n重點評估：{focus_text}")
        
        # Add context if available
        if context:
            if context.get("worldbuilding"):
                parts.append("\n\n【世界觀參考】")
                for item in context["worldbuilding"][:5]:
                    parts.append(f"- {item.get('title', '')}: {item.get('content', '')[:150]}")
            
            if context.get("characters"):
                parts.append("\n\n【角色參考】")
                for char in context["characters"][:3]:
                    parts.append(f"- {char.get('name', '')}: {char.get('description', '')[:100]}")
        
        # Add content to review
        parts.append(f"\n\n【待評估內容】\n{content}")
        
        return "\n".join(parts)
    
    def _parse_critique_response(self, response: str) -> CritiqueResult:
        """Parse the LLM's critique response into structured result."""
        items = []
        recommendations = []
        score = 7.0
        summary = ""
        
        lines = response.split("\n")
        
        for line in lines:
            line = line.strip()
            
            # Extract score
            if "評分" in line or "分數" in line or "/10" in line:
                try:
                    import re
                    numbers = re.findall(r'(\d+\.?\d*)', line)
                    if numbers:
                        score = min(float(numbers[0]), 10.0)
                except:
                    pass
            
            # Extract issues (lines starting with - or •)
            if line.startswith("-") or line.startswith("•") or line.startswith("*"):
                issue_text = line.lstrip("-•* ").strip()
                
                # Determine severity
                severity = "moderate"
                if any(word in issue_text for word in ["嚴重", "重大", "critical", "major"]):
                    severity = "major"
                elif any(word in issue_text for word in ["輕微", "minor", "小問題"]):
                    severity = "minor"
                
                # Determine category
                category = CritiqueCategory.QUALITY
                if any(word in issue_text for word in ["一致", "矛盾", "設定"]):
                    category = CritiqueCategory.CONSISTENCY
                elif any(word in issue_text for word in ["角色", "人物", "性格"]):
                    category = CritiqueCategory.CHARACTER
                elif any(word in issue_text for word in ["情節", "邏輯", "劇情"]):
                    category = CritiqueCategory.PLOT
                elif any(word in issue_text for word in ["節奏", "pacing"]):
                    category = CritiqueCategory.PACING
                elif any(word in issue_text for word in ["對話", "dialogue"]):
                    category = CritiqueCategory.DIALOGUE
                elif any(word in issue_text for word in ["描寫", "場景"]):
                    category = CritiqueCategory.DESCRIPTION
                elif any(word in issue_text for word in ["流暢", "過渡"]):
                    category = CritiqueCategory.FLOW
                
                items.append(CritiqueItem(
                    category=category,
                    severity=severity,
                    issue=issue_text,
                    suggestion=""
                ))
            
            # Extract recommendations
            if "建議" in line and "：" in line:
                rec = line.split("：", 1)[-1].strip()
                if rec:
                    recommendations.append(rec)
        
        # Extract summary (usually at the end)
        if "總結" in response or "總評" in response:
            try:
                summary_start = response.rfind("總結") if "總結" in response else response.rfind("總評")
                summary = response[summary_start:summary_start+300].strip()
            except:
                summary = response[-300:].strip()
        else:
            summary = response[-300:].strip() if len(response) > 300 else response
        
        return CritiqueResult(
            satisfactory=score >= self.min_score,
            score=score,
            items=items,
            summary=summary,
            recommendations=recommendations[:5]  # Limit recommendations
        )
