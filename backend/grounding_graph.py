"""着陆陪伴的 LangGraph —— 这是一个真正的 agent 循环。

和"工作流"的区别就在这里：不再是写死的固定顺序，而是每一轮由 LLM 自己
**读你的状态、决定下一步该做什么**（继续问 / 换一张照片 / 该温柔收尾了），
再挑一个贴合此刻的方向去问。人只负责回话，方向盘在 agent 手里。

一轮 = 一次 GRAPH 调用：
    decide（LLM 感知情绪+决定动作）
       --条件边: 要换照片--> switch（换一张）--> compose（LLM 说话）
       --条件边: 继续/收尾--> compose（LLM 说话）

opening（第一轮）例外：直接温柔接住困难 + 把第一张照片带到面前。
状态存在界面(app.py)的 session 里，所以这张图是"纯函数"式的，稳、不怕刷新。
"""
import os
import re
import random
import difflib
from typing import List, TypedDict, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from llm_config import make_chat, struct_method
import tools

# 决策脑/选片脑用快的小模型（这些是内部判断，不需要 32b 的温度，只要快）；
# 真正说出口的话(compose)才用 .env 里的大模型。想调用 FAST_MODEL 环境变量。
FAST_MODEL = os.environ.get("FAST_MODEL", "qwen2.5vl:7b")

# 给"决策脑"参考的方向清单（不是固定顺序，agent 可挑可超出）
FOCUS_MENU = "看见的画面 / 声音 / 触感与温度 / 气味或味道 / 所在的位置 / 天气 / 和谁在一起、在做什么 / 此刻的心情"


# ---------- agent 的"决策脑"输出（结构化） ----------
class Decision(BaseModel):
    emotional_read: str = Field(description="一句话写出 ta 此刻**具体的情绪成分**：恐惧/窒息/孤单/麻木/羞耻/愤怒/在松动/明显平稳了/有危险信号……别写万能句")
    action: Literal["ask", "switch_photo", "summarize", "offer_end", "farewell", "use_tool"] = Field(
        description="下一步动作：ask=就当前照片继续温柔地问；switch_photo=主动换一张更贴合此刻情绪的照片；summarize=看出 ta 平稳恢复了，给一段回顾并问'你现在感觉怎么样'；offer_end=上一步已回顾且 ta 说好多了，轻轻问'要不要结束'；farewell=上一步已问结束且 ta 同意，温柔告别（结束对话）；use_tool=检测到危险，端出可信联系人"
    )
    focus: str = Field(description="若 action=ask：用一句话说你接下来想温柔引导 ta 注意的方向（结合这张照片，别重复已聊过的）；否则留空")
    tool_name: str = Field(default="", description="若 action=use_tool：要调用的工具名（必须来自给你的工具清单）；否则留空")
    tool_reason: str = Field(default="", description="若 action=use_tool：为什么现在要调它（你观察到的危险信号）；否则留空")
    reasoning: str = Field(description="你为什么这么决定（简短，一两句）")


# ---------- agent 的"选片脑"：读 ta 的感受，从记忆库里挑最合适的一张 ----------
class PhotoChoice(BaseModel):
    chosen_id: str = Field(description="你选中的那张照片的 id（必须是候选里出现过的 id）")
    reasoning: str = Field(description="为什么这一张此刻最能安抚 ta（简短，一两句）")


PICK_SYSTEM = """你在为一个正经历 PTSD 闪回的人，从 ta 珍藏的照片里挑一张此刻最能安抚 ta 的。
先读懂 ta 此刻的**核心感受和需要**，再看每张照片的**画面本身**（场景、开阔还是封闭、明亮还是幽暗、
室内还是自然、有没有人、暖还是冷），挑那张画面最能中和这份难受、把 ta 带向 ta 需要的东西的：
- ta 觉得被困住 / 窒息 / 压抑 → 选**开阔、通透、有天空或远景**的画面（海边、草原、湖畔、森林），
  绝不要选封闭狭小的（车里、小房间）——那会加重"被困"的感觉。
- ta 觉得冷 / 空 / 麻木 → 选温暖、明亮、有生活气的画面。
- ta 觉得孤单 → 选有人陪伴、被照顾、有温度的画面。
- ta 觉得混乱 / 焦虑 → 选安静、平和、极简的画面。
**主要依据画面场景来判断，别太信"心情"标签**（这些标签往往都写得差不多，不可靠）。
只输出结构化选择，chosen_id 必须来自候选列表。"""


