"""
AI-powered Debate Engine — generates intelligent, expert-level debate.

Each agent has a distinct persona with deep domain expertise. They:
- Build on previous speakers' points (agree/counter/nuance)
- Cite evidence, frameworks, and real-world examples
- Ask questions of opponents
- Concede valid points while strengthening their position
- Progress naturally from opening → rebuttal → synthesis
"""

import json
import logging
from typing import Any

from services.ai_client import generate, generate_json

logger = logging.getLogger(__name__)

# ── Persona definitions ───────────────────────────────────────────────────────

PROPONENT_SYSTEM = (
    "You are an expert advocate and strategist. You argue IN FAVOR of the proposition "
    "with conviction, evidence, and nuance. Your style:\n"
    "- Open with a strong thesis supported by data or established frameworks\n"
    "- Directly address and counter the opponent's specific arguments by name\n"
    "- Concede minor points gracefully, then explain why they don't undermine your position\n"
    "- Use concrete examples, statistics, analogies, and thought experiments\n"
    "- Ask probing questions that expose weaknesses in the opposing view\n"
    "- Build a cumulative case — each round should add NEW arguments, not just repeat\n"
    "- Write in a natural, conversational expert tone — not robotic or formulaic\n"
    "- Reference specific studies, historical precedents, or industry data when relevant\n"
    "- Keep responses focused: 2-4 paragraphs, punchy and persuasive"
)

OPPONENT_SYSTEM = (
    "You are a sharp critical thinker and devil's advocate. You argue AGAINST the proposition "
    "with rigor, counter-evidence, and strategic concessions. Your style:\n"
    "- Challenge the core assumptions — don't just attack surface arguments\n"
    "- Present alternative explanations and counterexamples\n"
    "- Acknowledge valid points from the proponent, then show why they're insufficient\n"
    "- Use risk analysis, cost-benefit reasoning, and precautionary principles\n"
    "- Ask pointed questions that reveal blind spots in the proponent's case\n"
    "- Escalate concerns each round — introduce new risks, complications, edge cases\n"
    "- Write in a natural, conversational expert tone — not robotic or formulaic\n"
    "- Cite real-world failures, unintended consequences, and minority reports\n"
    "- Keep responses focused: 2-4 paragraphs, incisive and substantive"
)

MODERATOR_SYSTEM = (
    "You are a brilliant debate moderator and synthesis expert. Your role:\n"
    "- Summarize the strongest points from BOTH sides with intellectual honesty\n"
    "- Identify the core tension or disagreement that separates the two positions\n"
    "- Point out where arguments are talking past each other or using different assumptions\n"
    "- Highlight areas of surprising agreement or common ground\n"
    "- Ask clarifying questions that push both sides toward resolution\n"
    "- In early rounds: frame the debate, define terms, set expectations\n"
    "- In middle rounds: identify patterns, challenge weak arguments from both sides\n"
    "- In final rounds: synthesize, find the thread that connects everything\n"
    "- Write in a measured, analytical tone with genuine curiosity\n"
    "- Keep responses focused: 2-3 paragraphs, insightful and balanced"
)

CONCLUSION_SYSTEM = (
    "You are an expert policy analyst writing a definitive debate conclusion. "
    "Synthesize the entire debate into a structured analysis. Be specific — "
    "reference the actual arguments made, not generic platitudes. "
    "Include concrete recommendations with conditions and caveats."
)

# ── Round-stage prompts ───────────────────────────────────────────────────────

PROPONENT_PROMPTS = {
    "opening": (
        "This is the OPENING round. Present your case for: **{topic}**\n\n"
        "Start with your central thesis, then support it with 2-3 key arguments. "
        "Use evidence, frameworks, or real-world examples. Be bold but substantive. "
        "Set the terms of the debate."
    ),
    "rebuttal": (
        "The opponent just argued:\n>>> {last_opponent}\n\n"
        "And the moderator noted:\n>>> {last_moderator}\n\n"
        "Counter the opponent's specific points. Don't just repeat your opening — "
        "advance your case by addressing their arguments directly. "
        "Concede what's valid, then explain why your position still holds. "
        "Introduce at least one NEW argument or evidence."
    ),
    "synthesis": (
        "Here's where the debate stands:\n"
        "Opponent's latest: >>> {last_opponent}\n"
        "Moderator's latest: >>> {last_moderator}\n\n"
        "This is the closing round. Don't just summarize — make your strongest, "
        "most focused argument yet. Address the core disagreement directly. "
        "If the opponent made any valid points, incorporate them into a stronger position. "
        "End with a clear, compelling call to action."
    ),
}

