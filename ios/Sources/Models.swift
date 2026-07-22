import Foundation

// 跟后端 api.py 的 pydantic 模型一一对应。

struct Msg: Codable {
    let role: String     // "me" | "companion"
    let text: String
}

/// 一张完整的回忆卡片。**这是个人数据，只存在手机上。**
/// 每一轮对话由客户端把整个记忆库发给后端；后端跑完就忘，不落盘。
struct MemoryCard: Codable, Identifiable, Equatable {
    var id: String
    var title: String = ""
    var whereText: String = ""
    var when: String = ""
    var who: String = ""
    var what_happened: String = ""
    var see: String = ""
    var hear: String = ""
    var touch: String = ""
    var smell_taste: String = ""
    var weather_temp: String = ""
    var food: String = ""
    var emotion: String = ""
    var grounding_questions: [String] = []

    // 后端字段名是 where —— 在 Swift 里是关键字，所以映射成 whereText
    enum CodingKeys: String, CodingKey {
        case id, title, when, who, what_happened, see, hear, touch
        case smell_taste, weather_temp, food, emotion, grounding_questions
        case whereText = "where"
    }

    init(id: String) { self.id = id }

    /// 宽容解码：视觉模型起草的草稿卡片**没有 id**，别的字段也可能缺。
    /// 缺什么就用空值，绝不因为少一个字段就整张卡片解不出来。
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func s(_ k: CodingKeys) -> String { ((try? c.decodeIfPresent(String.self, forKey: k)) ?? nil) ?? "" }
        id = s(.id)
        title = s(.title)
        whereText = s(.whereText)
        when = s(.when)
        who = s(.who)
        what_happened = s(.what_happened)
        see = s(.see)
        hear = s(.hear)
        touch = s(.touch)
        smell_taste = s(.smell_taste)
        weather_temp = s(.weather_temp)
        food = s(.food)
        emotion = s(.emotion)
        grounding_questions = ((try? c.decodeIfPresent([String].self, forKey: .grounding_questions)) ?? nil) ?? []
    }
}

/// 后端回给客户端的"当前这张是哪张"——只有 id 和标题，不含任何图片地址。
struct MemoryOut: Codable {
    let id: String
    let title: String
}

struct Avoid: Codable {
    let text: String
    let note: String
}

struct Contact: Codable {
    let contact_name: String
    let contact_note: String
}

struct TurnIn: Codable {
    let user_text: String
    let memories: [MemoryCard]   // ★ 记忆库随请求带上去；服务器不存
    let history: [Msg]
    let memory_id: String?
    let shown_ids: [String]
    let turn: Int
    let covered: [String]
    let arm: String
    let avoid: [Avoid]
    let avoid_recent: [String]   // 最近几次发作看过的照片 id（存在手机上，跨 session），开场避开
    let contact: Contact?
}

struct Crisis: Codable {
    let contact_name: String?
    let contact_note: String?
    let hotline: String?
}

struct TurnOut: Codable {
    let companion_message: String
    let memory: MemoryOut?
    let shown_ids: [String]
    let covered: [String]
    let turn: Int
    let action: String
    let done: Bool
    let photo_changed: Bool
    let crisis: Crisis?
    let emotional_read: String
    let pick_reason: String
    let reasoning: String?      // 为什么这么决定（可选，后端旧版没有也不会崩）
}

/// /api/ingest 的返回：视觉模型起草的卡片草稿（还没入库，等你补充确认）。
struct IngestOut: Codable {
    let draft: MemoryCard
}
