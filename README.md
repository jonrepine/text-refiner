# Text Refiner

A small macOS daemon that lets you highlight text anywhere on your Mac,
double-tap **Right Option**, and have an LLM rewrite the selection in
place — clean up spelling, tighten prose, format as a Slack message,
turn it into a Notion-ready report, or improve a rough prompt before
sending it to another model.

The picker overlays on whatever app you're in, including fullscreen
Spaces. It uses the macOS Accessibility API to replace the selection
directly when the host app supports it, and falls back to the clipboard
for Electron-based apps (Cursor, VS Code, Chrome, etc).

Native Swift / AppKit for everything macOS-specific (hotkey, picker,
Accessibility, launchd), Python for the prompts and the LLM call.

## Requirements

- macOS 13 (Ventura) or later
- Xcode Command Line Tools (`xcode-select --install`)
- Python 3.10+ (`python3 --version`)
- An Anthropic API key (other providers planned — see
  [`docs/github-app-spec.md`](docs/github-app-spec.md))

## Install

```sh
git clone https://github.com/jonrepine/text-refiner.git ~/.local/text-refiner
cd ~/.local/text-refiner
./setup.sh
```

`setup.sh` creates a Python virtualenv at `~/.text-refiner/env`,
compiles the Swift daemon to `~/.text-refiner/TextRefinerNative`, signs
it ad-hoc with a stable code identifier, writes the LaunchAgent plist,
and starts the daemon.

Then store your API key in the macOS Keychain:

```sh
~/.text-refiner/env/bin/python3 - <<'PY'
import keyring
keyring.set_password("text-refiner", "api_key", "sk-ant-...your key...")
PY
```

## Grant permissions

The daemon needs two macOS permissions. Open
**System Settings → Privacy & Security**:

1. **Accessibility** → click **+** → press `⌘⇧G` → paste
   `/Users/<you>/.text-refiner/TextRefinerNative` → add it → toggle ON.
2. **Input Monitoring** → repeat the same steps.

If the daemon log says `Accessibility trust: NO`, toggle the permission
off and back on again — macOS sometimes leaves the toggle visually ON
while the underlying permission has been invalidated.

## Use it

1. Highlight text in any app.
2. Double-tap the **Right Option** key.
3. Pick a mode from the panel:

   | # | Mode | What it does |
   |---|------|--------------|
   | 1 | Spelling only | Fixes misspellings. Nothing else. |
   | 2 | Grammar | Fixes spelling, grammar, punctuation. Keeps phrasing. |
   | 3 | Improve Writing | Tighter, clearer, same meaning. Cuts filler. |
   | 4 | Slack | Succinct, warm, lowercase, no sign-off. |
   | 5 | Email | Polished, warm opener, ends with "Cheers,". |
   | 6 | Report | Notion-formatted with headings + emojis. |
   | 7 | Bullet Points | Scannable list of distinct ideas. |
   | 8 | Improve Prompt | Rewrites your input as a stronger LLM prompt. |
   | 9 | Custom... | Type a one-off instruction for this run. |
   | 0 | Cancel | Leave the text unchanged. |

You can press the digit (`1`–`9` or `0`) instead of clicking. Escape
also cancels.

## Configuration

`config/config.json` controls the model, timeout, and history settings.
Defaults:

```json
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 1024,
  "timeout_seconds": 45,
  "save_history": true,
  "history_limit": 50
}
```

History is written to `~/.text-refiner/history.json` (last 50 runs).
Disable it by setting `save_history` to `false`.

## How it works

```
launchd ──► TextRefinerNative (Swift)
              │ Hotkey, picker, Accessibility, clipboard fallback
              │
              └──► refiner_cli.py (Python)
                     │ Prompt lookup, Anthropic SDK call
                     │
                     └──► returns JSON {ok, text|error}
```

Read [`docs/learnings.md`](docs/learnings.md) for the longer story of
what tools worked for which part of this and why,
[`docs/model-comparison.md`](docs/model-comparison.md) for side-by-side
Haiku 4.5 vs Sonnet 4.6 outputs across all modes, and
[`docs/github-app-spec.md`](docs/github-app-spec.md) for the spec of
where this is headed (configuration UI, multi-provider support).

## Uninstall

```sh
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.textrefiner.plist
rm ~/Library/LaunchAgents/com.textrefiner.plist
rm -rf ~/.text-refiner
~/.text-refiner/env/bin/python3 - <<'PY'
import keyring
keyring.delete_password("text-refiner", "api_key")
PY
```

## License

[MIT](LICENSE).