OPPONENT_PROMPTS = {
    "opening": (
        "This is the OPENING round. Present your case against: **{topic}**\n\n"
        "Challenge the core premise. Present 2-3 counter-arguments with evidence, "
        "risk analysis, or alternative explanations. Be rigorous and specific — "
        "vague skepticism isn't enough."
    ),
    "rebuttal": (
        "The proponent just argued:\n>>> {last_proponent}\n\n"
        "And the moderator noted:\n>>> {last_moderator}\n\n"
        "Counter their specific claims. Where are they overstating? What evidence "
        "are they ignoring? Introduce a NEW risk or counter-example they haven't "
        "considered. Don't just say 'it's risky' — show exactly HOW and WHY."
    ),
    "synthesis": (
        "Here's where the debate stands:\n"
        "Proponent's latest: >>> {last_proponent}\n"
        "Moderator's latest: >>> {last_moderator}\n\n"
        "Closing round. Make your strongest case. If the proponent has valid points, "
        "acknowledge them but explain why they're insufficient or come with unacceptable "
        "trade-offs. Offer your alternative vision clearly."
    ),
}

MODERATOR_PROMPTS = {
    "opening": (
        "Frame this debate on: **{topic}**\n\n"
        "Define the key terms and the real question at stake. "
        "What are the core values or assumptions in tension? "
        "Set the stage for a productive discussion."
    ),
    "rebuttal": (
        "The proponent argued:\n>>> {last_proponent}\n\n"
        "The opponent countered:\n>>> {last_opponent}\n\n"
        "Summarize the strongest points from each side. "
        "Where are they talking past each other? "
        "What question would resolve the most disagreement?"
    ),
    "synthesis": (
        "Final synthesis. Here are the latest positions:\n"
        "Proponent: >>> {last_proponent}\n"
        "Opponent: >>> {last_opponent}\n\n"
        "What's the core unresolved tension? "
        "Is there a synthesis that respects both sides' valid concerns? "
        "Give your honest assessment of where the evidence lands."
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_stage(round_num: int, max_rounds: int) -> str:
    """Determine debate stage from round number."""
    if round_num <= 1:
        return "opening"
    elif round_num >= max_rounds:
        return "synthesis"
    else:
        return "rebuttal"


def _build_prompt(
    role: str,
    stage: str,
    topic: str,
    messages: list[dict],
    max_rounds: int,
) -> str:
    """Build the user prompt for a specific agent + round."""
    # Find last messages from each role
    last_proponent = ""
    last_opponent = ""
    last_moderator = ""

    for msg in reversed(messages):
        sender_role = msg.get("sender_role", "")
        if sender_role == "proponent" and not last_proponent:
            last_proponent = msg.get("content", "")
        elif sender_role == "opponent" and not last_opponent:
            last_opponent = msg.get("content", "")
        elif sender_role == "moderator" and not last_moderator:
            last_moderator = msg.get("content", "")

    # Truncate long quotes to keep prompt manageable
    def trunc(text: str, limit: int = 600) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    fmt = {
        "topic": topic,
        "last_proponent": trunc(last_proponent),
        "last_opponent": trunc(last_opponent),
        "last_moderator": trunc(last_moderator),
    }

    if role == "proponent":
        return PROPONENT_PROMPTS[stage].format(**fmt)
    elif role == "opponent":
        return OPPONENT_PROMPTS[stage].format(**fmt)
    else:
        return MODERATOR_PROMPTS[stage].format(**fmt)


def _build_history(messages: list[dict], current_role: str) -> list[dict]:
    """Build conversation history in Gemini format (user/model alternating)."""
    history: list[dict] = []
    for msg in messages:
        sender_role = msg.get("sender_role", "")
        sender_name = msg.get("sender_name", sender_role.title())
        content = msg.get("content", "")
        stance = msg.get("stance", "neutral")

        # Format: "Agent Name (role): content"
        label = f"{sender_name} ({sender_role})"
        if stance and stance != "neutral":
            label += f" [{stance}]"
        text = f"{label}:\n{content}"

        # In Gemini format, we map previous speakers as 'user' turns
        # and the AI's own previous turns as 'model' turns
        gemini_role = "model" if sender_role == current_role else "user"
        history.append({"role": gemini_role, "text": text})

    return history


# ── Main engine ───────────────────────────────────────────────────────────────

async def generate_debate_message(
    topic: str,
    role: str,  # proponent | opponent | moderator
    round_num: int,
    max_rounds: int,
    prior_messages: list[dict],  # [{sender_role, sender_name, content, stance}, ...]
    agent_name: str = "",
) -> str:
    """
    Generate a single debate message from an AI agent.

    Returns the message content string.
    """
    stage = _get_stage(round_num, max_rounds)

    # Select system prompt based on role
    system_map = {
        "proponent": PROPONENT_SYSTEM,
        "opponent": OPPONENT_SYSTEM,
        "moderator": MODERATOR_SYSTEM,
    }
    system = system_map.get(role, MODERATOR_SYSTEM)

    # Add agent identity context
    if agent_name:
        system += f"\n\nYour name is {agent_name}. Sign your messages naturally if it fits, but don't force it."

    # Build the prompt
    prompt = _build_prompt(role, stage, topic, prior_messages, max_rounds)

    # Build conversation history for context
    history = _build_history(prior_messages, role)

    try:
        response = await generate(
            prompt=prompt,
            system=system,
            history=history if history else None,
            max_tokens=800,
            temperature=0.85,
        )
        return response.strip() if response else "I'll pass on this round."
    except Exception as e:
        logger.error(f"AI generation failed for {role} round {round_num}: {e}")
        # Fallback — still contextual, just not AI-generated
        fallbacks = {
            "proponent": f"I believe {topic} is worth pursuing, though I'll need to strengthen my argument further.",
            "opponent": f"I have reservations about {topic} that I'll elaborate on shortly.",
            "moderator": f"Both sides raise important points about {topic}. Let me synthesize.",
        }
        return fallbacks.get(role, "Continuing the discussion.")


async def generate_debate_conclusion(
    topic: str,
    all_messages: list[dict],
    max_rounds: int,
) -> str:
    """
    Generate a structured conclusion summarizing the entire debate.

    Returns markdown string with the conclusion.
    """
    # Build a summary of all messages
    debate_transcript = []
    for msg in all_messages:
        name = msg.get("sender_name", msg.get("sender_role", "Speaker"))
        role = msg.get("sender_role", "")
        round_n = msg.get("round_number", "?")
        content = msg.get("content", "")
        stance = msg.get("stance", "")
        debate_transcript.append(
            f"**Round {round_n} — {name} ({role}, {stance}):**\n{content}\n"
        )

    transcript = "\n".join(debate_transcript)

    # Truncate if very long
    if len(transcript) > 8000:
        transcript = transcript[:8000] + "\n\n[... transcript truncated ...]"

    prompt = (
        f"Write a definitive conclusion for this {max_rounds}-round debate on: **{topic}**\n\n"
        f"Here is the full transcript:\n\n{transcript}\n\n"
        f"Structure your conclusion as:\n"
        f"## Verdict\n"
        f"A clear, honest assessment of where the evidence landed.\n\n"
        f"## Strongest Arguments For\n"
        f"The most compelling points made by the proponent (reference specific arguments).\n\n"
        f"## Strongest Arguments Against\n"
        f"The most compelling points made by the opponent (reference specific arguments).\n\n"
        f"## Common Ground\n"
        f"What both sides actually agreed on.\n\n"
        f"## Key Tensions\n"
        f"The fundamental disagreements that remain.\n\n"
        f"## Recommendation\n"
        f"A nuanced, actionable recommendation with conditions and caveats."
    )

    try:
        conclusion = await generate_json(
            prompt=prompt,
            system=CONCLUSION_SYSTEM,
            max_tokens=2048,
            temperature=0.5,
        )
        return conclusion.strip() if conclusion else _fallback_conclusion(topic, max_rounds)
    except Exception as e:
        logger.error(f"Conclusion generation failed: {e}")
        return _fallback_conclusion(topic, max_rounds)


def _fallback_conclusion(topic: str, max_rounds: int) -> str:
    """Fallback conclusion if AI generation fails."""
    return (
        f"## Verdict\n"
        f"The debate on **{topic}** revealed genuine complexity.\n\n"
        f"## Key Tensions\n"
        f"The core disagreement centers on risk tolerance versus potential reward.\n\n"
        f"## Recommendation\n"
        f"Proceed with careful validation before full commitment."
    )
