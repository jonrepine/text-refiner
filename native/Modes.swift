import Foundation

/// One row in the picker. The `isCustom` and `isCancel` flags drive the
/// special-case behavior in the controller so we never key off magic IDs.
struct Mode {
    let id: Int
    let name: String
    let detail: String
    var isCustom: Bool = false
    var isCancel: Bool = false
}

/// The picker is rendered in the order below. Digit shortcuts come from `id`,
/// so each id has to be a single character in `0`-`9`.
let modes: [Mode] = [
    Mode(id: 1, name: "Spelling only",  detail: "spelling fixes, nothing else"),
    Mode(id: 2, name: "Grammar",        detail: "grammar, punctuation + spelling"),
    Mode(id: 3, name: "Improve Writing", detail: "tighter, clearer · same meaning"),
    Mode(id: 4, name: "Slack",          detail: "succinct · warm · lowercase"),
    Mode(id: 5, name: "Email",          detail: "polished · ends with cheers"),
    Mode(id: 6, name: "Report",         detail: "notion-formatted · layered"),
    Mode(id: 7, name: "Bullet Points",  detail: "scannable · discrete ideas"),
    Mode(id: 8, name: "Improve Prompt", detail: "rewrite for an LLM"),
    Mode(id: 9, name: "Custom...",      detail: "type your own instruction", isCustom: true),
    Mode(id: 0, name: "Cancel",         detail: "leave text unchanged",       isCancel: true),
]
