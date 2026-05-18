import Foundation

/// Tiny global logger that flushes stdout so the launchd-captured log file
/// stays in step with what the daemon is doing.
func log(_ message: String) {
    print(message)
    fflush(stdout)
}
