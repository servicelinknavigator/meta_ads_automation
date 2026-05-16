"""
Sales transcript analyser.
Extracts voice-of-customer language from intake/sales call transcripts.
Results are stored in the transcripts table and injected into future AI prompts.
"""
from __future__ import annotations
import logging

import core.db as db
from core.ai_client import call_json, call_text

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Je bent een copywriter die voice-of-customer research doet voor Meta-advertenties. "
    "Extraheer letterlijke klantuitspraken, geen parafrasen. "
    "Antwoord ALLEEN met geldig JSON, geen uitleg eromheen."
)


def extract_voice_of_customer(transcript_text: str) -> dict:
    """
    Analyse a sales/intake transcript and extract:
    - exact_phrases: top 5 sentences usable directly as hook openers
    - objections: recurring objections prospects raised
    - yes_moments: what persuaded them (moments of agreement)
    - problem_words: exact words used to describe their problem

    Returns a dict with these four keys (values are newline-separated strings).
    """
    if not transcript_text or len(transcript_text) < 50:
        return {"error": "Transcript te kort of leeg."}

    # Truncate to avoid token limits (keep first 6000 chars)
    excerpt = transcript_text[:6000]

    prompt = f"""Analyseer dit verkoopgesprek/intake transcript en extraheer voice-of-customer inzichten.

TRANSCRIPT:
{excerpt}

Geef uitsluitend dit JSON object terug:
{{
  "exact_phrases": ["zin 1", "zin 2", "zin 3", "zin 4", "zin 5"],
  "objections": ["bezwaar 1", "bezwaar 2", "bezwaar 3"],
  "yes_moments": ["wat overtuigde hen 1", "wat overtuigde hen 2"],
  "problem_words": ["woord/frase 1", "woord/frase 2", "woord/frase 3", "woord/frase 4"]
}}

Regels:
- Gebruik ALLEEN letterlijke citaten of minimaal bewerkte uitspraken uit het transcript
- exact_phrases: openingszinnen die direct werken als hook in een Meta video-ad
- objections: bezwaren die prospects noemden
- yes_moments: de argumenten/bewijzen die de doorslag gaven
- problem_words: de exacte woorden waarmee zij hun probleem omschreven"""

    result = call_json(prompt, system=_SYSTEM, max_tokens=800)

    if "_error" in result:
        logger.error("extract_voice_of_customer AI error: %s", result["_error"])
        return {"error": result["_error"]}

    return {
        "exact_phrases": result.get("exact_phrases", []),
        "objections":    result.get("objections", []),
        "yes_moments":   result.get("yes_moments", []),
        "problem_words": result.get("problem_words", []),
    }


def analyze_and_save(client_id: int, transcript_text: str) -> dict:
    """
    Full pipeline: extract insights → format → save to DB.
    Returns the extracted data dict (plus 'transcript_id').
    """
    try:
        result = extract_voice_of_customer(transcript_text)

        if "error" in result:
            return result

        def _join(lst) -> str:
            return "\n".join(lst) if isinstance(lst, list) else str(lst)

        extracted_hooks      = _join(result.get("exact_phrases", []))
        extracted_objections = _join(result.get("objections", []))
        extracted_phrases    = _join(result.get("problem_words", []))

        tid = db.save_transcript(
            client_id         = client_id,
            transcript_text   = transcript_text,
            extracted_hooks   = extracted_hooks,
            extracted_objections = extracted_objections,
            extracted_phrases = extracted_phrases,
        )

        return {
            "transcript_id":   tid,
            "exact_phrases":   result.get("exact_phrases", []),
            "objections":      result.get("objections", []),
            "yes_moments":     result.get("yes_moments", []),
            "problem_words":   result.get("problem_words", []),
        }
    except Exception as e:
        logger.error("analyze_and_save failed for client %s: %s", client_id, e)
        return {"error": str(e)}