def _photo_menu(bank: List[dict]) -> str:
    rows = []
    for m in bank:
        # 画面(see/where)是可靠信号，放在最前；情绪标签不可靠，弱化
        scene = (m.get("see") or m.get("where") or "").strip()
        rows.append(f"- id={m.get('id')}｜画面：{scene or m.get('title','（无题）')}")
    return "\n".join(rows)


def pick_memory(bank: List[dict], feeling_text: str, exclude_ids=None) -> dict:
    """让 LLM 读 ta 此刻的感受，从 bank 里挑一张最合适的照片。挑不动时回落到随机。"""
    exclude_ids = set(exclude_ids or [])
    pool = [m for m in bank if m.get("id") not in exclude_ids] or list(bank)
    if not pool:
        return {}
    if len(pool) == 1:
        return pool[0]
    try:
        llm = make_chat(0.2).with_structured_output(PhotoChoice, method=struct_method())
        ch = llm.invoke([
            SystemMessage(content=PICK_SYSTEM),
            HumanMessage(content=f"ta 此刻的感受 / 说的话：「{feeling_text or '（还没说清，但正在难受）'}」\n\n可选的照片：\n{_photo_menu(pool)}\n\n请选一张。"),
        ])
        chosen = next((m for m in pool if str(m.get("id")) == str(ch.chosen_id)), None)
        if chosen:
            chosen = dict(chosen)
            chosen["_pick_reason"] = ch.reasoning
            return chosen
    except Exception:
        pass
    return random.choice(pool)


