import SwiftUI

/// agent 这一轮"怎么想的"（后端本来就传，之前没显示）。
struct ThinkInfo: Codable {
    let emotionalRead: String     // 读到的情绪
    let action: String            // ask / switch_photo / summarize / offer_end / farewell / use_tool
    let pickReason: String        // 为什么选/换这张照片
    let reasoning: String         // 为什么这么决定

    /// 把动作代码翻成人话
    var actionCN: String {
        switch action {
        case "ask": return "继续温柔地问"
        case "switch_photo": return "换了一张更贴合的照片"
        case "summarize": return "看你平稳了，回顾一下"
        case "offer_end": return "问问要不要结束"
        case "farewell": return "温柔告别"
        case "use_tool": return "危机支持（联系可信的人）"
        default: return action
        }
    }
}

/// 界面上的一条消息。可 Codable，用来存历史。
struct ChatMsg: Identifiable, Codable {
    var id = UUID()
    let role: String            // "me" | "companion"
    let text: String
    var photoId: String? = nil
    var think: ThinkInfo? = nil
}

/// 这次对话的全部状态、以及整个记忆库，都在客户端。
/// 后端是无状态的：每一轮我们把状态 + 记忆库卡片一起发过去，它跑完就忘。
@MainActor
final class ChatModel: ObservableObject {
    @Published var messages: [ChatMsg] = []
    @Published var input: String = ""
    @Published var sending = false
    @Published var crisis: Crisis? = nil
    @Published var done = false
    @Published var errorText: String? = nil

    /// 记忆库（照片 + 卡片都在手机上）。发请求时随身带上去。
    private let library: LibraryStore
    init(library: LibraryStore) { self.library = library }

    // 发回后端的对话状态
    private var memoryId: String? = nil
    private var shownIds: [String] = []
    private var turn = 0
    private var covered: [String] = []

    // 这次对话在历史里的 id（每次「新的一次」换一个）
    private var sessionId = UUID()

    // 跨 session 记住"最近看过哪些照片"（存手机，重启也在），开场避开，防止每次发作都看同一张而麻木。
    private let recentKey = "recentShownIds"
    private var recentShown: [String] {
        get { UserDefaults.standard.stringArray(forKey: recentKey) ?? [] }
        set { UserDefaults.standard.set(Array(newValue.suffix(12)), forKey: recentKey) }  // 只留最近 12 张
    }
    private func recordShown(_ id: String?) {
        guard let id, !id.isEmpty else { return }
        recentShown = recentShown.filter { $0 != id } + [id]
    }

    func reset() {
        // 开新的一次之前，当前这次已经在每轮自动存过历史了，直接换新 session 即可
        messages = []
        input = ""
        sending = false
        crisis = nil
        done = false
        errorText = nil
        memoryId = nil
        shownIds = []
        turn = 0
        covered = []
        sessionId = UUID()
    }

    func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        guard !library.isEmpty else {
            errorText = "记忆库还是空的，先去加几张照片吧"
            return
        }
        input = ""
        errorText = nil
        messages.append(ChatMsg(role: "me", text: text))
        sending = true

        Task {
            do {
                // history = 这条 user 消息之前的所有消息
                let hist = messages.dropLast().map { Msg(role: $0.role, text: $0.text) }
                let body = TurnIn(
                    user_text: text,
                    memories: library.cards,          // ★ 记忆库随请求上去，服务器不存
                    history: Array(hist),
                    memory_id: memoryId,
                    shown_ids: shownIds,
                    turn: turn,
                    covered: covered,
                    arm: "agent",
                    avoid: [],
                    avoid_recent: recentShown,
                    contact: ContactStore.contact
                )
                let out = try await API.turn(body)

                // 首轮，或这一轮换了照片 → 把照片挂到这条陪伴消息上显示
                let showPhoto = (memoryId == nil) || out.photo_changed
                if showPhoto { recordShown(out.memory?.id) }   // 记进"最近看过"，下次发作避开

                memoryId = out.memory?.id
                shownIds = out.shown_ids
                covered = out.covered
                turn = out.turn
                done = out.done
                crisis = out.crisis

                messages.append(ChatMsg(
                    role: "companion",
                    text: out.companion_message,
                    photoId: showPhoto ? out.memory?.id : nil,
                    think: ThinkInfo(
                        emotionalRead: out.emotional_read,
                        action: out.action,
                        pickReason: out.pick_reason,
                        reasoning: out.reasoning ?? ""
                    )
                ))
                HistoryStore.save(id: sessionId, messages: messages)   // 每轮自动存进手机本地历史
            } catch {
                errorText = error.localizedDescription
            }
            sending = false
        }
    }
}
