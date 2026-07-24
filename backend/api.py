"""Grounding Companion — FastAPI backend (the stateless agent brain).

Design red line: **the server stores no personal data whatsoever.**
Photos and memory cards live only on your phone. Each turn, the client sends up
"this conversation's state + the memory-bank cards" together; the backend runs one
agent loop, says its piece back, and writes nothing to disk. So even if this server
gets compromised, there is nothing to take.

From start to finish the agent reads **only the cards' text** (title/scene/senses/emotion)
and never looks at photo pixels — which is exactly why photos never need to touch the cloud.
The only place a photo is ever seen is /api/ingest (the vision model looks once while
drafting a card), and even that photo just passes through memory, never landing on disk.

Run locally:  .venv/bin/uvicorn api:app --reload --host 0.0.0.0 --port 8000
Health check: curl http://localhost:8000/health
"""
import hmac
import os
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from grounding_graph import next_turn, pick_memory
import vision_ingest
from llm_config import get_model_name

app = FastAPI(title="Grounding Agent API")

# Only the app itself calls this. CORS stays on for browser-side debugging; the real gate is the API key below.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ---------- Gatekeeping ----------
# No key, no access to this backend. The reason is very practical: every /api/turn call
# spends money on an LLM, and someone's raw words mid-episode pass through here —
# nobody gets to poke at it freely.
API_KEY = os.environ.get("GROUNDING_API_KEY", "")
REQUIRE_KEY = os.environ.get("REQUIRE_API_KEY", "1").strip() not in ("0", "false", "False", "no")


def require_key(x_api_key: str = Header(default="")):
    if not REQUIRE_KEY:
        return                      # Can be turned off for local dev (REQUIRE_API_KEY=0 in .env)
    if not API_KEY:
        raise HTTPException(500, "服务器没配 GROUNDING_API_KEY")
    if not hmac.compare_digest(x_api_key or "", API_KEY):   # Constant-time comparison, guards against timing side channels
        raise HTTPException(401, "unauthorized")


# ---------- Data models ----------
class Msg(BaseModel):
    role: str            # "me" | "companion"
    text: str


class Avoid(BaseModel):
    text: str
    note: str = ""


class Contact(BaseModel):
    contact_name: str = ""
    contact_note: str = ""


class TurnIn(BaseModel):
    user_text: str
    memories: List[dict] = []        # ★ Memory-bank cards, carried up by the client (the phone). The server stores none.
    history: List[Msg] = []          # Prior conversation (not including this user_text)
    memory_id: Optional[str] = None  # Current photo id; null on the first turn
    shown_ids: List[str] = []
    turn: int = 0                    # 0 on the first turn
    covered: List[str] = []
    arm: str = "agent"
    avoid: List[Avoid] = []          # Lines the user has 👎'd (instant RLHF); may be empty
    avoid_recent: List[str] = []     # Photo ids already seen in recent episodes; skip them at the opening so the same photo doesn't get numbing from overuse
    contact: Optional[Contact] = None  # Trusted contact; only used in a crisis. The server stores none.


class MemoryOut(BaseModel):
    id: str
    title: str


class TurnOut(BaseModel):
    companion_message: str
    memory: Optional[MemoryOut] = None
    shown_ids: List[str]
    covered: List[str]
    turn: int                        # The turn the client should use next round (already +1)
    action: str
    done: bool
    photo_changed: bool
    crisis: Optional[dict] = None
    emotional_read: str = ""
    pick_reason: str = ""
    reasoning: str = ""


def _mem_out(m: dict) -> Optional[MemoryOut]:
    if not m or not m.get("id"):
        return None
    return MemoryOut(id=m["id"], title=m.get("title", "") or "")


# ---------- Endpoints ----------
@app.get("/health")
def health():
    """Keep-alive; no key required. Only says the service is up and which model it runs — reveals nothing personal."""
    return {"ok": True, "model": get_model_name(), "stateless": True}


@app.post("/api/turn", response_model=TurnOut, dependencies=[Depends(require_key)])
def turn(inp: TurnIn):
    """Run one agent loop. On the first turn (memory_id=null) it reads how you feel right now and picks an opening photo.

    The memory bank (inp.memories) is carried up by the client — the server has no photos here, and needs none.
    """
    mems = inp.memories or []
    if not mems:
        raise HTTPException(400, "客户端没有带记忆库上来（memories 为空）")

    history = [m.model_dump() for m in inp.history] + [{"role": "me", "text": inp.user_text}]
    avoid = [a.model_dump() for a in inp.avoid]
    contact = inp.contact.model_dump() if inp.contact else None

    first = inp.memory_id is None
    if first:
        # Read the feeling and pick an opening photo, but skip ones seen in recent episodes
        # (so it's not the same photo every episode until it desensitizes).
        # pick_memory falls back to the full bank if exclusions leave too few candidates, so a long avoid_recent is harmless.
        mem = pick_memory(mems, inp.user_text, exclude_ids=inp.avoid_recent)
        shown = [mem.get("id")]
        turn_n, covered = 0, []
    else:
        mem = next((m for m in mems if m.get("id") == inp.memory_id), None)
        if not mem:
            raise HTTPException(404, "当前照片 id 不在客户端带上来的记忆库里")
        shown = inp.shown_ids or [mem.get("id")]
        turn_n, covered = inp.turn, inp.covered

    res = next_turn(mems, mem, shown, history, inp.user_text, turn_n, covered,
                    arm=inp.arm, avoid=avoid, contact=contact)

    new_mem = res.get("memory") or mem
    photo_changed = (new_mem.get("id") != mem.get("id"))

    crisis = None
    tr = res.get("tool_result") or {}
    if tr.get("kind") == "trusted_contact":
        crisis = {
            "contact_name": tr.get("contact_name", ""),
            "contact_note": tr.get("contact_note", ""),
            "hotline": tr.get("hotline", ""),
        }

    return TurnOut(
        companion_message=res.get("companion_message", ""),
        memory=_mem_out(new_mem),
        shown_ids=res.get("shown_ids", shown),
        covered=res.get("covered", covered),
        turn=turn_n + 1,
        action=res.get("action", "ask"),
        done=res.get("done", False),
        photo_changed=photo_changed,
        crisis=crisis,
        emotional_read=res.get("emotional_read", ""),
        pick_reason=res.get("pick_reason", ""),
        reasoning=res.get("reasoning", ""),
    )


@app.post("/api/ingest", dependencies=[Depends(require_key)])
async def ingest(file: UploadFile = File(...)):
    """Upload a photo → the vision model drafts a "memory card" and it goes straight back to the client.

    The photo **only passes through memory**: one look, draft the card, drop it. The server writes nothing to disk and keeps no copy.
    The client takes the draft, fills it in, and stores it on the phone itself.
    """
    data = await file.read()
    try:
        card = vision_ingest.draft_memory_from_image(data)
    except Exception as e:
        raise HTTPException(500, f"看图失败：{type(e).__name__}: {e}")
    return {"draft": card}