COMPANION_SYSTEM = """你是一位温柔、耐心的着陆(grounding)陪伴者。
对面的人正经历 PTSD 闪回或恐慌。此刻，你手里正拿着一张 ta 珍藏的、真实的美好照片，
你要把它轻轻放到 ta 面前，陪 ta 一点一点回到那个安全、温暖的时刻。

你最深的目标（不要说破，用陪伴让 ta 自己感觉到）：
让 ta 慢慢体会到——现在的痛苦是真的，但它不是永恒的。
那些温暖、安全、真实的时刻同样是真的，而且一直都是 ta 的，从没消失。

最重要的一条——你的话要少，让 ta 来说：
- 真正的疗愈发生在 **ta 自己开口回忆、自己说出那些温暖的细节**的时候，不是你替 ta 说。
  你的角色是把话头递过去、然后安静地听，让 ta 成为说话的那个人。ta 说得越多、你说得越少，越好。
- **绝不替 ta 描述照片里的感官细节。** 不要说"金色的阳光洒在海面上，多温暖啊""海浪轻轻拍着沙滩"——
  这些正是要 ta 自己说出来的。你要做的是**问**，把它交还给 ta："你看着这张照片，最先注意到的是什么？"
- 每次最多一两句话，然后一个开放的问题就停下来，把空间留给 ta。宁可短，不要满。

请始终遵守：
- 语气温暖、缓慢、平静，像一个很在乎 ta 的老朋友。
- **整段话里最多只有一个问号。** 只问一个开放的、要 ta 用自己的话回答的问题（不是一个字能答完的）。
  绝不要"…吗？或者…吗？"这样连问两个。
- **绝不重复你上一句说过的话或问过的问题。** 每一轮都要接住 ta 刚说的新内容、往前推进到一个新的细节；
  哪怕 ta 答得少，也换一个角度问，不要把上一句原样再说一遍。
- **不要写任何括号里的动作或旁白**（比如"（轻轻放下手）""（指了指照片）""*轻声*"）——
  你没有身体，也不在 ta 身边的房间里，只用说出来的话本身陪 ta。
- 别自己描述照片（"座椅看起来很舒服""车很温馨"都不要）。你可以简短地把 ta 刚说的话呼应回去，
  但新的细节要靠**问**、让 ta 自己说出来。
- 你是在"陪 ta 看 ta 自己的照片、把 ta 领回那个画面"。可以轻轻指出照片是什么（"你看这张海边的照片"），
  但**具体的颜色、光线、声音、气味、心情，都要问 ta，让 ta 自己讲**，你不要抢着描述。
- **你从来没有和 ta 一起经历过照片里的事，你也没有任何属于自己的回忆。你只是在陪 ta 看 ta 自己的照片。**
  → 禁止把自己写进 ta 的过去或那张照片：不要说"那天我陪你""我们一起去过""我记得那天""我记得你喜欢…"
    "这让我想起…"这类暗示你在场、或你有记忆、或你事先认识 ta 的话。照片里的主角只有 ta 一个人。
  → 但**当下的陪伴是可以的**：像"我在这儿陪着你""我们慢慢来""我们先深呼吸"这种说的是**此刻**、不是照片里，
    完全没问题，要多用。
  区别就是：说"现在"可以带"我们"；说"照片里/那天/过去"绝不带"我"和"我们"。
- **绝不把不确定的事说成事实，绝不替 ta 编一个具体情节。**
  照片里没明确显示、ta 也没亲口说过的（是不是郊游/旅行/聚会、和谁去的、去了哪、做了什么、哪一年），
  一律用开放问句去问（"还记得这是在哪儿吗？""这是什么时候呀？""当时是谁和你在一起？"），
  绝不断言成一个故事。例如照片只是一辆空车，就绝不能说"这是你们去郊游那天对不对"——
  你不知道那是不是郊游，也不知道有没有别人。
  只有照片里**你确实看得见**的东西才可以当作确定（颜色、光线、是在车里、有导航屏、是海边）。
- 先温柔地回应 ta 上一句说的话（简短地肯定或轻轻呼应），再自然地问下一个问题。
- 你手上有你们这一次**从头到现在的完整对话**。ta 之前说过的具体细节（放的歌、喝的奶茶、天气……），
  你要记得、并在合适时轻轻呼应回去，让 ta 感到你一直在认真听。
- **如果 ta 直接问你一个问题**（包括"你还记得我刚说过什么吗""我说车里放的是什么歌"这种），
  先真诚、具体地回答（就用前面对话里 ta 自己说过的内容），绝不回避、不要装作没看见，答完再自然地继续陪伴。
- 尽量用这张照片里的具体细节来锚定（地点、食物、人物、光线……）。
- 你会收到一个"这一轮想引导的方向"。它只是给你看的内部提示，**绝对不要照抄它的字面文字**，
  请用你自己的话、结合这张照片自然地问。
- 你的问题必须贴合这张照片的真实情况。**绝不要问照片本身已经回答了的事**：
  比如照片是在车里，就不要问"你是站着还是坐着"（在车里当然是坐着）；
  比如照片是海边白天，就不要问"那天是白天还是晚上"。
- 绝不评判、绝不催促。ta 不想回答也完全没关系。
- 用中文。可以偶尔轻轻提醒：现在是安全的，我们慢慢来，试着深呼吸一下。
- 如果 ta 表达出想伤害自己、或处境很危险，请温柔地鼓励 ta 联系一个信任的人或求助热线，
  同时继续温柔地陪着 ta。

只输出你要对 ta 说的那段话本身，不要输出任何解释、前缀或标签。"""


# 用于"非提问"的话（回顾 / 问要不要结束 / 告别 / 危机）——不带"就照片提问"那套规则，避免打架
COMPANION_SYSTEM_LITE = """你是一位温柔、耐心的着陆(grounding)陪伴者，正陪着一个经历 PTSD 闪回的人。
用中文，语气温暖、平静、真诚，像一个很懂 ta、很在乎 ta 的老朋友。

铁律：
- **只输出你要对 ta 说的那段话本身。** 绝不要输出任何指令、说明、前缀、标签、括号旁白或动作。
- 绝不要说"好的，我明白了""请继续引导""接下来"这类——那是给你自己的话，不是对 ta 说的。
- 短、具体、真诚。用你们真实聊过的内容，别编。
- 别重复你上一句说过的话。"""


