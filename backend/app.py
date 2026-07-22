"""🕊️ 着陆陪伴 · Grounding Companion —— Streamlit 界面。
启动： streamlit run app.py

交互方向：
- 记忆银行：你一次性传进一堆珍藏的好照片，AI 自动看懂、悄悄建库，不用你描述。
- 着陆陪伴：难受时你先说一句此刻的困难，AI 会从你的记忆库里挑一张照片放到你面前，
  一句一句陪你回忆，慢慢让你感到——闪回不是永恒的。
"""
import os
import time
import html
import random

import streamlit as st
from dotenv import load_dotenv

import memory_store as ms
import eval_log as ev

load_dotenv()

st.set_page_config(page_title="着陆陪伴", page_icon="🕊️", layout="centered")

# ---------- 现代、克制、平静的样式 ----------
st.markdown(
    """
    <style>
      /* 藏掉 Streamlit 自带的顶栏/菜单/footer，让它像个真 app */
      #MainMenu, footer, header,
      [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }

      [data-testid="stAppViewContainer"], .stApp { background: #f5f4f1; }
      .block-container { max-width: 720px; padding-top: 2rem; padding-bottom: 7rem; }

      html, body, [class*="css"] {
        font-family: -apple-system, "SF Pro Text", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        font-size: 16px; color: #2b2a27;
      }
      h1 { font-size: 25px; font-weight: 650; letter-spacing: .2px; }
      h1, h2, h3 { color: #2b2a27; }
      .soft { color: #8c877d; font-size: 14px; }

      /* 聊天气泡：你说的在右边(彩色)，陪伴者在左边(白色) —— 像 iMessage */
      .chat { display: flex; flex-direction: column; gap: 12px; margin: 10px 0 6px; }
      .bubble { max-width: 84%; padding: 11px 16px; line-height: 1.62; font-size: 16px;
                border-radius: 20px; word-break: break-word; }
      .bubble.assistant { align-self: flex-start; background: #ffffff; color: #2b2a27;
                border: 1px solid #ecebe4; border-bottom-left-radius: 6px;
                box-shadow: 0 1px 2px rgba(60,50,30,.05); }
      .bubble.me { align-self: flex-end; background: #6f8f7c; color: #fbfdfc;
                border-bottom-right-radius: 6px; }

      /* 开场/收尾的柔和卡片 */
      .big-msg { font-size: 18px; line-height: 1.72; color: #2b2a27;
                background: #ffffff; border: 1px solid #ecebe4; border-radius: 20px;
                padding: 20px 22px; margin: 8px 0 12px; box-shadow: 0 1px 2px rgba(60,50,30,.05); }

      /* 危机卡片：温暖但克制，不刺眼 */
      .crisis-card { font-size: 17px; line-height: 1.7; color: #7a4a2e;
                background: #fbeee5; border: 1px solid #e7c4a9; border-radius: 18px;
                padding: 16px 20px; margin: 6px 0 14px; }
      .crisis-card b { color: #b5651d; }

      /* 按钮：圆润、克制 */
      .stButton>button { border-radius: 12px; padding: 9px 16px; font-size: 15px; font-weight: 500;
                border: 1px solid #ddd9cf; background: #ffffff; color: #4a463f; transition: all .15s; }
      .stButton>button:hover { border-color: #6f8f7c; color: #3a5f4d; }
      .stButton>button[kind="primary"] { background: #6f8f7c; border-color: #6f8f7c; color: #fff; }
      .stButton>button[kind="primary"]:hover { background: #5f7f6c; border-color: #5f7f6c; }

      /* 输入框 */
      .stTextArea textarea, .stTextInput input { border-radius: 12px; border: 1px solid #e3dfd5; font-size: 15px; }
      [data-testid="stChatInput"] textarea { border-radius: 14px; font-size: 16px; }

      /* 呼吸光晕：随节奏(吸4·屏4·呼6)缓缓涨落，淡淡浮在背景，不挡字 */
      .breathe-ring {
        position: fixed; top: 42%; left: 56%;
        width: 360px; height: 360px; margin: -180px 0 0 -180px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(111,143,124,0.16) 0%, rgba(111,143,124,0.05) 45%, rgba(111,143,124,0) 70%);
        pointer-events: none; z-index: 0;
        animation: breathe 14s ease-in-out infinite;
      }
      @keyframes breathe {
        0%   { transform: scale(0.72); opacity: 0.35; }   /* 呼尽，最小 */
        29%  { transform: scale(1.12); opacity: 0.75; }   /* 吸气 ~4s，胀大 */
        57%  { transform: scale(1.12); opacity: 0.75; }   /* 屏住 ~4s */
        100% { transform: scale(0.72); opacity: 0.35; }   /* 呼气 ~6s，收回 */
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _has_key():
    return bool(os.environ.get("OPENAI_API_KEY"))


def _gentle_error(e):
    st.warning(
        "刚才没能连上模型。深呼吸，这不是你的错。\n\n"
        "可以：稍等一下再点一次；或检查本地模型（Ollama）是否在运行、网络是否正常。\n\n"
        f"（技术细节：{e}）"
    )


def _render_chat(history):
    """把整段对话渲染成聊天气泡：你在右(彩色)，陪伴者在左(白色)。"""
    rows = []
    for h in history:
        cls = "me" if h.get("role") == "me" else "assistant"
        txt = html.escape(h.get("text", "")).replace("\n", "<br>")
        rows.append(f'<div class="bubble {cls}">{txt}</div>')
    st.markdown(f'<div class="chat">{"".join(rows)}</div>', unsafe_allow_html=True)


def _pick_memory(mems, exclude_ids=None):
    """AI 自动挑一张照片：优先挑这次还没看过的；都看过了就从全部里挑一张。"""
    exclude_ids = set(exclude_ids or [])
    pool = [m for m in mems if m.get("id") not in exclude_ids] or mems
    return random.choice(pool)


# 反馈队列：你随手记，等你跟我说"处理反馈"时我一起过一遍、直接改代码、撞墙写 wall-log。
FEEDBACK_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback.jsonl")

# RLHF 偏好数据：你对每句 AI 的话点 👍/👎，连同 agent 当时的决策一起存下来。
# 这就是 RLHF/DPO 的燃料——攒够了可以塞回 prompt 当反面教材，或以后微调模型。
RLHF_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rlhf.jsonl")


def _log_rlhf(rating, idx, history, memory, note=""):
    """记一条偏好：rating=good/bad；note=你说的"为什么不好"；连同那句话、agent 决策、上下文一起存。"""
    import json
    entry = history[idx] if 0 <= idx < len(history) else {}
    prev_user = ""
    for j in range(idx - 1, -1, -1):
        if history[j].get("role") == "me":
            prev_user = history[j].get("text", "")
            break
    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
        "rating": rating,
        "note": note.strip(),                       # 你写的"哪里不好"
        "companion_text": entry.get("text", ""),
        "decision": entry.get("meta", {}),          # agent 当时的 action/focus/emotional_read/reasoning
        "prev_user": prev_user,
        "photo": {"id": (memory or {}).get("id", ""), "title": (memory or {}).get("title", "")},
    }
    with open(RLHF_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _recent_bad_examples(limit=5):
    """读最近被 👎 的话+原因，喂给陪伴者当反面教材（即时 RLHF）。"""
    import json
    if not os.path.exists(RLHF_LOG):
        return []
    bad = []
    try:
        with open(RLHF_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("rating") == "bad":
                    bad.append({"text": r.get("companion_text", ""), "note": r.get("note", "")})
    except Exception:
        return []
    return bad[-limit:]


def _save_feedback(text, where=""):
    import json
    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
        "where": where,
        "text": text.strip(),
        "done": False,   # 我处理完会把它标成 True
    }
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------- 侧边栏 ----------
with st.sidebar:
    st.markdown("### 🕊️ 着陆陪伴")
    mode = st.radio("现在想做什么？", ["🕊️ 着陆陪伴", "📷 记忆银行", "📊 我的存档"], label_visibility="collapsed")
    if not _has_key():
        st.error("还没检测到模型配置。请确认 .env 已填好（默认走本地 Ollama）。")
    st.markdown("---")
    st.markdown("#### 🤝 需要一个真人？")
    cfg = ms.load_config()
    name = st.text_input("我信任的人", value=cfg.get("contact_name", ""), placeholder="名字")
    note = st.text_input("怎么联系 / 一句话", value=cfg.get("contact_note", ""), placeholder="电话、微信，或求助热线")
    if st.button("保存联系人"):
        ms.save_config({"contact_name": name, "contact_note": note})
        st.success("已保存 🤍")
    if cfg.get("contact_name") or cfg.get("contact_note"):
        st.info(f"最难的时候，可以找：**{cfg.get('contact_name','')}**　{cfg.get('contact_note','')}")

    st.markdown("---")
    st.markdown("#### 💬 给这个 app 提反馈")
    st.caption("哪里不对、想改什么，随手记。攒着，等你跟 Claude 说“处理反馈”时一起改。")
    fb = st.text_area("说说看", key="fb_text", height=80,
                      placeholder="比如：这句话太长了 / 换照片太慢 / 这个按钮我没看懂……", label_visibility="collapsed")
    if st.button("记下这条反馈"):
        if fb.strip():
            _save_feedback(fb, where=mode)
            st.success("记下了 🤍 下次说“处理反馈”，我就来改。")
        else:
            st.warning("先写点什么再记哦。")
    # 让你看到还有几条没处理
    if os.path.exists(FEEDBACK_LOG):
        import json as _json
        pending = 0
        try:
            with open(FEEDBACK_LOG, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not _json.loads(line).get("done"):
                        pending += 1
        except Exception:
            pass
        if pending:
            st.caption(f"📥 还有 {pending} 条反馈等我处理")


# ================= 模式一：着陆陪伴 =================
def render_grounding():
    mems = ms.load_memories()
    if not mems:
        st.markdown("# 🕊️ 我在这儿")
        st.info("还没有照片呢。先去左边的 **📷 记忆银行**，传几张你最珍爱的照片，我们就可以开始了。")
        return

    ss = st.session_state
    ss.setdefault("g_history", [])
    id2mem = {m.get("id"): m for m in mems}

    def _apply(res):
        """把 agent 这一轮的产出落进对话。"""
        ss.g_memory = res["memory"]
        ss.g_shown = res["shown_ids"]
        ss.g_covered = res["covered"]
        ss.g_decision = {
            "action": res["action"],
            "emotional_read": res["emotional_read"],
            "reasoning": res["reasoning"],
            "pick_reason": res.get("pick_reason", ""),
        }
        ss.g_history = list(ss.get("g_history", [])) + [{
            "role": "companion",
            "text": res["companion_message"],
            "meta": {
                "action": res.get("action", ""),
                "focus": res.get("focus", ""),
                "emotional_read": res.get("emotional_read", ""),
                "reasoning": res.get("reasoning", ""),
                "memory_id": (res.get("memory") or {}).get("id", ""),
            },
        }]
        ss.g_turn = ss.get("g_turn", 0) + 1
        tr = res.get("tool_result") or {}
        if tr.get("kind") == "trusted_contact":
            ss.g_crisis = tr
        # agent 自己收尾 → 悄悄记进存档，不打断对话
        if res["done"] and not ss.get("g_ended"):
            ss.g_ended = True
            try:
                ev.log_event(ss.get("g_session_id", ev.new_session_id()), "end",
                             exit_type="graceful_agent", turns=ss.get("g_turn", 0),
                             photos=ss.get("g_shown", []), transcript=ss.get("g_history", []))
            except Exception:
                pass

    def _run_turn(user_text):
        """跑一轮。第一句话自动开新 session（读情绪、挑照片、记 start），之后继续。"""
        from grounding_graph import next_turn, pick_memory
        first = not ss.get("g_started")
        ss.g_history = list(ss.get("g_history", [])) + [{"role": "me", "text": user_text}]
        try:
            with st.spinner("我在……"):
                if first:
                    ss.g_started = True
                    ss.g_ended = False
                    ss.g_session_id = ev.new_session_id()
                    ss.g_turn = 0
                    ss.g_covered = []
                    mem = pick_memory(mems, user_text)          # 读你此刻的感受挑照片
                    ss.g_memory = mem
                    ss.g_shown = [mem.get("id")]
                    ss.g_pick_reason = mem.get("_pick_reason", "")
                    try:
                        ev.log_event(ss.g_session_id, "start", arm="agent", distress=user_text)
                    except Exception:
                        pass
                    res = next_turn(mems, mem, [mem.get("id")], ss.g_history, user_text, 0, [],
                                    arm="agent", avoid=_recent_bad_examples())
                else:
                    res = next_turn(mems, ss.g_memory, ss.get("g_shown", []),
                                    ss.get("g_history", []), user_text,
                                    ss.get("g_turn", 1), ss.get("g_covered", []),
                                    arm="agent", avoid=_recent_bad_examples())
            _apply(res)
        except Exception as e:
            _gentle_error(e)

    # 顶部：标题 + “新的一次”（像 ChatGPT 的 New chat）
    c_title, c_new = st.columns([4, 1])
    c_title.markdown("# 🕊️ 我在这儿")
    if ss.get("g_history") and c_new.button("新的一次"):
        for k in [x for x in ss.keys() if x.startswith("g_") or x.startswith("why_") or x.startswith("note_")]:
            ss.pop(k, None)
        st.rerun()

    # 危机卡片：一直置顶
    cri = ss.get("g_crisis")
    if cri:
        name = cri.get("contact_name", "")
        note = cri.get("contact_note", "")
        who = f"<b>{name}</b>　{note}" if name else "一个你信任的人"
        st.markdown(
            f'<div class="crisis-card">🤍 你不是一个人。此刻，给 {who} 发一句话或打个电话，好吗？就现在。<br>'
            f'<span style="font-size:16px">{cri.get("hotline","")}</span><br>'
            f'<span style="font-size:16px">我会一直在这儿陪着你，不走。</span></div>',
            unsafe_allow_html=True,
        )

    # 空状态：AI 先打个招呼（像 ChatGPT 新对话）
    if not ss.get("g_history"):
        st.markdown(
            '<div class="chat"><div class="bubble assistant">我在。<br>'
            '此刻，你心里正在经历什么？跟我说说，我陪着你。</div></div>',
            unsafe_allow_html=True,
        )

    # 对话流：照片内嵌在"引入它的那句 AI 消息"上；每句 AI 带 👍/👎
    hist = ss.get("g_history", [])
    last_photo = None
    for i, h in enumerate(hist):
        txt = html.escape(h.get("text", "")).replace("\n", "<br>")
        if h.get("role") == "me":
            st.markdown(f'<div class="chat"><div class="bubble me">{txt}</div></div>', unsafe_allow_html=True)
        else:
            pid = (h.get("meta") or {}).get("memory_id", "")
            if pid and pid != last_photo:
                p = ms.image_abspath((id2mem.get(pid) or {}).get("image_path", ""))
                if p:
                    st.image(p, use_container_width=True)
                last_photo = pid
            st.markdown(f'<div class="chat"><div class="bubble assistant">{txt}</div></div>', unsafe_allow_html=True)
            fc1, fc2, _sp = st.columns([1, 1, 7])
            if fc1.button("👍", key=f"good_{i}", help="这句挺好，多来点"):
                _log_rlhf("good", i, hist, ss.get("g_memory", {}))
                st.toast("记下了 🤍")
            if fc2.button("👎", key=f"bad_{i}", help="这句有点傻，点开告诉我哪里不好"):
                ss[f"why_{i}"] = True
                st.rerun()
            if ss.get(f"why_{i}"):
                note = st.text_input("这句哪里不好？说得越具体，它学得越准", key=f"note_{i}",
                    placeholder="比如：它替我描述了照片 / 问得太傻 / 语气太假 / 又编了我的事……")
                nc1, nc2, _n = st.columns([1, 1, 6])
                if nc1.button("记下 👎", key=f"savebad_{i}", type="primary"):
                    _log_rlhf("bad", i, hist, ss.get("g_memory", {}), note=note)
                    ss[f"why_{i}"] = False
                    st.toast("记下了，我下一句就避开 🙏")
                    st.rerun()
                if nc2.button("取消", key=f"cancel_{i}"):
                    ss[f"why_{i}"] = False
                    st.rerun()

    # AI 的思考 + 呼吸（收起来，不打扰）
    dec = ss.get("g_decision", {})
    if dec.get("emotional_read"):
        _act_zh = {"ask": "继续陪你聊", "switch_photo": "换一张照片", "summarize": "回顾这一路",
                   "offer_end": "轻轻问要不要结束", "farewell": "温柔告别", "use_tool": "端出可信联系人"}
        with st.expander("🧠 看看我此刻怎么想的（AI 的决策）"):
            st.markdown(f"- **我感觉你现在**：{dec.get('emotional_read','')}")
            st.markdown(f"- **我决定**：{_act_zh.get(dec.get('action'), dec.get('action',''))}")
            st.markdown(f"- **为什么**：{dec.get('reasoning','')}")
            if dec.get("pick_reason"):
                st.markdown(f"- **我为什么挑这张照片**：{dec.get('pick_reason','')}")
    # 呼吸光晕：淡淡浮在背景，跟着它的涨落一起呼吸就好
    st.markdown('<div class="breathe-ring"></div>', unsafe_allow_html=True)

    # 唯一入口：底部固定聊天框。第一句就是开始，不用表单、不用滑块。
    user_text = st.chat_input("跟我说说，此刻你在经历什么……")
    if user_text and user_text.strip():
        _run_turn(user_text.strip())
        st.rerun()


# ================= 模式二：记忆银行（批量上传，自动建库） =================
def render_bank():
    st.markdown("# 📷 记忆银行")
    st.markdown(
        '<span class="soft">把你最珍爱的照片一次性传进来，AI 会自己看懂每一张、悄悄记下来。'
        '你什么都不用写——难受的时候，它会带着这些照片来陪你。</span>',
        unsafe_allow_html=True,
    )

    ss = st.session_state
    ups = st.file_uploader(
        "一次可以选很多张（让你觉得温暖、安全、开心的照片）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if ups:
        st.markdown(f'<span class="soft">选好了 {len(ups)} 张。</span>', unsafe_allow_html=True)
        if st.button("建进我的记忆库 ✨", type="primary"):
            if not _has_key():
                st.error("需要先在 .env 里配置好模型（默认本地 Ollama）。")
            else:
                from vision_ingest import draft_memory_from_image
                prog = st.progress(0.0)
                ok, fail = 0, 0
                for i, up in enumerate(ups):
                    try:
                        data = up.getvalue()
                        mime = up.type or "image/jpeg"
                        ext = "." + (up.name.rsplit(".", 1)[-1].lower() if "." in up.name else "jpg")
                        with st.spinner(f"AI 正在温柔地看第 {i+1}/{len(ups)} 张……"):
                            draft = draft_memory_from_image(data, mime=mime)
                        ms.save_memory(draft, data, ext=ext)
                        ok += 1
                    except Exception as e:
                        fail += 1
                        st.warning(f"第 {i+1} 张没建成：{e}")
                    prog.progress((i + 1) / len(ups))
                if ok:
                    st.success(f"存好 {ok} 张啦，它们会在你需要的时候陪着你 🕊️")
                if fail:
                    st.info(f"有 {fail} 张没成功，可以待会儿再试一次。")
                st.rerun()

    # 已有的回忆
    mems = ms.load_memories()
    if mems:
        st.markdown("---")
        st.markdown(f"### 🗂️ 已在你记忆库里的照片（{len(mems)} 张）")
        for m in mems:
            with st.container():
                cols = st.columns([1, 3])
                p = ms.image_abspath(m.get("image_path", ""))
                if p:
                    cols[0].image(p, use_container_width=True)
                with cols[1]:
                    st.markdown(f"**{m.get('title','（无题）')}**")
                    with st.expander("AI 记下的细节"):
                        for label, key in ms.FIELDS[1:]:
                            v = m.get(key, "")
                            if v:
                                st.markdown(f"- **{label}**：{v}")
                    if st.button("删除", key="del_" + m.get("id", "")):
                        ms.delete_memory(m.get("id"))
                        st.rerun()


# ================= 模式三：我的存档（康复档案 + 诚实的起效检查） =================
REFLECT_SYS = """你在温柔地帮一个有 PTSD、会经历恐慌发作的人，回看 ta 自己的康复记录。
下面是 ta 每次发作时选了哪些照片、难受度降了多少、发作时最先说的话的汇总。

请基于这些**已经发生的真实记录**，用中文写一小段温柔、诚实、试探性的观察（不是诊断）：
- 轻轻指出你看到的模式：ta 反复被哪种气质的照片安抚（温暖？开阔？被照顾？），
  这可能在悄悄说 ta 反复需要的是什么（比如休息、温暖、被陪伴、好好吃饭）。
- 如果数据显示哪种照片总让 ta 降得最多，温柔地点出来。
- 全程用"也许""看起来""我猜"这类不确定的语气，把结论权留给 ta 自己。
- 明确说这些只是基于目前 N 次记录的初步观察，样本还小。
- 不做临床诊断、不下病名。如果模式里有反复的痛苦，温柔地鼓励 ta 也和信任的人或专业者聊聊。
- 温暖、简短，像一个很懂 ta 的朋友在陪 ta 一起看这些记录。"""


def _fmt_date(ts):
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return ""


def render_archive():
    st.markdown("# 📊 我的存档")
    st.markdown('<span class="soft">每一次恐慌发作，和你怎么一点点好起来的，都在这里。这是你自己的康复档案。</span>', unsafe_allow_html=True)

    sessions = ev.load_sessions()
    mems = ms.load_memories()
    id2 = {m.get("id"): m for m in mems}
    completed = [s for s in sessions if s.get("completed") and s.get("relief") is not None]

    if not sessions:
        st.info("还没有记录呢。等你第一次用过 **🕊️ 着陆陪伴**，这里就会长出你的第一段存档。")
        return

    # --- 趋势：每次难受度降了多少 ---
    if completed:
        st.markdown("### 📉 每一次，你都降下来了多少")
        st.line_chart({"难受度下降": [s["relief"] for s in completed]})
        avg = sum(s["relief"] for s in completed) / len(completed)
        st.markdown(f'<span class="soft">走完全程 {len(completed)} 次，平均每次难受度降了 {avg:.1f} 分（满分 10）。</span>', unsafe_allow_html=True)

    # --- AI 帮你看模式 ---
    st.markdown("### 🔍 你真正需要的，也许藏在这些记录里")
    if len(completed) < 3:
        st.caption(f"再攒几次（现在 {len(completed)} 次），AI 就能帮你横着看出模式了。")
    else:
        if st.button("让 AI 帮我看看我的模式 ✨"):
            try:
                from llm_config import make_chat
                from langchain_core.messages import SystemMessage, HumanMessage
                digest = ev.journey_digest(sessions, mems)
                with st.spinner("正在温柔地回看你的每一次……"):
                    r = make_chat(0.5).invoke([SystemMessage(content=REFLECT_SYS), HumanMessage(content=digest)])
                st.markdown(f'<div class="big-msg">{r.content.replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)
            except Exception as e:
                _gentle_error(e)

    # --- 每一次发作的卡片 ---
    st.markdown("### 🗂️ 一次一次翻回去")
    for s in reversed(sessions):
        pre, post = s.get("pre_suds"), s.get("post_suds")
        head = _fmt_date(s.get("started_ts"))
        if s.get("completed") and pre is not None and post is not None:
            head += f"　难受 {pre} → {post}（降了 {pre - post}）"
        elif not s.get("completed"):
            head += "　（这次没走完）"
        with st.expander(head):
            photos = [id2.get(p) for p in s.get("photos", []) if id2.get(p)]
            if photos:
                cols = st.columns(min(len(photos), 4))
                for i, m in enumerate(photos):
                    p = ms.image_abspath(m.get("image_path", ""))
                    if p:
                        cols[i % len(cols)].image(p, caption=m.get("title", ""), use_container_width=True)
            for h in s.get("transcript", []):
                who = "🫂 我" if h.get("role") == "me" else "🕊️ 陪伴者"
                st.markdown(f"**{who}**：{h.get('text','')}")

    # --- 诚实的起效检查（A/B）---
    with st.expander("🔬 起效检查：它真的比随机好吗？（诚实的 A/B）"):
        rep = ev.analyze()
        st.caption("每次发作被盲分到「随机塞一张」或「聪明选片」。回归均值对两臂一样，所以聪明臂高出随机臂的那部分，才是真效果。")
        _zh = {"random": "随机（傻基线）", "agent": "聪明选片"}
        for arm, st_ in rep["by_arm"].items():
            mr = st_.get("mean_relief")
            line = f"**{_zh.get(arm, arm)}**：完成 {st_.get('n_completed',0)} 次"
            if mr is not None:
                line += f"，平均降 {mr:.1f} 分"
            if st_.get("ci95"):
                line += f"（95% 区间 {st_['ci95'][0]:.1f} ~ {st_['ci95'][1]:.1f}）"
            if st_.get("graceful_rate") is not None:
                line += f"，从容退出率 {st_['graceful_rate']*100:.0f}%"
            st.markdown(line)
        title, detail = rep["verdict"]
        st.markdown(f"**结论：{title}**")
        st.caption(detail)


if mode.startswith("🕊️"):
    render_grounding()
elif mode.startswith("📷"):
    render_bank()
else:
    render_archive()
