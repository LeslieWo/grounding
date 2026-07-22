# Wall-Log — Grounding Agent

> 每次现成工具/库/服务做不到你 agent 需要的事，就是一堵墙，记一行。
> 反复出现的墙 = 当前 agent infra 的缺口 = 你「X for agent」的候选。
>
> **纪律 1：当场记**（撞墙那一刻，不是晚上——晚上你只记得「绕过去了」）。
> **纪律 2：记墙，不记绕法**（绕法是临时补丁；墙才是产品）。
>
> 撞满 ~20 行后，把「根因」那列聚类。重复出现的 2-3 个根因，就是你的 X。
>
> **两个桶——别混，混了信号就死：**
> - `[GOTCHA]` = 已经有好解法，只是烦人的配置/兼容坑。记它是为了省未来的你时间。**不是** X。
> - `[GAP]` = 没有好解法、只能硬绕。**这才是候选 X。** 聚类时只盯这一类。
> 每行在「根因」列前打上标签。

## 地形图 / Watch list（横向 agent infra 栈——内容无关，边建边对照）

> 核心判断：越靠 cloud/big/enterprise 越挤(红海)；越靠 **local/small/private/edge/低延迟** 越空。
> 你这个项目的硬约束(本地·离线·on-device 小 VLM·隐私·panic 级延迟)把每块都推进那个没人服务的边缘角 → **约束就是 wedge**。

| 栈里的一块 | 已知的墙 | 先验 | 备注 |
|---|---|---|---|
| VLM 看图 | 小/本地 VLM 结构化抽取质量、幻觉、延迟 | GOTCHA（"本地小 VLM 可靠抽取"偏 GAP） | 已撞#1 |
| 缓存 | 多步/分支中间结果、plan 复用缓存没人做好 | 偏 GAP | prompt cache 本身是 GOTCHA |
| 反应速度 | 串行 LLM 调用延迟累加 | **GAP（本地+危机级延迟）** | 云端延迟是 GOTCHA |
| token 消耗 | 每步重发 context、长记忆烧钱 | 半 GOTCHA | context 压缩有人做 |
| LLM 记忆 | 本地/私有记忆、"记忆有没有用"的 eval、结果条件化检索 | GAP | 通用长期记忆是 GOTCHA(Mem0/Zep)；**已撞#2**(选片=情绪调节检索无效力信号) |
| fine-tuning | 何时 tune vs RAG、数据生成、评估 | GOTCHA | 工具成熟 |
| **agent eval** | 多步/轨迹/非确定/开放任务无 GT/结果 vs 过程 | **强 GAP（尤其 outcome 向）** | ★ 重点蹲守；**已撞#3**(agent 决策轨迹只能手搓场景眼看) |
| **mem planning** | 记什么/何时写/何时调；把记忆当 plan 规划 | **GAP** | ★ 重点蹲守 |

★ 三个最可能出真 GAP：**agent eval(outcome 向)、mem planning、local/低延迟 caching**。

## 记录表