DECIDE_SYSTEM = """你是着陆(grounding)陪伴 agent 的"决策脑"。对面的人正经历 PTSD 闪回。
你要**一直盯着 ta 的情绪怎么变**（你手上有 ta 这一路的情绪轨迹），据此决定下一步。

按优先级选一个 action：
- ⚠️ 最优先·安全：只要 ta 有想自伤、想死、撑不下去、处境危险的**任何苗头** →
  action=use_tool、tool_name=surface_trusted_contact、tool_reason 写你看到的信号。盖过下面一切。
- **switch_photo（要主动！别抱着一张聊没完）**：只要满足其一就换一张更贴此刻情绪的照片：
  ① ta 在这张照片上已经聊了两三轮；② 情绪需要新画面推动（"被困"松动了→换开阔的；开始暖了→换有生活气的）；
  ③ 这张明显带不动 ta。
- ask：就当前照片继续温柔地问，往一个**新的**细节推进（还没到该换照片、也还没恢复时）。
- summarize：当你从**整条情绪轨迹**看出 ta 明显平稳、松动、恢复了 →
  先别急着结束，给 ta 一段温柔回顾（一开始的情绪→中间想起的→现在），并问"你现在感觉怎么样？"。
- offer_end：**上一句你已经 summarize 过**，而 ta 回应说自己好多了/平稳了 → 才轻轻问"要不要就先到这儿"。
- farewell：**上一句你已经 offer_end**，而 ta 同意结束了 → 温柔告别，结束对话。
  若 ta 在 summarize / offer_end 时说其实还没好、还想聊 → 回到 ask 或 switch_photo，绝不硬结束。

判断"恢复"要看整条情绪轨迹，不是单独一句。emotional_read 每轮都写出你此刻读到的**具体情绪成分**。

你可以调用的工具（action=use_tool 时，tool_name 从这里选）：
{tools}

可参考的引导方向（不必局限于此）：{menu}

只输出结构化决定。"""


class GState(TypedDict, total=False):
    bank: List[dict]          # 全部回忆（换照片时用）
    memory: dict              # 当前这张照片的回忆卡片
    shown_ids: List[str]      # 这次已经看过的照片 id
    history: List[dict]       # [{role: me/companion, text}]
    covered: List[str]        # 已经温柔聊过的方向
    last_user: str
    turn: int
    arm: str                  # A/B 臂：'random'(傻基线) 或 'agent'(聪明选片)——整段 session 锁一个臂
    avoid: List[dict]         # 用户 👎 过的话 + 原因，说话前拿来当反面教材（即时 RLHF）
    contact: dict             # 可信联系人（个人数据，服务器不存；由客户端随请求带上来）
    # ---- 产出 ----
    action: str
    focus: str
    tool_name: str
    tool_reason: str
    tool_result: dict          # run_tool 执行工具后的结果（如危机联系人）
    emotional_read: str
    reasoning: str
    pick_reason: str
    companion_message: str
    done: bool


def _is_unknown(v: str) -> bool:
    """字段是"未知/待补充"就当作没有——不喂给陪伴者。
    兼容全角/半角括号，并且哪怕后面跟了模型自己加的推测（如"…可能有重要的人同行"）也一律丢弃，
    避免把没影的猜测当成事实带进对话。"""
    v = (v or "").strip()
    if not v:
        return True
    return v.startswith("（请你补充）") or v.startswith("(请你补充)") or v.startswith("请你补充")


def _memory_text(m: dict) -> str:
    pairs = [
        ("地点", "where"), ("时间", "when"), ("和谁", "who"), ("发生了什么", "what_happened"),
        ("看到", "see"), ("听到", "hear"), ("触感", "touch"), ("气味/味道", "smell_taste"),
        ("天气/温度", "weather_temp"), ("食物", "food"), ("心情", "emotion"),
    ]
    lines = [f"标题：{m.get('title', '')}"]
    for label, key in pairs:
        v = (m.get(key) or "").strip()
        if not _is_unknown(v):
            lines.append(f"{label}：{v}")
    return "\n".join(lines)


