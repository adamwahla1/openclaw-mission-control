"""Debate CRUD endpoints with simulation support."""
import json
import uuid
from fastapi import APIRouter, HTTPException
from database import get_db
from models.debate import DebateCreate, DebateMessageCreate, DebateQuestionCreate
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/debates", tags=["debates"])


# ── List ──────────────────────────────────────────────────────────────────────
@router.get("")
async def list_debates():
    db = await get_db()
    async with db.execute(
        """SELECT d.*, COUNT(dp.id) AS participant_count
           FROM debates d
           LEFT JOIN debate_participants dp ON dp.debate_id = d.id
           GROUP BY d.id
           ORDER BY d.created_at DESC"""
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Create ────────────────────────────────────────────────────────────────────
@router.post("", status_code=201)
async def create_debate(body: DebateCreate):
    db = await get_db()
    debate_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO debates (id, topic, max_rounds)
           VALUES (?, ?, ?)""",
        (debate_id, body.topic, body.max_rounds),
    )
    await db.commit()
    debate = await _get_debate(debate_id)
    await sse.broadcast("debate.created", debate)
    return debate


# ── Get ───────────────────────────────────────────────────────────────────────
@router.get("/{debate_id}")
async def get_debate(debate_id: str):
    return await _get_debate(debate_id)


# ── Update ────────────────────────────────────────────────────────────────────
@router.patch("/{debate_id}")
async def update_debate(debate_id: str, body: dict):
    db = await get_db()
    async with db.execute("SELECT id FROM debates WHERE id = ?", (debate_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Debate not found")

    allowed = {"status", "conclusion_md", "needs_user_input"}
    updates = []
    params = []
    for field, value in body.items():
        if field in allowed:
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        raise HTTPException(400, "No valid fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(debate_id)
    await db.execute(f"UPDATE debates SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    debate = await _get_debate(debate_id)
    return debate


# ── Delete ────────────────────────────────────────────────────────────────────
@router.delete("/{debate_id}")
async def delete_debate(debate_id: str):
    db = await get_db()
    async with db.execute("SELECT id FROM debates WHERE id = ?", (debate_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Debate not found")
    await db.execute("DELETE FROM debates WHERE id = ?", (debate_id,))
    await db.commit()
    return {"ok": True}


# ── Participants ──────────────────────────────────────────────────────────────
@router.post("/{debate_id}/participants", status_code=201)
async def add_participant(debate_id: str, body: dict):
    agent_id = body.get("agent_id")
    if not agent_id:
        raise HTTPException(400, "agent_id required")

    db = await get_db()
    async with db.execute("SELECT id FROM debates WHERE id = ?", (debate_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Debate not found")

    role = body.get("role", "participant")
    specialty = body.get("specialty")

    await db.execute(
        """INSERT INTO debate_participants (id, debate_id, agent_id, role, specialty)
           VALUES (?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), debate_id, agent_id, role, specialty),
    )
    await db.commit()

    debate = await _get_debate(debate_id)
    return debate


@router.delete("/{debate_id}/participants/{agent_id}")
async def remove_participant(debate_id: str, agent_id: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM debate_participants WHERE debate_id = ? AND agent_id = ?",
        (debate_id, agent_id),
    )
    await db.commit()
    return {"ok": True}


