"""着陆陪伴 —— FastAPI 后端（无状态的 agent 大脑）。

设计红线：**服务器不存任何个人数据。**
照片和回忆卡片都只在你手机上。每一轮，客户端把"这次对话的状态 + 记忆库卡片"一起发过来，
后端跑一轮 agent 循环、把话说回去，什么都不落盘。所以就算这台服务器被攻破，也没有东西可拿。

agent 从头到尾**只读卡片的文字**（标题/场景/感官/情绪），从不看照片像素——
这正是照片可以完全不上云的原因。唯一会看到照片的地方是 /api/ingest（建卡片时视觉模型看一次），
那张照片也只是穿过内存，不落盘。

本地起：  .venv/bin/uvicorn api:app --reload --host 0.0.0.0 --port 8000
健康检查：curl http://localhost:8000/health
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

# 只有 app 自己调它。留 CORS 是为了浏览器端调试；真正的门是下面的 API key。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ---------- 门禁 ----------
# 没有 key 就打不动这个后端。理由很实在：/api/turn 每次都在花钱调 LLM，
# 而且发作时的原话会经过这里——不能让任何人随便戳。
API_KEY = os.environ.get("GROUNDING_API_KEY", "")
REQUIRE_KEY = os.environ.get("REQUIRE_API_KEY", "1").strip() not in ("0", "false", "False", "no")


def require_key(x_api_key: str = Header(default="")):
    if not REQUIRE_KEY:
        return                      # 本地开发可以关掉（.env 里 REQUIRE_API_KEY=0）
    if not API_KEY:
        raise HTTPException(500, "服务器没配 GROUNDING_API_KEY")
    if not hmac.compare_digest(x_api_key or "", API_KEY):   # 定长比较，防时序侧信道
        raise HTTPException(401, "unauthorized")


# ---------- 数据模型 ----------
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
    memories: List[dict] = []        # ★ 记忆库卡片，由客户端（手机）带上来。服务器不存。
    history: List[Msg] = []          # 之前的对话（不含这次 user_text）
    memory_id: Optional[str] = None  # 当前照片 id；首轮传 null
    shown_ids: List[str] = []
    turn: int = 0                    # 首轮 0
    covered: List[str] = []
    arm: str = "agent"
    avoid: List[Avoid] = []          # 用户 👎 过的话（即时 RLHF），可空
    avoid_recent: List[str] = []     # 最近几次发作已经看过的照片 id，开场避开，防止总看同一张而麻木
    contact: Optional[Contact] = None  # 可信联系人；危机时才用到。服务器不存。


class MemoryOut(BaseModel):
    id: str
    title: str


class TurnOut(BaseModel):
    companion_message: str
    memory: Optional[MemoryOut] = None
    shown_ids: List[str]
    covered: List[str]
    turn: int                        # 客户端下一轮该用的 turn（已 +1）
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


# ---------- 端点 ----------
@app.get("/health")
def health():
    """保活用，不需要 key。只说服务在、用的哪个模型——不透露任何个人信息。"""
    return {"ok": True, "model": get_model_name(), "stateless": True}


@app.post("/api/turn", response_model=TurnOut, dependencies=[Depends(require_key)])
def turn(inp: TurnIn):
    """跑一轮 agent 循环。首轮(memory_id=null)会读你此刻的感受挑一张开场照片。

    记忆库(inp.memories)由客户端带上来——服务器这边没有、也不需要有任何照片。
    """
    mems = inp.memories or []
    if not mems:
        raise HTTPException(400, "客户端没有带记忆库上来（memories 为空）")

    history = [m.model_dump() for m in inp.history] + [{"role": "me", "text": inp.user_text}]
    avoid = [a.model_dump() for a in inp.avoid]
    contact = inp.contact.model_dump() if inp.contact else None

    first = inp.memory_id is None
    if first:
        # 读感受挑开场照片，但避开最近几次已经看过的（防止每次发作都看同一张而脱敏）。
        # pick_memory 里若排除后候选太少会自动回落到全库，所以不怕 avoid_recent 太长。
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
    """上传一张照片 → 用视觉模型起草一张"回忆卡片"草稿，直接返回给客户端。

    照片**只穿过内存**：看一眼、起草卡片、丢掉。服务器不写盘、不留副本。
    客户端拿到草稿后自己补充、自己存在手机上。
    """
    data = await file.read()
    try:
        card = vision_ingest.draft_memory_from_image(data)
    except Exception as e:
        raise HTTPException(500, f"看图失败：{type(e).__name__}: {e}")
    return {"draft": card}