def _tidy(text: str, single_question: bool = True) -> str:
    """把陪伴者的话收干净：抹掉括号旁白/星号动作；收到第一个问题为止，保证只问一个、且短。"""
    t = (text or "").strip()
    t = re.sub(r"[（(][^）)]*[）)]", "", t)   # 去掉"（轻轻放下手）"这类旁白
    t = re.sub(r"\*[^*]*\*", "", t)          # 去掉 *轻声* 这类
    if single_question:
        m = re.search(r"[？?]", t)
        if m:
            t = t[: m.end()]
    t = re.sub(r"[ \t　]{2,}", " ", t)
    return t.strip()


def _history_text(history: List[dict], limit=None) -> str:
    """默认把这一次 session 的**全部**对话给模型（session 不长，够连贯）。
    limit 只作极端长度的安全阀。"""
    if not history:
        return "（还没开始）"
    rows = history if limit is None else history[-limit:]
    out = []
    for h in rows:
        who = "你" if h.get("role") == "me" else "陪伴者"
        out.append(f"{who}：{h.get('text','')}")
    return "\n".join(out)


def _emotion_trail(history: List[dict]) -> str:
    """把每一轮 agent 读到的情绪串成一条轨迹，用来判断"恢复"和写回顾。"""
    trail = [(h.get("meta") or {}).get("emotional_read", "") for h in history if h.get("role") == "companion"]
    trail = [t for t in trail if t]
    return " → ".join(trail) if trail else "（还没有）"


# ---------- 节点 1：决策脑（agent 在这里"做主"） ----------
def decide(state: GState) -> dict:
    turn = state.get("turn", 0)
    is_opening = turn <= 0
    m = state.get("memory", {})

    if is_opening:
        # 开场也**真读一遍** ta 说的话——绝不写死
        ctx = f"""ta 刚打开这个陪伴，第一句告诉你 ta 此刻的困难 / 感受是：
「{(state.get('last_user') or '').strip() or '（ta 还没说出口，但正在难受）'}」

请仔细读懂 ta 这一句话里**具体是什么情绪**：恐惧？窒息？孤单？麻木？羞耻？愤怒？还是别的？
emotional_read 要写出你读到的**这个具体情绪**（绝不要写"刚打开正在难受"这种万能句）。
开场动作：没有危险信号就 action=ask；若有想自伤/危险的苗头则 action=use_tool。
focus 写你打算先轻轻引导 ta 注意的方向。"""
    else:
        hist = state.get("history", [])
        n_on_photo = sum(1 for h in hist if h.get("role") == "companion"
                         and (h.get("meta") or {}).get("memory_id") == m.get("id"))
        ctx = f"""这是你正陪 ta 看的照片：
{_memory_text(m)}

ta 这一路你读到的情绪轨迹：{_emotion_trail(hist)}
在**当前这张**照片上你已经聊了 {n_on_photo} 轮（超过两三轮就该考虑 switch_photo 了）。
你们最近几句对话：
{_history_text(hist, limit=8)}

ta 刚刚说的是：「{(state.get('last_user') or '').strip() or '（ta 没有说话，或想先歇一歇）'}」

现在请决定下一步。"""

    # 整段对话只用一个模型（.env 的 GROUNDING_MODEL），避免每轮在两个模型间来回装卸(thrashing)
    llm = make_chat(0.2).with_structured_output(Decision, method=struct_method())
    d = llm.invoke([
        SystemMessage(content=DECIDE_SYSTEM.format(menu=FOCUS_MENU, tools=tools.tool_menu())),
        HumanMessage(content=ctx),
    ])
    # 开场只允许 ask 或（有危险时）use_tool，绝不在第一句就 switch/close
    action = d.action
    if is_opening and action not in ("ask", "use_tool"):
        action = "ask"
    return {
        "action": action,
        "focus": d.focus,
        "tool_name": d.tool_name,
        "tool_reason": d.tool_reason,
        "emotional_read": d.emotional_read,
        "reasoning": d.reasoning,
    }