# ── Messages ──────────────────────────────────────────────────────────────────
@router.get("/{debate_id}/messages")
async def get_messages(debate_id: str, round: int | None = None):
    db = await get_db()
    query = "SELECT * FROM debate_messages WHERE debate_id = ?"
    params: list = [debate_id]
    if round is not None:
        query += " AND round_number = ?"
        params.append(round)
    query += " ORDER BY created_at ASC"
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/{debate_id}/messages", status_code=201)
async def add_message(debate_id: str, body: DebateMessageCreate):
    db = await get_db()
    async with db.execute("SELECT id, current_round FROM debates WHERE id = ?", (debate_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Debate not found")

    current_round = row["current_round"]
    msg_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO debate_messages (id, debate_id, agent_id, round_number, content, response_to_id, stance)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (msg_id, debate_id, body.agent_id, current_round, body.content, body.response_to_id, body.stance),
    )
    await db.commit()

    async with db.execute("SELECT * FROM debate_messages WHERE id = ?", (msg_id,)) as cursor:
        msg_row = await cursor.fetchone()
    msg_dict = dict(msg_row)
    await sse.broadcast("debate.message", {"debate_id": debate_id, "message": msg_dict})
    return msg_dict


# ── Questions ─────────────────────────────────────────────────────────────────
@router.get("/{debate_id}/questions")
async def get_questions(debate_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM debate_questions WHERE debate_id = ? ORDER BY created_at ASC",
        (debate_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/{debate_id}/questions", status_code=201)
async def add_question(debate_id: str, body: DebateQuestionCreate):
    db = await get_db()
    async with db.execute("SELECT id FROM debates WHERE id = ?", (debate_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Debate not found")

    q_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO debate_questions (id, debate_id, question, asked_by_agent_id)
           VALUES (?, ?, ?, ?)""",
        (q_id, debate_id, body.question, body.asked_by_agent_id),
    )
    await db.commit()

    async with db.execute("SELECT * FROM debate_questions WHERE id = ?", (q_id,)) as cursor:
        row = await cursor.fetchone()
    return dict(row)


@router.patch("/{debate_id}/questions/{question_id}")
async def answer_question(debate_id: str, question_id: str, body: dict):
    user_response = body.get("user_response")
    if not user_response:
        raise HTTPException(400, "user_response required")

    db = await get_db()
    await db.execute(
        """UPDATE debate_questions
           SET user_response = ?, answered_at = datetime('now')
           WHERE id = ? AND debate_id = ?""",
        (user_response, question_id, debate_id),
    )
    await db.commit()

    async with db.execute("SELECT * FROM debate_questions WHERE id = ?", (question_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Question not found")
    return dict(row)


# ── Advance round ─────────────────────────────────────────────────────────────
@router.post("/{debate_id}/advance")
async def advance_round(debate_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT id, current_round, max_rounds, status FROM debates WHERE id = ?",
        (debate_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Debate not found")

    new_round = row["current_round"] + 1
    new_status = row["status"]
    if new_round >= row["max_rounds"]:
        new_status = "concluded"

    await db.execute(
        "UPDATE debates SET current_round = ?, status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_round, new_status, debate_id),
    )
    await db.commit()

    debate = await _get_debate(debate_id)
    event = "debate.concluded" if new_status == "concluded" else "debate.round_advanced"
    await sse.broadcast(event, {"debate_id": debate_id, "current_round": new_round, "status": new_status})
    return debate


# ── Simulate debate ──────────────────────────────────────────────────────────
@router.post("/{debate_id}/simulate")
async def simulate_debate(debate_id: str):
    """Run a simulated debate with auto-generated agents and messages."""
    db = await get_db()

    async with db.execute("SELECT * FROM debates WHERE id = ?", (debate_id,)) as cursor:
        debate_row = await cursor.fetchone()
    if not debate_row:
        raise HTTPException(404, "Debate not found")

    debate = dict(debate_row)
    topic = debate["topic"]
    max_rounds = debate["max_rounds"]

    # Check for existing participants
    async with db.execute(
        "SELECT dp.*, a.name FROM debate_participants dp JOIN agents a ON a.id = dp.agent_id WHERE dp.debate_id = ?",
        (debate_id,),
    ) as cursor:
        participants = await cursor.fetchall()

    # If no participants, create 2-3 agents
    if not participants:
        from services.agent_factory import create_agent_for_task

        roles_data = [
            ("proponent", "Advocates for the proposal, finding supporting arguments and evidence."),
            ("opponent", "Challenges the proposal, identifying risks and counter-arguments."),
            ("moderator", "Keeps the debate on track, summarizes points, and identifies common ground."),
        ]

        for role, desc in roles_data:
            agent = await create_agent_for_task(
                {"title": f"Debate: {topic}", "description": desc},
                role=role,
            )
            await db.execute(
                """INSERT INTO debate_participants (id, debate_id, agent_id, role, specialty)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), debate_id, agent["id"], role, desc),
            )

        await db.commit()

        # Re-fetch participants
        async with db.execute(
            "SELECT dp.*, a.name FROM debate_participants dp JOIN agents a ON a.id = dp.agent_id WHERE dp.debate_id = ?",
            (debate_id,),
        ) as cursor:
            participants = await cursor.fetchall()

    participant_list = [dict(p) for p in participants]

    # Simulated viewpoints per role per round
    proponent_templates = [
        "I strongly believe {topic} is the right direction. The evidence shows clear benefits including improved efficiency and better outcomes.",
        "Building on my previous point, {topic} offers significant advantages. The data consistently supports this approach over alternatives.",
        "To address the concerns raised: the risks of {topic} are manageable and far outweighed by the benefits we've discussed.",
        "The case for {topic} remains compelling. Each round has strengthened the argument with concrete evidence.",
        "In conclusion, {topic} represents our best path forward. The evidence, benefits, and feasibility all align.",
    ]

    opponent_templates = [
        "I must disagree with the premise of {topic}. There are significant risks and downsides that need careful consideration.",
        "Furthermore, {topic} could lead to unintended consequences. We've seen similar approaches fail in comparable situations.",
        "While I acknowledge some benefits, the costs of {topic} are substantial and the evidence for success is mixed at best.",
        "The concerns about {topic} have not been adequately addressed. We should proceed with extreme caution.",
        "In summary, {topic} as proposed carries too much risk. I recommend a more conservative approach with better safeguards.",
    ]

    moderator_templates = [
        "Let me frame this discussion on {topic}. We have strong arguments on both sides. The key question is whether the benefits justify the risks.",
        "Both sides have made valid points about {topic}. The proponent highlights efficiency gains, while the opponent raises legitimate risk concerns.",
        "I'm seeing some common ground emerging on {topic}. Both sides agree on the importance of careful implementation.",
        "The debate on {topic} is reaching a critical juncture. The remaining disagreement centers on risk tolerance and evidence interpretation.",
        "To summarize this debate on {topic}: there is agreement on the potential benefits, but legitimate disagreement on risk assessment and implementation approach.",
    ]

    role_templates = {
        "proponent": proponent_templates,
        "opponent": opponent_templates,
        "moderator": moderator_templates,
    }

    # Run rounds
    all_messages = []
    for round_num in range(max_rounds):
        # Update current round
        await db.execute(
            "UPDATE debates SET current_round = ?, updated_at = datetime('now') WHERE id = ?",
            (round_num + 1, debate_id),
        )
        await db.commit()

        await sse.broadcast("debate.round_advanced", {
            "debate_id": debate_id,
            "current_round": round_num + 1,
            "status": "active",
        })

        # Each participant posts a message
        for participant in participant_list:
            role = participant.get("role", "participant")
            templates = role_templates.get(role, moderator_templates)
            template = templates[round_num % len(templates)]
            content = template.format(topic=topic)

            stance = "support" if role == "proponent" else "oppose" if role == "opponent" else "neutral"

            msg_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO debate_messages (id, debate_id, agent_id, round_number, content, stance)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (msg_id, debate_id, participant["agent_id"], round_num + 1, content, stance),
            )

            all_messages.append({
                "id": msg_id,
                "debate_id": debate_id,
                "agent_id": participant["agent_id"],
                "round_number": round_num + 1,
                "content": content,
                "stance": stance,
            })

            await sse.broadcast("debate.message", {
                "debate_id": debate_id,
                "message": {
                    "id": msg_id,
                    "agent_id": participant["agent_id"],
                    "round_number": round_num + 1,
                    "content": content,
                    "stance": stance,
                },
            })

    # Generate conclusion
    conclusion = (
        f"## Debate Conclusion: {topic}\n\n"
        f"After {max_rounds} rounds of structured debate, the following key points emerged:\n\n"
        f"**Arguments in Favor:**\n"
        f"- The proposal offers clear efficiency and outcome improvements\n"
        f"- Evidence supports the approach over alternatives\n"
        f"- Risks are manageable with proper safeguards\n\n"
        f"**Arguments Against:**\n"
        f"- Significant risks and potential unintended consequences exist\n"
        f"- Evidence for success is mixed in comparable situations\n"
        f"- A more conservative approach may be warranted\n\n"
        f"**Common Ground:**\n"
        f"- Both sides agree on the importance of careful implementation\n"
        f"- The potential benefits are acknowledged by all parties\n"
        f"- Risk mitigation strategies should be a priority\n\n"
        f"**Recommendation:** Proceed with a phased approach, starting with a pilot to validate assumptions before full implementation."
    )

    await db.execute(
        "UPDATE debates SET status = 'concluded', conclusion_md = ?, updated_at = datetime('now') WHERE id = ?",
        (conclusion, debate_id),
    )
    await db.commit()

    await sse.broadcast("debate.concluded", {
        "debate_id": debate_id,
        "status": "concluded",
        "conclusion_md": conclusion,
    })

    return await _get_debate(debate_id)


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _get_debate(debate_id: str) -> dict:
    db = await get_db()
    async with db.execute("SELECT * FROM debates WHERE id = ?", (debate_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Debate not found")
    debate = dict(row)

    # Participants
    async with db.execute(
        """SELECT dp.*, a.name, a.role AS agent_role
           FROM debate_participants dp
           JOIN agents a ON a.id = dp.agent_id
           WHERE dp.debate_id = ?""",
        (debate_id,),
    ) as cursor:
        p_rows = await cursor.fetchall()
    debate["participants"] = [dict(r) for r in p_rows]

    # Messages
    async with db.execute(
        "SELECT * FROM debate_messages WHERE debate_id = ? ORDER BY round_number ASC, created_at ASC",
        (debate_id,),
    ) as cursor:
        m_rows = await cursor.fetchall()
    debate["messages"] = [dict(r) for r in m_rows]

    # Questions
    async with db.execute(
        "SELECT * FROM debate_questions WHERE debate_id = ? ORDER BY created_at ASC",
        (debate_id,),
    ) as cursor:
        q_rows = await cursor.fetchall()
    debate["questions"] = [dict(r) for r in q_rows]

    return debate
