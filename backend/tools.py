"""Tools the agent can call.
Each tool = a name + a description shown to the LLM + an execution function.
The agent decides in `decide` whether to call one and which; the run_tool node does the executing.
Future tools (search_memory / recall_past_sessions / start_breathing…) all go in here.

Note: the trusted contact is **personal data** and the server stores none of it.
In production the client sends it along with the request (the contact parameter);
in local Streamlit dev nobody passes it, so we fall back to local data/config.json.
"""


def surface_trusted_contact(reason: str = "", contact: dict = None) -> dict:
    """Crisis escalation: bring the contact info of someone they trust, plus a help hotline, right in front of them.
    This does not mean the companionship ends — the companion keeps gently staying with them all the while."""
    cfg = contact
    if cfg is None:
        # Only local dev (Streamlit) takes this path: read the local config file. The production server has no such file.
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
        # Fallback: even if no trusted contact is set yet, still offer a general help line (US 988)
        "hotline": "如果撑不住，拨打或发短信 988（美国自杀与危机生命线，24 小时，中文可转接）。",
    }


# Tool registry: name -> {execution function, description shown to the LLM}
TOOLS = {
    "surface_trusted_contact": {
        "fn": surface_trusted_contact,
        "desc": ("当 ta 流露出想伤害自己、想死、撑不下去、或处境有危险的信号时，调用它，"
                 "把 ta 信任的人的联系方式和求助热线端到 ta 面前。宁可多端一次，也不要漏。"
                 "调用它不代表结束陪伴。"),
    },
}


def tool_menu() -> str:
    """The tool menu shown to the decision brain."""
    return "\n".join(f"- {name}：{t['desc']}" for name, t in TOOLS.items())


def run(tool_name: str, reason: str = "", contact: dict = None) -> dict:
    """Execute a tool and return its result dict (empty dict if not found)."""
    t = TOOLS.get(tool_name)
    if not t:
        return {}
    try:
        return t["fn"](reason, contact)
    except Exception:
        return {}