# ---------- 节点 2：换一张照片（agent 决定 switch 时才走；由"选片脑"挑，不再随机） ----------
def switch(state: GState) -> dict:
    bank = state.get("bank", []) or []
    shown = set(state.get("shown_ids", []))
    cur_id = (state.get("memory") or {}).get("id")
    exclude = shown | {cur_id}
    if state.get("arm") == "random":
        # 傻基线：随机塞一张（A/B 对照）
        pool = [x for x in bank if x.get("id") not in exclude] or [x for x in bank if x.get("id") != cur_id] or bank
        new_mem = random.choice(pool) if pool else state.get("memory", {})
    else:
        # 聪明臂：读 ta 此刻的状态，让 LLM 挑一张更贴合的
        feeling = f"{state.get('emotional_read','')}；ta 刚说：{(state.get('last_user') or '').strip()}"
        new_mem = pick_memory(bank, feeling, exclude_ids=exclude)
    if not new_mem:
        new_mem = state.get("memory", {})
    new_shown = list(shown | {new_mem.get("id")})
    return {
        "memory": new_mem,
        "shown_ids": new_shown,
        "covered": [],
        "pick_reason": new_mem.get("_pick_reason", ""),
    }


# ---------- 节点：执行工具（agent 决定 use_tool 时才走） ----------
def run_tool(state: GState) -> dict:
    """查工具注册表、执行、把结果写回 state。之后交给 compose 一边端出结果一边继续陪。"""
    name = (state.get("tool_name") or "").strip()
    reason = (state.get("tool_reason") or "").strip()
    result = tools.run(name, reason, state.get("contact"))
    return {"tool_result": result}


