import Foundation

// One-to-one with the pydantic models in the backend's api.py.

struct Msg: Codable {
    let role: String     // "me" | "companion"
    let text: String
}

/// One complete memory card. **This is personal data; it lives only on the phone.**
/// Each conversation turn the client sends the whole memory library to the backend; the backend forgets it once the turn is done and never writes it to disk.
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

    // The backend field is named `where`, a keyword in Swift, so it maps to whereText
    enum CodingKeys: String, CodingKey {
        case id, title, when, who, what_happened, see, hear, touch
        case smell_taste, weather_temp, food, emotion, grounding_questions
        case whereText = "where"
    }

    init(id: String) { self.id = id }

    /// Lenient decoding: draft cards from the vision model **have no id**, and other fields may be missing too.
    /// Whatever is missing gets an empty value; never let one absent field make the whole card undecodable.
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

/// The backend's answer to "which photo is current": just the id and title, no image URL of any kind.
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
    let memories: [MemoryCard]   // ★ the memory library rides along with the request; the server stores nothing
    let history: [Msg]
    let memory_id: String?
    let shown_ids: [String]
    let turn: Int
    let covered: [String]
    let arm: String
    let avoid: [Avoid]
    let avoid_recent: [String]   // photo ids seen during recent episodes (stored on the phone, across sessions); avoid them at the start
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
    let reasoning: String?      // why it decided this (optional; older backends without it won't crash us)
}

/// Response from /api/ingest: the card draft the vision model wrote (not yet in the library; waiting for you to fill in and confirm).
struct IngestOut: Codable {
    let draft: MemoryCard
}
