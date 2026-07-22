"""agent 能调用的工具（tools）。
每个工具 = 名字 + 给 LLM 看的说明 + 执行函数。
agent 在 decide 里决定"要不要调、调哪个"，run_tool 节点负责执行。
以后加新工具（search_memory / recall_past_sessions / start_breathing…）都往这里加。

注意：可信联系人是**个人数据**，服务器不存。线上由客户端随请求带上来（contact 参数）；
本地 Streamlit 开发时没人传，就回落到本机 data/config.json。
"""


def surface_trusted_contact(reason: str = "", contact: dict = None) -> dict:
    """危机升级：把 ta 信任的人的联系方式 + 求助热线，端到 ta 面前。
    这不代表结束陪伴——陪伴者会同时继续温柔地陪着 ta。"""
    cfg = contact
    if cfg is None:
        # 本地开发（Streamlit）才走这条：读本机配置文件。线上服务器上没有这个文件。
        try:
            import memory_store as ms
            cfg = ms.load_config()
        except Exception:
            cfg = {}
    cfg = cfg or {}
    return {
        "kind": "trusted_contact",
        "reason": reason,
        "contact_name": (cfg.get("contact_name") or "").strip(),
        "contact_note": (cfg.get("contact_note") or "").strip(),
        # 兜底：万一还没设可信联系人，也给一条通用求助线（美国 988）
        "hotline": "如果撑不住，拨打或发短信 988（美国自杀与危机生命线，24 小时，中文可转接）。",
    }


# 工具注册表：名字 -> {执行函数, 给 LLM 看的说明}
TOOLS = {
    "surface_trusted_contact": {
        "fn": surface_trusted_contact,
        "desc": ("当 ta 流露出想伤害自己、想死、撑不下去、或处境有危险的信号时，调用它，"
                 "把 ta 信任的人的联系方式和求助热线端到 ta 面前。宁可多端一次，也不要漏。"
                 "调用它不代表结束陪伴。"),
    },
}


def tool_menu() -> str:
    """给决策脑看的工具清单。"""
    return "\n".join(f"- {name}：{t['desc']}" for name, t in TOOLS.items())


def run(tool_name: str, reason: str = "", contact: dict = None) -> dict:
    """执行一个工具，返回结果 dict（找不到就返回空）。"""
    t = TOOLS.get(tool_name)
    if not t:
        return {}
    try:
        return t["fn"](reason, contact)
    except Exception:
        return {}