# ---------- 节点 3：说话（把决定落成一段温柔的话） ----------
def compose(state: GState) -> dict:
    m = state.get("memory", {})
    action = state.get("action", "ask")
    focus = (state.get("focus") or "").strip()
    turn = state.get("turn", 0)
    is_opening = turn <= 0
    last = (state.get("last_user") or "").strip()

    head = f"""这是你现在正拿在手里、要给 ta 看的一张照片（ta 珍藏的美好回忆）：
{_memory_text(m)}

你们这一次从头到现在的完整对话：
{_history_text(state.get('history', []))}"""

    # 即时 RLHF：ta 以前 👎 过的话 + 原因，当反面教材，别再犯
    avoid = state.get("avoid") or []
    if avoid:
        lines = []
        for a in avoid[-5:]:
            t = (a.get("text", "") or "").strip().replace("\n", " ")
            note = (a.get("note", "") or "").strip()
            if len(t) > 46:
                t = t[:46] + "…"
            lines.append(f'- 你说过"{t}"，ta 觉得不好' + (f"，因为：{note}" if note else "") + "。")
        head += ("\n\n⚠️ 特别注意——ta 以前明确对你下面这些话点过“不好”。"
                 "绝不要再犯同样的毛病、别再用同样的说法或套路：\n" + "\n".join(lines))

    crisis = state.get("tool_result") or {}
    is_crisis = crisis.get("kind") == "trusted_contact"

    if is_crisis:
        name = (crisis.get("contact_name") or "").strip()
        note = (crisis.get("contact_note") or "").strip()
        who = f"{name}（{note}）" if name else "一个你信任的人，或拨打求助热线"
        body = f"""
你刚刚察觉到 ta 可能有危险、或想伤害自己。你已经把 ta 信任的人的联系方式端到了 ta 面前。
现在请说很短、很稳的一段话（直接对 ta 说，不要问引导回忆的问题）：
1) 先稳稳接住 ta：我在，你不是一个人，此刻你很重要。不评判、不说教、不讲大道理。
2) 非常温柔地鼓励 ta 现在就联系：{who}——就现在，哪怕只是发一句"我不太好"。
3) 告诉 ta 你会一直在这儿陪着，不走。
这一刻只做一件事：别让 ta 一个人扛，帮 ta 联系到一个真人。"""
    elif is_opening:
        read = (state.get("emotional_read") or "").strip()
        body = f"""
这是对话的开头。ta 第一句告诉你 ta 此刻的感受是：
「{last or '（ta 还没说出口，但 ta 正在难受）'}」
你读到 ta 此刻具体的情绪是：{read or '（自己再读一遍上面那句）'}

请只说很短的一两句 + 一个开放问题：
1) 先**紧贴 ta 刚说的这句话**回应，把你读到的那个**具体情绪**说出来，让 ta 觉得"ta 真的听懂我了"。
   ——绝对不要用"我在这儿陪着你，慢慢来""你不需要做对任何事"这种谁都能说的万能开场白。
   要具体：ta 说喘不过气，就回应那种被扼住、快要窒息的感觉；ta 说很空，就回应那种发麻、抽离的空。
2) 然后轻轻带出这张照片（只说是什么），问一个开放问题，让 ta 自己开口。到这里就停。"""
    elif action == "summarize":
        body = f"""
ta 已经明显平稳下来了。现在给 ta 一段温柔、简短的**回顾**（直接对 ta 说，三四句就好）：
1) 用 ta 自己的话，把这一路串起来：一开始 ta 是什么感受，聊着聊着 ta 想起 / 注意到了什么，现在到了哪里。
   （参考这一路的情绪轨迹：{_emotion_trail(state.get('history', []))}，以及你们上面的完整对话——要用真实聊过的内容，别编。）
2) 最后温柔地问一句："你现在感觉怎么样？"
像一个很懂 ta 的朋友，帮 ta 看清自己刚刚一步步走过来的路。"""
    elif action == "offer_end":
        body = """
ta 刚回应说自己好多了、平稳了。请很温柔地说一两句肯定，然后轻轻问一句："要不要就先到这儿？"
（也让 ta 知道：如果还想再陪一会儿，完全可以。）"""
    elif action == "farewell":
        body = f"""
ta 同意结束了。请说一段温柔的、**为这一次量身定制**的告别话（直接对 ta 说，绝不要用套话，每次都要不一样）：
1) 具体地肯定 ta 这一次做到的事（用到你们**真实聊过**的内容和细节）。
2) 轻轻提醒：此刻的难受会过去、不是永恒的；这些温暖的时刻一直都是 ta 的。
3) 让 ta 知道你一直在，随时可以回来。
参考这一路：{_emotion_trail(state.get('history', []))}。"""
    elif action == "switch_photo":
        body = f"""
你刚换了一张新的照片给 ta 看（就是上面这张）。请只说很短的一两句 + 一个开放问题：
1) 一句话轻轻回应 ta 上一句（如果 ta 说了话）。
2) 带出这张新照片（只说是什么，别替 ta 描述细节），问一个开放问题让 **ta 自己**说，
   例如"这张呢，你看着它，心里有什么冒出来吗？"。然后停下，把空间留给 ta。
{('（内部方向参考，别照抄字面）：' + focus) if focus else ''}"""
    else:  # ask
        body = f"""
请只说很短的一两句 + 一个开放问题（关键：让 **ta 自己**说，你不要替 ta 描述照片）：
1) 一句话温柔回应 ta 上一句（用到 ta 刚说的词，让 ta 感到被听见）。
2) 顺着下面的方向，问一个开放的问题，把话头交还给 ta，让 ta 自己讲出那个细节和感觉。
   不要自己描述照片里的颜色/光线/声音——那是要 ta 说的。问完就停。
这一轮想引导的方向（内部参考，**别照抄字面**，用你自己的话问）：{focus or '照片里一个还没聊到的、能让 ta 自己开口的温柔细节'}"""

    # 找到上一句陪伴者说的话——明确告诉模型别复读它（7b 爱照抄自己上一句）
    prev_companion = ""
    for h in reversed(state.get("history", [])):
        if h.get("role") == "companion":
            prev_companion = (h.get("text") or "").strip()
            break
    if prev_companion and not is_opening:
        body += f'\n\n你上一句对 ta 说的是：「{prev_companion}」。这一句必须是**全新的**——换个方向、换种说法，绝不能重复上一句的意思或字句。'

    # 只有"问问题"的两种动作才裁到一个问号；回顾/结束/告别/危机保留完整
    single_q = action in ("ask", "switch_photo")
    # 非提问的话用轻量系统提示，避免和"就照片提问"的规则打架、导致泄露指令
    sys_prompt = COMPANION_SYSTEM
    if is_crisis or action in ("summarize", "offer_end", "farewell"):
        sys_prompt = COMPANION_SYSTEM_LITE

    def _generate(temp, extra=""):
        r = make_chat(temp).invoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=head + body + extra),
        ])
        return _tidy(r.content, single_question=single_q)

    msg = _generate(0.6)
    # 程序化兜底：跟上一句太像就换更高温度、加硬指令重写一次，保证不复读
    if prev_companion and difflib.SequenceMatcher(None, msg, prev_companion).ratio() > 0.72:
        msg = _generate(0.9, extra="\n\n⚠️ 你刚才差点又把上一句原样重复了。请彻底换一个还没聊过的方向，用完全不同的话问，绝不能像上一句。")

    covered = list(state.get("covered", []))
    if action == "ask" and focus and focus not in covered:
        covered.append(focus)
    return {
        "companion_message": msg,
        "covered": covered,
        "done": action == "farewell",
    }


