import Foundation

/// The backend is just a **stateless agent brain**: it stores neither your photos nor your memory cards.
/// Each turn, we send up the memory library along with this conversation's state; once the turn finishes, it forgets everything.
///
/// The base URL and key come from Config.xcconfig (not checked into the repo); see Config.swift.
enum API {
    private static var base: String { Config.apiBase }

    private static func request(_ path: String, base overrideBase: String? = nil,
                                method: String = "POST") throws -> URLRequest {
        let b = overrideBase ?? base
        guard !b.isEmpty, let url = URL(string: b + path) else { throw APIError.notConfigured }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue(Config.apiKey, forHTTPHeaderField: "X-API-Key")   // without it the backend always returns 401
        req.timeoutInterval = 60
        return req
    }

    private static func send<T: Decodable>(_ req: URLRequest, as: T.Type) async throws -> T {
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw APIError.noResponse }
        guard http.statusCode == 200 else {
            if http.statusCode == 401 { throw APIError.unauthorized }
            let detail = String(data: data, encoding: .utf8) ?? "请求失败"
            throw APIError.server(code: http.statusCode, detail: detail)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    /// Run one companionship turn. The memory library goes up with the request.
    static func turn(_ body: TurnIn) async throws -> TurnOut {
        var req = try request("/api/turn")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(body)
        return try await send(req, as: TurnOut.self)
    }

    /// Upload a photo and have the vision model draft a memory card.
    /// The photo only passes through the backend's memory (one look, draft, discard); it never touches disk and no copy is kept.
    static func ingest(imageData: Data) async throws -> MemoryCard {
        var req = try request("/api/ingest")
        let boundary = "Boundary-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 120                     // looking at an image is slower than chatting; give it plenty of time

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        return try await send(req, as: IngestOut.self).draft
    }

    // MARK: - One-time migration (move photos and cards from the old backend back to the phone; once done, the old service can be shut down)

    /// Fetch all complete cards from the old backend.
    static func exportFromOldBackend() async throws -> [MemoryCard] {
        let req = try request("/api/export", base: Config.migrateBase, method: "GET")
        return try await send(req, as: [MemoryCard].self)
    }

    /// Fetch a photo's raw bytes from the old backend.
    static func photoFromOldBackend(_ id: String) async throws -> Data {
        let req = try request("/api/photo/\(id)", base: Config.migrateBase, method: "GET")
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.noResponse
        }
        return data
    }
}

enum APIError: LocalizedError {
    case notConfigured
    case noResponse
    case unauthorized
    case server(code: Int, detail: String)

    var errorDescription: String? {
        switch self {
        case .notConfigured: return "还没配置后端地址（Config.xcconfig）"
        case .noResponse:    return "没有连上后端，检查一下网络"
        case .unauthorized:  return "后端不认这个 key（401）"
        case .server(let code, _): return "后端出错（\(code)），稍等再试"
        }
    }
}
