"""Hermes Skills Base - Context providers for LLM"""
import logging

log = logging.getLogger("hermes_skills")

class HermesSkill:
    """Base class for Hermes context providers.
    
    Each skill's prepare(text) method fetches real-time data and
    returns a dict with context to inject into the LLM prompt.
    """
    name = "base"
    description = ""

    def prepare(self, text: str) -> dict:
        """Fetch context for LLM.
        
        Returns:
            dict with keys:
              - "context": str - formatted context data for LLM prompt
              - "action": dict or None - optional post-LLM action
              - "skip_llm": bool - if True, use reply directly (for simple tasks)
              - "reply": str - direct reply if skip_llm=True
        """
        return {"context": "", "action": None, "skip_llm": False, "reply": ""}