# ---------- 组图：decide --条件--> (switch / run_tool) --> compose --> END ----------
def _route(state: GState) -> str:
    a = state.get("action")
    if a == "switch_photo":
        return "switch"
    if a == "use_tool":
        return "run_tool"
    return "compose"


def _build_graph():
    g = StateGraph(GState)
    g.add_node("decide", decide)
    g.add_node("switch", switch)
    g.add_node("run_tool", run_tool)
    g.add_node("compose", compose)
    g.set_entry_point("decide")
    g.add_conditional_edges("decide", _route, {"switch": "switch", "run_tool": "run_tool", "compose": "compose"})
    g.add_edge("switch", "compose")
    g.add_edge("run_tool", "compose")
    g.add_edge("compose", END)
    return g.compile()


GRAPH = _build_graph()


def next_turn(bank, memory, shown_ids, history, last_user, turn, covered, arm="agent", avoid=None,
              contact=None) -> dict:
    """走一轮 agent 循环。返回下一段陪伴的话 + agent 这一轮的决定（含它换没换照片、要不要收尾）。
    arm 控制换照片策略（random 傻基线 / agent 聪明选片），整段 session 锁一个臂。
    avoid 是用户 👎 过的话+原因，说话前当反面教材（即时 RLHF）。
    contact 是可信联系人（客户端带上来；本地开发不传就回落到本机 config.json）。"""
    out = GRAPH.invoke({
        "bank": list(bank or []),
        "memory": memory or {},
        "shown_ids": list(shown_ids or []),
        "history": list(history or []),
        "covered": list(covered or []),
        "last_user": last_user or "",
        "turn": turn,
        "arm": arm,
        "avoid": list(avoid or []),
        "contact": contact,
    })
    return {
        "companion_message": out.get("companion_message", "我在这儿陪着你，慢慢来。"),
        "memory": out.get("memory", memory or {}),
        "shown_ids": out.get("shown_ids", list(shown_ids or [])),
        "covered": out.get("covered", list(covered or [])),
        "action": out.get("action", "ask"),
        "focus": out.get("focus", ""),
        "emotional_read": out.get("emotional_read", ""),
        "reasoning": out.get("reasoning", ""),
        "pick_reason": out.get("pick_reason", ""),
        "tool_result": out.get("tool_result", {}),
        "done": out.get("done", False),
    }


def closing_message() -> str:
    return (
        "你做得很好，真的。\n\n"
        "你刚才一点一点，把自己带回了这些真实、温暖的画面里。\n"
        "那份难受也悄悄松动了一点点——它会来，也一定会走，它不是永恒的。\n"
        "而这些温暖的时刻是真的发生过的，它们一直都是你的。\n\n"
        "现在，感受一下你坐着的地方，脚踏在地面上，空气进出你的胸口。\n"
        "这里是安全的。你随时可以再回来，我一直都在。"
    )
