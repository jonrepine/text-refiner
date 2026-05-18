import AppKit
import ApplicationServices
import IOKit.hid

/// Wraps the two TCC permissions Text Refiner needs and exposes the API
/// surface used by the onboarding window.
enum Permissions {
    enum Kind {
        case accessibility
        case inputMonitoring
    }

    /// Reads the current grant state for `kind`. Does NOT prompt — that's the
    /// job of `requestPrompt(for:)`.
    static func isGranted(_ kind: Kind) -> Bool {
        switch kind {
        case .accessibility:
            return AXIsProcessTrusted()
        case .inputMonitoring:
            // `kIOHIDAccessTypeGranted` is the success return.
            let status = IOHIDCheckAccess(kIOHIDRequestTypeListenEvent)
            return status == kIOHIDAccessTypeGranted
        }
    }

    /// Asks macOS to show the standard system prompt for `kind`. The prompt
    /// only appears the first time per binary identity; afterwards the user
    /// has to flip the toggle in System Settings themselves.
    static func requestPrompt(for kind: Kind) {
        switch kind {
        case .accessibility:
            let options: NSDictionary = [
                kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true
            ]
            _ = AXIsProcessTrustedWithOptions(options as CFDictionary)
        case .inputMonitoring:
            _ = IOHIDRequestAccess(kIOHIDRequestTypeListenEvent)
        }
    }

    static func openSystemSettings(for kind: Kind) {
        let url: String
        switch kind {
        case .accessibility:
            url = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        case .inputMonitoring:
            url = "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
        }
        if let target = URL(string: url) {
            NSWorkspace.shared.open(target)
        }
    }
}
