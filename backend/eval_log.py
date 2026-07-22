"""本地 outcome eval + 个人康复存档。
每一次 panic session 记一条：既是"到底有没有起效"的诚实尺子（A/B vs 傻基线），
也是你自己的康复档案（每次怎么好起来的）。全部只在本机 data/sessions.jsonl。

诚实边界：
- n 很小 → 早期数字是噪音，analyze() 会明说，别当结论。
- 回归均值 → 难受到峰值本来会自然回落；只有 agent 臂高出 random 臂的那部分才是真效果。
- 盲 → arm 对用户隐藏，避免期待偏差。
"""
import json
import os
import time
import uuid
import random
import statistics
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
LOG = os.path.join(DATA, "sessions.jsonl")

# A/B：傻基线 vs 聪明情感检索。50/50 盲分。
ARMS = ["random", "agent"]


def assign_arm() -> str:
    return random.choice(ARMS)


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def log_event(session_id: str, kind: str, **data):
    """kind ∈ {'start','end'}。start 记 pre_suds+arm；end 记 post_suds+退出方式+对话。"""
    os.makedirs(DATA, exist_ok=True)
    rec = {"session_id": session_id, "kind": kind, "ts": time.time(), **data}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _load_events():
    if not os.path.exists(LOG):
        return []
    out = []
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def load_sessions():
    """把 start/end 事件拼成每次 session 的完整记录。没 end 的 = 中途 abandon。"""
    ev = _load_events()
    starts = {e["session_id"]: e for e in ev if e.get("kind") == "start"}
    ends = {e["session_id"]: e for e in ev if e.get("kind") == "end"}
    sessions = []
    for sid, s in starts.items():
        e = ends.get(sid)
        rec = {
            "session_id": sid,
            "arm": s.get("arm"),
            "pre_suds": s.get("pre_suds"),
            "started_ts": s.get("ts"),
            "completed": e is not None,
        }
        if e:
            rec.update({
                "post_suds": e.get("post_suds"),
                "exit_type": e.get("exit_type"),
                "turns": e.get("turns"),
                "photos": e.get("photos", []),
                "transcript": e.get("transcript", []),
                "ended_ts": e.get("ts"),
                "duration_s": (e.get("ts", 0) - s.get("ts", 0)) if s.get("ts") else None,
            })
            if rec["pre_suds"] is not None and rec["post_suds"] is not None:
                rec["relief"] = rec["pre_suds"] - rec["post_suds"]
        sessions.append(rec)
    sessions.sort(key=lambda r: r.get("started_ts") or 0)
    return sessions


def _verdict(a, r, n_completed):
    if n_completed < 8 or a.get("mean_relief") is None or r.get("mean_relief") is None:
        return ("样本太少，还不能下结论",
                "现在的数字基本是噪音。至少攒到每臂 ~15 次、总共 30+ 次，才谈得上信号。先安心用，数据会自己长出来。")
    diff = a["mean_relief"] - r["mean_relief"]
    overlap = True
    if "ci95" in a and "ci95" in r:
        overlap = not (a["ci95"][0] > r["ci95"][1] or r["ci95"][0] > a["ci95"][1])
    if diff <= 0:
        return ("聪明检索还没赢过随机",
                f"agent 并不比随机塞一张更好（差 {diff:+.1f} 分）。看起来合理 ≠ 起效——这恰恰是最该盯的诚实信号。")
    if not overlap:
        return ("聪明检索暂时领先",
                f"agent 平均多降 {diff:.1f} 分，且置信区间不重叠。仍是小样本，继续攒才敢下结论。")
    return ("方向对，但还分不清真假",
            f"agent 高 {diff:.1f} 分，但置信区间重叠，可能是噪音。继续攒。")


def analyze():
    sessions = load_sessions()
    completed = [s for s in sessions if s.get("completed") and s.get("relief") is not None]
    by_arm = {}
    for arm in ARMS:
        rows = [s for s in completed if s.get("arm") == arm]
        started = [s for s in sessions if s.get("arm") == arm]
        reliefs = [s["relief"] for s in rows]
        graceful = [s for s in rows if str(s.get("exit_type", "")).startswith("graceful")]
        stat = {
            "n_started": len(started),
            "n_completed": len(rows),
            "mean_relief": statistics.mean(reliefs) if reliefs else None,
            "graceful_rate": (len(graceful) / len(started)) if started else None,
        }
        if len(reliefs) >= 2:
            sd = statistics.stdev(reliefs)
            se = sd / (len(reliefs) ** 0.5)
            m = stat["mean_relief"]
            stat["ci95"] = (m - 1.96 * se, m + 1.96 * se)
        by_arm[arm] = stat
    verdict = _verdict(by_arm.get("agent", {}), by_arm.get("random", {}), len(completed))
    return {"by_arm": by_arm, "n_total": len(sessions), "n_completed": len(completed), "verdict": verdict}


def journey_digest(sessions, memories) -> str:
    """给 LLM 做纵向反思的原料：最常选的照片/情绪、平均降幅、发作时的原话、降得最多的几次。"""
    id2 = {m.get("id"): m for m in memories}
    completed = [s for s in sessions if s.get("completed")]
    lines = [f"总发作记录：{len(sessions)} 次；走完全程的 {len(completed)} 次。"]

    reliefs = [s["relief"] for s in completed if s.get("relief") is not None]
    if reliefs:
        lines.append(f"平均难受度下降：{statistics.mean(reliefs):.1f} 分（满分 10）。")

    cnt = Counter()
    emo_cnt = Counter()
    for s in completed:
        for pid in s.get("photos", []):
            cnt[pid] += 1
            emo = (id2.get(pid, {}) or {}).get("emotion", "")
            if emo:
                emo_cnt[emo] += 1
    if cnt:
        lines.append("最常来陪你的照片：")
        for pid, c in cnt.most_common(5):
            m = id2.get(pid, {}) or {}
            lines.append(f"  - {m.get('title', '（已删）')}（气质/心情：{m.get('emotion', '')}）— {c} 次")
    if emo_cnt:
        lines.append("这些照片反复带来的气质（可能对应你反复需要的东西）：")
        for emo, c in emo_cnt.most_common(5):
            lines.append(f"  - {emo} — {c} 次")

    best = sorted([s for s in completed if s.get("relief") is not None], key=lambda s: -s["relief"])[:3]
    if best:
        lines.append("降得最多的几次，是哪些照片陪着的：")
        for s in best:
            titles = "、".join((id2.get(p, {}) or {}).get("title", "?") for p in s.get("photos", []))
            lines.append(f"  - 降了 {s['relief']} 分，照片：{titles}")

    says = []
    for s in completed:
        for h in s.get("transcript", []):
            if h.get("role") == "me" and (h.get("text") or "").strip():
                says.append(h["text"].strip())
                break
    if says:
        lines.append("发作时你最先说出口的话（原话）：")
        for x in says[:10]:
            lines.append(f"  - 「{x}」")
    return "\n".join(lines)