| # | 日期 | 哪一步 | 我需要它做什么 | 用了什么现成工具 | 它怎么没做到（具体） | 我只能怎么绕 | 根因：缺的是什么 |
|---|------|--------|----------------|------------------|----------------------|--------------|------------------|
| 1 | 07-02 | 建记忆库(读图→结构化 MemoryCard) | 同一个模型既看图、又输出 13 字段结构 | Ollama qwen2.5-VL + LangChain `.with_structured_output(method="function_calling")` | qwen2.5vl:7b 在 Ollama 不支持 tools，function_calling 路径直接报错 | 改用 `method="json_schema"`(Ollama format 约束解码，不走 tool) | `[GOTCHA]` 结构化输出机制因后端而异(function_calling / json_schema / json_mode)，无跨后端统一原语；vision 模型尤其常不支持 tool 路径。已有解法，非 X |
| 2 | 07-02 | 选片(读情绪→挑最能安抚的照片) | 挑"对当前情绪状态最有调节效力"的那张 | LLM prompt 读感受语义 + json_schema 输出 chosen_id | LLM 只按画面气质/语义匹配("冷"→"温暖海边")，没 grounded 在"这张对这个状态真的有调节效果"的信号上；也无从验证挑得对不对 | 信 LLM 语义直觉，人工眼看它给的理由说不说得通 | `[GAP]` 缺"面向情绪/状态调节**结果**"的检索信号与 eval——现成 embedding/检索只编码语义相关度，没有"调节效力"维度。★命中示例墙 |
| 3 | 07-02 | agent 决策循环(每轮决定 ask/switch/close) | 判断"agent 这串决策是否真把人从闪回带回安全" | 手搓 2-3 个情绪弧场景，眼看每步决策合不合理 | 只能验证单点"这一步看着合理"，量不了整条轨迹的**结果**(有没有真 ground 下来)；无 GT、非确定、开放任务 | 手工造场景 + 主观 y/n | `[GAP]` agent eval(**outcome 向**)——多步/轨迹任务缺"过程合理→结果达成"的评估。★强 GAP，重点蹲守 |
| 4 | 07-03 | 给 agent 加工具(危机升级=端出可信联系人) | 让本地模型原生 tool-calling(bind_tools/ToolNode) | Ollama qwen2.5-VL + LangChain 原生 tools | 视觉模型在 Ollama 不支持 tools，`bind_tools` 那条工业标准路径直接走不通 | 用 json_schema 手搓整个 ReAct 工具循环(Decision 加 use_tool + 注册表 + run_tool 节点 + 回灌) | `[GOTCHA]偏GAP` 本地/私有 agent 没有可移植的 tool-use 原语，每套本地栈都要手工重建 ReAct；跟"结构化输出机制因后端而异"#1 同源。要 native tools 得拆双模型(文字模型跑 agent + VL 只管看图) |
| 5 | 07-03 | 多模型 agent 编排(decide 用 7B、compose 用 32B) | 每轮该用哪个模型就调哪个，省算力 | Ollama 本地(48G 统一内存)+ 双模型 | 内存装不下两个，每换模型要踢旧(21GB)、从硬盘重装新，swap 本身几十秒；7B 反而比 32B 慢(53s vs 47s)，越"优化"越慢=thrashing | 整个对话只用一个常驻模型，不换 | `[GOTCHA]偏GAP` 本地多模型 agent 编排是内存/thrashing-bound，cloud 永不遇到；无"本地不 thrash 跑多模型 agent"的原语。且暴露真实延迟地板(32B ~40s/call 对危机工具太慢)——正是 local+危机延迟这个 wedge 角 |
| 6 | 07-04 | 换云端前沿模型(GLM-4.6/z.ai)替代本地 7b | 危机级低延迟 + 前沿中文质量的陪伴 | z.ai GLM-4.6 OpenAI 兼容接口 + LangChain ChatOpenAI | 默认开"深度思考(thinking)"，一句话回复要 12-35s；上云本身没解决延迟，reasoning-on 反而比本地 7B 还慢 | `extra_body={"thinking":{"type":"disabled"}}` 关掉 → 2s | `[GOTCHA]` 云端前沿模型的"默认推理模式"让延迟不可预测，"上云=快"是错觉；低延迟仍要显式管理(关 thinking/选非推理档)。与 local 那堵墙对称：local 延迟是内存/thrash-bound，cloud 延迟是 reasoning-mode-bound |
| 7 | | | | | | | |
| 8 | | | | | | | |

---

## 示例（撞到类似的就照这个粒度记，然后删掉这段）

| # | 日期 | 哪一步 | 我需要它做什么 | 用了什么现成工具 | 它怎么没做到 | 我只能怎么绕 | 根因 |
|---|------|--------|----------------|------------------|--------------|--------------|------|
| ex | 07-02 | 检索 | 按「哪张能让我平静」捞图 | CLIP embedding + 余弦相似度 | embedding 只编码视觉/语义，没有「情绪调节效力」这个维度 | 全靠手工打标签 | 没有为「情感/状态调节」目标优化的 embedding 和检索 |
| ex | 07-02 | 状态→策略 | 把「我在解离」映射到「调强触觉锚」 | 一段 prompt | 没有干净办法存/表达「每种状态对应的检索策略」 | 硬写 if/else | 缺「状态条件化检索策略」这个抽象 |
| ex | 07-02 | eval | 量「这次检索有没有把状态调节下来」 | 找遍了没有 | 现成 eval 全是量相关度，没有量「检索→情绪结果」的 | 只能自己 y/n 手评 | 没有面向「结果」而非「相关度」的检索 eval |

---

## 根因聚类（撞满 20 行后再填）

- 反复出现的根因 A：
- 反复出现的根因 B：
- → 候选 X for agent：
