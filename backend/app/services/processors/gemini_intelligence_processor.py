import json
import logging
from typing import List

logger = logging.getLogger(__name__)


class GeminiMeetingIntelligenceProcessor:
    """Gemini-based meeting intelligence extraction: summary, decisions, action items, sentiment."""

    # Try these models in order — first available will be used
    MODEL_NAMES = [
        "gemini-3.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def __init__(self):
        from app.core.config import settings
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key or self.api_key.startswith("your-"):
            raise ValueError("GEMINI_API_KEY not configured in settings")

        import google.generativeai as genai
        self.genai = genai
        self.genai.configure(api_key=self.api_key)

        self.model = None
        for model_name in self.MODEL_NAMES:
            try:
                self.model = self.genai.GenerativeModel(model_name)
                logger.info(f"Using Gemini model: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Model {model_name} not available: {e}")
                continue

        if self.model is None:
            raise ValueError("No available Gemini model found")

    async def analyze(self, meeting_id: str, segments: List[dict], summary_mode: str = "detailed") -> dict:
        """
        segments: list of dicts with keys start_time, end_time, speaker, text
        Returns a dict matching MeetingIntelligenceResponse fields (minus meeting_id).
        """
        import asyncio

        prompt = self._build_prompt(segments, summary_mode)

        response = await asyncio.to_thread(self.model.generate_content, prompt)
        result = self._parse_response(response.text)
        result["meeting_id"] = meeting_id
        return result

    def _build_prompt(self, segments: List[dict], summary_mode: str) -> str:
        transcript_lines = [
            f"[{seg.get('start_time', 0):.0f}s] {seg.get('speaker', 'Unknown')}: {seg.get('text', '')}"
            for seg in segments
        ]
        transcript_text = "\n".join(transcript_lines)

        mode_note = (
            "Keep summary_short concise (1-3 sentences) and summary_detailed comprehensive."
            if summary_mode == "detailed"
            else "Keep both summaries brief; summary_detailed can be a short paragraph."
        )

        return f"""You are an AI Meeting Intelligence engine. Read this timestamped, speaker-labeled
meeting transcript and extract structured business information.

Rules:
- Only report information actually present or clearly implied in the transcript.
- Never invent names, dates, or tasks that were not mentioned.
- Deadlines mentioned in natural language (e.g. "next Friday") go in deadline_raw.
  Only fill "deadline" with a resolved YYYY-MM-DD date if you can compute it confidently;
  otherwise leave it null.
- Return ONLY valid JSON, no markdown fences, no extra text.

Transcript:
{transcript_text}

{mode_note}

Return valid JSON in exactly this format:
{{
  "summary_short": "string",
  "summary_detailed": "string",
  "key_points": ["string", ...],
  "decisions": [{{"decision": "string", "timestamp": "string or null"}}],
  "action_items": [{{"task": "string", "owner": "string or null", "deadline": "YYYY-MM-DD or null", "deadline_raw": "string or null"}}],
  "unresolved_issues": [{{"issue": "string", "raised_by": "string or null"}}],
  "follow_up_items": ["string", ...],
  "sentiment": "string",
  "sentiment_notes": "string or null"
}}
"""

    def _parse_response(self, response_text: str) -> dict:
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    return json.loads(response_text[start_idx:end_idx + 1].strip())
            except (json.JSONDecodeError, ValueError):
                pass
            # Fallback so the endpoint doesn't hard-crash on a malformed LLM response
            logger.error(f"Failed to parse Gemini response as JSON: {response_text[:500]}")
            return {
                "summary_short": "",
                "summary_detailed": response_text.strip()[:2000],
                "key_points": [],
                "decisions": [],
                "action_items": [],
                "unresolved_issues": [],
                "follow_up_items": [],
                "sentiment": "unknown",
                "sentiment_notes": "Could not parse structured output from model.",
            }