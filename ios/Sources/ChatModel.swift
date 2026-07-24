import SwiftUI

/// What the agent was "thinking" this turn (the backend always sent this; we just never showed it before).
struct ThinkInfo: Codable {
    let emotionalRead: String     // the emotion it read
    let action: String            // ask / switch_photo / summarize / offer_end / farewell / use_tool
    let pickReason: String        // why it picked / switched to this photo
    let reasoning: String         // why it decided this

    /// Translate the action code into plain language
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

/// One message in the UI. Codable so it can be saved to history.
struct ChatMsg: Identifiable, Codable {
    var id = UUID()
    let role: String            // "me" | "companion"
    let text: String
    var photoId: String? = nil
    var think: ThinkInfo? = nil
}

/// All of this conversation's state, plus the entire memory library, lives on the client.
/// The backend is stateless: each turn we send the state + memory cards along; once it finishes the turn, it forgets.
@MainActor
final class ChatModel: ObservableObject {
    @Published var messages: [ChatMsg] = []
    @Published var input: String = ""
    @Published var sending = false
    @Published var crisis: Crisis? = nil
    @Published var done = false
    @Published var errorText: String? = nil

    /// The memory library (photos + cards both live on the phone). Carried along with every request.
    private let library: LibraryStore
    init(library: LibraryStore) { self.library = library }

    // Conversation state sent back to the backend
    private var memoryId: String? = nil
    private var shownIds: [String] = []
    private var turn = 0
    private var covered: [String] = []

    // This conversation's id in history (a fresh one for every "start over")
    private var sessionId = UUID()

    // Remember "which photos were seen recently" across sessions (stored on the phone, survives restarts); avoid them at the start of a session, so she doesn't see the same photo every episode and grow numb to it.
    private let recentKey = "recentShownIds"
    private var recentShown: [String] {
        get { UserDefaults.standard.stringArray(forKey: recentKey) ?? [] }
        set { UserDefaults.standard.set(Array(newValue.suffix(12)), forKey: recentKey) }  // keep only the most recent 12
    }
    private func recordShown(_ id: String?) {
        guard let id, !id.isEmpty else { return }
        recentShown = recentShown.filter { $0 != id } + [id]
    }

    func reset() {
        // Before starting a new session, the current one has already been auto-saved to history every turn, so just switch to a new session
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
                // history = every message before this user message
                let hist = messages.dropLast().map { Msg(role: $0.role, text: $0.text) }
                let body = TurnIn(
                    user_text: text,
                    memories: library.cards,          // ★ memory library goes up with the request; the server stores nothing
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

                // First turn, or the photo changed this turn → attach the photo to this companion message for display
                let showPhoto = (memoryId == nil) || out.photo_changed
                if showPhoto { recordShown(out.memory?.id) }   // record into "recently seen" so the next episode avoids it

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
                HistoryStore.save(id: sessionId, messages: messages)   // auto-save to on-device history every turn
            } catch {
                errorText = error.localizedDescription
            }
            sending = false
        }
    }
}
