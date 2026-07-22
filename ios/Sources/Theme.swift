import SwiftUI

/// 视觉基调：鼠尾草绿 + 暖米白 + Baskerville 衬线，跟网页版一致，安静、温柔。
enum Theme {
    static let sage = Color(red: 0x6f / 255, green: 0x8f / 255, blue: 0x7c / 255)
    static let sageDeep = Color(red: 0x54 / 255, green: 0x70 / 255, blue: 0x5f / 255)
    static let bg = Color(red: 0xf4 / 255, green: 0xf1 / 255, blue: 0xea / 255)
    static let ink = Color(red: 0x2c / 255, green: 0x33 / 255, blue: 0x2e / 255)

    static func serif(_ size: CGFloat) -> Font { .custom("Baskerville", size: size) }
    static let title = serif(21)
    static let body = serif(18)
    static let small = serif(14)
}
