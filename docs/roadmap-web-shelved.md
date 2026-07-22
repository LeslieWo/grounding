> **状态:已搁置(2026-07-05 起)。** 多用户 Web 版走到 Phase 1 后,方向改为原生 iOS + TestFlight(见仓库 ios/)。留档是因为里面的架构分层想法(agent 核心与外壳解耦)仍然成立。

# 着陆陪伴 · Web 版路线图

把单人本地 Streamlit 应用，改造成**多用户云端 Web 应用**。目的：走一遍全套真实工程流程。

## 决定（2026-07-03 锁定）
- **照片上云**：接受照片离开设备（多用户前提）。不做本地/云双模式，一个云端版。
- **模型**：云端自托管开源视觉模型（qwen2.5-VL）跑在 GPU 上。开发期先连本地 Ollama。
  - 注意：自托管开源模型不支持原生 tools → 继续用手搓的 json_schema 工具循环。
- **技术栈**：FastAPI 后端 + React 前端（完整重写，学最多）。
- **数据/认证/存储**：Supabase（Postgres + Auth + Storage）。

## 目标架构
```
[React 前端] ←HTTPS→ [FastAPI 后端] → [agent 核心 LangGraph] → [自托管开源模型·GPU]
   (Vercel)            (Render/Fly)                                 (Runpod/Modal…)
                           ├→ [Supabase Postgres · 每人隔离(RLS)]
                           └→ [Supabase Storage · 每人照片]
   登录 ── JWT ──────────────┘
```

## 阶段（每阶段独立可跑通）
- [x] **Phase 1 · 后端骨架**：FastAPI 包住 agent 核心，`/api/turn`、`/api/pick`、`/api/ingest`、`/health` 能通过 HTTP 跑通（连本地 Ollama）。
- [ ] **Phase 2 · 数据库**：Supabase 建表（users / memories / sessions）+ 行级隔离；照片进 Storage；后端读写 DB 取代本地 JSON。
- [ ] **Phase 3 · 认证**：注册/登录 → JWT → 后端校验 → 所有数据按登录用户隔离。
- [ ] **Phase 4 · 前端**：React 重写三个模式（陪伴 / 记忆银行 / 存档），调后端 API。
- [ ] **Phase 5 · 部署**：前端 Vercel + 后端 Render + 模型上 GPU + 域名 HTTPS + CORS 收紧。
- [ ] **Phase 6 · 收尾**：同意条款/免责声明、危机资源、限流、安全审查。

## agent 核心（原样复用，跟平台解耦）
`backend/app/` 里的 `grounding_graph.py / tools.py / llm_config.py / vision_ingest.py`
就是原来那套 LangGraph 循环，一行没改。变的是外壳（HTTP + DB + 前端），不是大脑。
`memory_store.py` 是临时带过来的，Phase 2 会被 Supabase 版取代。
