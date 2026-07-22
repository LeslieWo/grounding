import Foundation

/// 后端只是一个**无状态的 agent 大脑**：它不存你的照片，也不存你的回忆卡片。
/// 每一轮，我们把记忆库和这次对话的状态一起发上去，它跑完一轮就忘掉。
///
/// 地址和 key 来自 Config.xcconfig（不进仓库），见 Config.swift。
enum API {
    private static var base: String { Config.apiBase }

    private static func request(_ path: String, base overrideBase: String? = nil,
                                method: String = "POST") throws -> URLRequest {
        let b = overrideBase ?? base
        guard !b.isEmpty, let url = URL(string: b + path) else { throw APIError.notConfigured }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue(Config.apiKey, forHTTPHeaderField: "X-API-Key")   // 没有它后端一律 401
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

    /// 跑一轮陪伴。记忆库跟着请求一起上去。
    static func turn(_ body: TurnIn) async throws -> TurnOut {
        var req = try request("/api/turn")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(body)
        return try await send(req, as: TurnOut.self)
    }

    /// 上传一张照片，让视觉模型起草一张回忆卡片草稿。
    /// 照片只穿过后端的内存（看一眼、起草、丢掉），不落盘、不留副本。
    static func ingest(imageData: Data) async throws -> MemoryCard {
        var req = try request("/api/ingest")
        let boundary = "Boundary-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 120                     // 看图比说话慢，给足时间

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        return try await send(req, as: IngestOut.self).draft
    }

    // MARK: - 一次性搬家（把照片和卡片从旧后端搬回手机，搬完旧服务就可以关掉）

    /// 从旧后端取回全部完整卡片。
    static func exportFromOldBackend() async throws -> [MemoryCard] {
        let req = try request("/api/export", base: Config.migrateBase, method: "GET")
        return try await send(req, as: [MemoryCard].self)
    }

    /// 从旧后端取回一张照片的原始字节。
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
