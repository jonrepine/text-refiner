# Text Refiner — Distributable GitHub App Specification

A specification for converting the current macOS Text Refiner daemon into an
installable application that any GitHub user can fork, configure, and run on
their own machine, with a settings UI, multi-provider model selection, and a
modern loading indicator.

This is a developer-facing document. Sections are ordered the way a developer
would implement them. Rationale is included inline where a choice deserves
context.

---

## 1. Goals and scope

The current app is a personal macOS LaunchAgent that talks to one provider.
The goal is to make it:

- **Installable from a GitHub repository** by any reasonably technical macOS
  user, with one command.
- **Configurable through a UI** instead of by editing files. Defaults stay
  curated; users can add their own modes; a small set of locked modes (such
  as "Cancel") cannot be removed.
- **Multi-provider**. Users can supply API keys for Anthropic, OpenAI, Kimi,
  and Google Gemini, pick from a curated dropdown of each provider's primary
  models, or paste a custom model slug.
- **Visually polished**. The picker and loading indicator should feel native
  to macOS, follow the user's Light/Dark mode, and use the system accent
  colour as the one functional pop of colour.

Out of scope for v1:

- Windows / Linux support. Cross-platform input synthesis and clipboard
  semantics are a separate project.
- A hosted SaaS version. The app stays on-device and keys never leave the
  user's machine.

---

## 2. Distribution and installation

### 2.1 Repository shape

Public GitHub repository, `text-refiner`, with the following top level:

```
text-refiner/
├── native/             Swift source
├── refiner/            Python prompts + Anthropic / OpenAI / Gemini SDK
├── ui/                 (optional) preferences app source
├── config/             default config + JSON schema
├── docs/               learnings, this spec, model-comparison
├── scripts/            install + uninstall + tooling
├── requirements.txt
├── setup.sh            primary entry point
└── uninstall.sh        clean removal
```

### 2.2 Install command

A user installs the app with:

```sh
git clone https://github.com/<owner>/text-refiner ~/.local/text-refiner
~/.local/text-refiner/setup.sh
```

`setup.sh` is idempotent and:

1. Creates `~/.text-refiner/env` (Python venv) and installs from
   `requirements.txt`.
2. Compiles `native/*.swift` to `~/.text-refiner/TextRefinerNative`.
3. Re-signs the binary ad-hoc with a stable identifier
   (`com.textrefiner.native`) so TCC permissions persist across upgrades.
4. Writes `~/Library/LaunchAgents/com.textrefiner.plist` with absolute
   user paths, loads it, and kickstarts the daemon.
5. Prints a short list of system settings to grant
   (Accessibility, Input Monitoring) and a verification command.

**Rationale**: `~/.local/text-refiner` and `~/.text-refiner` are kept
separate. The first is the cloned source (read-only, easy to git pull); the
second is the runtime install (venv, plist, log, keychain entry, compiled
binary). A user can wipe the runtime without losing local edits.

### 2.3 Upgrade

```sh
cd ~/.local/text-refiner && git pull && ./setup.sh
```

Re-running `setup.sh` rebuilds the binary with the same stable code
identifier, so previously granted Accessibility and Input Monitoring
permissions remain valid.

### 2.4 Uninstall

`uninstall.sh` removes the LaunchAgent, kills the daemon, deletes
`~/.text-refiner`, and offers (with confirmation) to also delete the
Keychain entry. It does not remove the cloned repo.

### 2.5 Release process

Tag-based releases on GitHub. Each release ships:

- A `setup.sh` that is backwards-compatible (it can migrate older configs).
- A `CHANGELOG.md` snippet generated from commit messages between tags.
- A `requirements.txt` pinned to versions known to work.

Distribution is git-only in v1 — no Homebrew tap, no signed installer. Both
are noted as follow-ups in §10.

---

## 3. Configuration interface

### 3.1 What the user can configure

| Setting              | Type            | Notes |
| -------------------- | --------------- | ----- |
| Trigger shortcut     | Enum             | "Double-tap Right Option" (default). Reserved space for "Custom" later. |
| Default model        | Provider + slug  | See §4. |
| Max tokens           | Integer          | 32–8192. Default 1024. |
| Timeout (seconds)    | Integer          | 5–120. Default 45. |
| Save history         | Bool             | Default true. History file at `~/.text-refiner/history.json`. |
| History limit        | Integer          | 1–500. Default 50. |
| Show toasts          | Bool             | Default true. |
| Modes (refinement)   | List of objects  | See §3.3. |

Stored as a single JSON file at `~/.text-refiner/config.json`. A JSON Schema
ships in `config/config.schema.json` so editors validate it.

### 3.2 Settings UI

A small SwiftUI preferences window, opened either:

- by clicking a menu-bar item that the daemon installs, or
- by running `text-refiner settings` from a shell.

The preferences window has three tabs:

1. **General** — trigger shortcut, history toggle and limit, show toasts.
2. **Modes** — full list of refinement modes, with locked rows clearly marked.
3. **Providers** — API keys, model selection (see §4).

Visual style follows the existing picker: `NSVisualEffectView` HUD
background, rows with `NSColor.controlBackgroundColor` at low alpha,
`NSColor.controlAccentColor` for the single piece of colour (selected row
ring and active toggle states). No custom colours, no custom fonts —
everything inherits from the user's system appearance.

### 3.3 Modes editor

Each mode is a JSON object:

```json
{
  "id": "spelling",
  "name": "Spelling",
  "detail": "fix spelling only",
  "prompt": "You are a careful proofreader…",
  "locked": false,
  "builtin": true,
  "shortcut": "1"
}
```

- `id` is a stable string (not a number) so user additions don't collide
  with built-in IDs.
- `builtin` flags whether the mode shipped in the install. Built-in modes
  can be edited but not deleted.
- `locked` flags whether the mode is fundamentally part of the picker
  contract. `cancel` is the only `locked: true` mode by default — it can be
  neither edited nor deleted nor reordered. The UI gates these operations:
  the row shows a small lock glyph, the **Delete**, **Edit prompt**, and
  **Set shortcut** controls are disabled, and a tooltip explains why.
- A "Reset to defaults" button restores any built-in modes the user edited,
  without touching their custom additions.

User custom modes can be added by clicking **+**. Each new mode gets an
auto-generated `id` (kebab-case from name) and is appended to the end of
the picker, with the next available digit shortcut (the first free of
`0`–`9`). The picker shows at most ten modes — anything beyond ten is in
the list but lacks a digit shortcut, and the row label communicates this.

**Rationale**: locking is enforced *both* in the UI (controls disabled,
visual indicator, tooltip) *and* in the config-write path (the settings
writer rejects writes that try to delete or unlock a `locked: true` mode).
The UI alone is not sufficient — a user editing `config.json` directly
should also be protected from accidentally removing core behaviour.

---

## 4. AI provider and model selection

### 4.1 Supported providers

| Provider   | SDK             | Default flagship models in dropdown |
| ---------- | --------------- | ----------------------------------- |
| Anthropic  | `anthropic`     | `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, `claude-opus-4-7` |
| OpenAI     | `openai`        | `gpt-5.5-extra-high`, `gpt-5.4-medium`, `gpt-5-haiku` |
| Kimi       | `openai` (compat) | `kimi-k2`, `kimi-k1.5` |
| Gemini     | `google-genai`  | `gemini-2.5-pro`, `gemini-2.5-flash` |

The dropdown is generated from a small JSON file
(`config/providers.json`) that ships in the repo, so a new model can be
surfaced by editing one file and re-installing — no SDK changes needed.

### 4.2 UI

The Providers tab is one section per provider, each containing:

1. **API key** field. `NSSecureTextField`. A "Show" button toggles
   visibility. Below the field, a small status reads "Stored in Keychain"
   (and shows the entry name) once the user has saved a key.
2. **Model** picker, an `NSPopUpButton`. The first items are the curated
   models for the provider. The last item is **Custom slug…**, which
   reveals an `NSTextField` below the picker for entering an arbitrary
   model ID. The custom slug persists with the rest of the settings; if
   the user later selects a built-in model, the custom slug is remembered
   in config but not active.
3. A **Test** button. Pressing it sends a one-token "ping" request to the
   provider and reports success or a humanised error inline.

Only the active provider (the one selected on the General tab as "Default
provider") is required to have a key. Other providers can sit blank.

### 4.3 Storage

Keys are never written to `config.json`. They live in the macOS Keychain
under `text-refiner` service, one item per provider:

```
keychain service: "text-refiner"
account:          "anthropic" | "openai" | "kimi" | "gemini"
password:         <API key>
```

The Python helper reads keys at runtime via `keyring`. Removing a provider
in the UI deletes the corresponding Keychain item.

### 4.4 Switching providers per mode

Each mode in `config.json` can optionally override the default provider and
model. The Modes editor exposes this as two extra fields under each mode
("Provider: default / specific provider", "Model: default / specific
model"). This lets a power user route, say, "Improve Prompt" to Sonnet 4.6
while keeping "Spelling" on Haiku.

**Rationale**: keeping the override at the mode level avoids a complicated
per-request routing UI. Most users set one default; advanced users override
where it matters.

---

## 5. Loading state

### 5.1 Visual design

A small, centred-bottom HUD panel, similar in size and material to the
success toast already shipped:

- Width 240, height 44. `NSVisualEffectView` with `.hudWindow` material.
- 16-pt corner radius. Subtle separator-coloured 0.5-pt border.
- Single line of text: `Refining · <mode name>…` in 12-pt medium
  `labelColor`.
- A 14-pt circular `NSProgressIndicator` configured as
  `.spinning` style, sized small, on the left of the label, in the system
  accent colour.
- No close button, no chrome. The HUD is not interactive.

### 5.2 Behaviour

- Appears the moment the user picks a mode and the refinement request is
  dispatched.
- Stays on top of the active app (`NSWindow.Level.screenSaver`, transient
  collection behaviour), visible over fullscreen Spaces.
- Fades in over 80 ms (opacity 0→1) so it doesn't pop.
- Fades out over 120 ms once the helper returns (success or failure).
- On failure, smoothly cross-fades into the error toast at the same
  bottom-centre position so the user feels one continuous overlay rather
  than two competing ones.

### 5.3 Rationale

A bottom-centre HUD keeps the user's eye on their text. A centre-of-screen
modal would make a 1–3 second wait feel disruptive. The spinner is small
and on the accent colour because that's the only place colour is justified
— it signals "something is happening" without being decorative.

---

## 6. Accessibility and permissions UX

### 6.1 First-run flow

When the daemon starts it calls `AXIsProcessTrustedWithOptions` with
`kAXTrustedCheckOptionPrompt = true`. If untrusted, macOS shows the standard
"app needs Accessibility access" alert with a button that deep-links to the
Privacy pane.

Independently, the menu-bar item shows a yellow status dot when Accessibility
or Input Monitoring is not trusted, and clicking it opens a help screen with
the two steps:

1. Open Privacy & Security → Accessibility, toggle `TextRefinerNative` off
   then on.
2. Open Privacy & Security → Input Monitoring, toggle off then on.

When both are trusted, the dot turns the system accent colour.

### 6.2 Logging

`~/.text-refiner/text-refiner.log` always begins with an `Accessibility
trust: YES/NO` line. The help screen in the menu-bar item has a "Show log"
button that opens this file. This is the single source of truth when
diagnosing why a run failed.

---

## 7. Picker UX refinements

The picker is largely already implemented. The remaining polish items:

- **Spacing**. The header gets a tighter top inset (10 pt) and the right
  hint sits at the same baseline as the title. List rows get a slightly
  taller height (44 pt) and 4 pt of inter-row spacing so the list breathes.
- **Accent colour**. The digit on the left of each row is rendered in the
  system accent colour for active modes, `tertiaryLabelColor` for the
  Cancel row. This is the only coloured element in the panel.
- **Consistency**. All panels (picker, status HUD, success toast, error
  toast) use the same `Metrics` struct for paddings, corner radii, and
  inter-element spacing. Adjustments live in one place.
- **Keyboard**. Digit keys 0–9 select rows directly. Escape cancels. The
  panel is `OverlayPanel: NSPanel` with `canBecomeKey = true`, otherwise
  digit keys pass through to the app behind it.

---

## 8. Architecture

```
┌──────────────────────────────────────────────┐
│ TextRefinerNative (Swift, launchd)           │
│                                              │
│  Hotkey ───► triggers refinement             │
│             │                                │
│             ▼                                │
│  Selection (Accessibility or clipboard)      │
│             │                                │
│             ▼                                │
│  Picker (NSPanel over fullscreen)            │
│             │                                │
│             ▼                                │
│  RefinerHelper ──► spawns Python subprocess  │
│                                              │
└────────────────────┬─────────────────────────┘
                     │ JSON over stdin / stdout
                     ▼
┌──────────────────────────────────────────────┐
│ refiner_cli.py (Python)                      │
│                                              │
│  Load mode prompt + provider config          │
│  Call provider SDK (Anthropic / OpenAI /     │
│   Kimi / Gemini)                             │
│  Optionally write history                    │
│  Print {"ok": bool, "text": …} on stdout     │
│                                              │
└──────────────────────────────────────────────┘
```

Module responsibilities (Swift, after refactor):

| File              | Responsibility |
| ----------------- | -------------- |
| `Modes.swift`     | `Mode` struct, the built-in modes list, the `isCustom` and `isCancel` flags that drive picker behaviour. |
| `Hotkey.swift`    | `DoubleTapDetector` — owns the `CGEventTap`, debounces Right Option taps into a double-tap. |
| `Selection.swift` | `Selection` (Accessibility) and `Clipboard` (fallback) helpers. |
| `KeySynthesis.swift` | `sendCommandShortcut(keyCode:)` — synthesizes ⌘C and ⌘V the right way. |
| `Picker.swift`    | `OverlayPanel` (key-receiving NSPanel), `Picker` enum (chooseMode, showStatus, showToast), `ChoiceController`. |
| `RefinerHelper.swift` | Spawns the Python helper subprocess; JSON-encodes the request and parses the response. |
| `Logger.swift`    | Tiny global `log(_:)` that flushes stdout for launchd's log capture. |
| `main.swift`      | `AppDelegate`, wires the pieces together, owns the trigger lifecycle. |

Rule of thumb: anything macOS-specific stays in Swift; anything model- or
prompt-specific stays in Python. The boundary is JSON over a pipe, so each
side can be replaced independently.

---

## 9. Data flow for one refinement

1. User selects text in any app.
2. `Hotkey.DoubleTapDetector` fires.
3. `AppDelegate.trigger()` runs on main thread.
4. `Selection.focusedElement()` is asked for the AX element.
5. If present and `kAXSelectedText` is readable → path A.
   Otherwise → `Clipboard.grabSelection` synthesizes `⌘C`, waits for the
   pasteboard's `changeCount` to bump → path B.
6. `Picker.chooseMode()` shows the panel and blocks on a modal session.
7. `Picker.showStatus(…)` displays the HUD.
8. `RefinerHelper.run(text:mode:customPrompt:)` shells out to Python,
   collects the JSON response.
9. On success:
   - Path A: `Selection.writeSelectedText` puts the new text in place via
     Accessibility. No paste needed.
   - Path B: `Clipboard.paste` reactivates the source app, writes to the
     pasteboard, synthesizes `⌘V`. Shows the `✓ Pasted` toast.

---

## 10. Open questions and follow-ups

- **Signed installer**. Ad-hoc signing is enough for personal use but a
  Developer ID-signed app and notarisation would make the install
  one-click and remove the toggle-off-toggle-on workaround when permissions
  are first granted.
- **Homebrew tap**. A `brew install <owner>/text-refiner/text-refiner`
  formula could wrap the install script and the launchd registration.
- **Custom shortcut**. Right now the trigger is hard-coded to double-tap
  Right Option. The UI should expose this, but the implementation needs
  care: shortcuts that include character keys can leak into editable
  fields, as documented in `learnings.md`.
- **History UI**. The on-disk history is already there; surfacing it as a
  searchable picker (read-only) would let users recover a previous
  refinement they wish they hadn't replaced.
- **Provider failover**. When the active provider errors with a
  rate-limit or timeout, retry the request against a configured fallback
  provider transparently.

---

## 11. Acceptance criteria

A reasonable v1 of this spec is shipped when:

1. A new user can install the app from a fresh GitHub clone in under three
   commands and have it working in any native macOS app.
2. The preferences window opens, persists, and validates all three tabs.
3. At least two of the four providers (Anthropic + OpenAI is sufficient)
   work end-to-end through the UI, with keys in Keychain.
4. Locked modes cannot be deleted from either the UI or by hand-editing
   `config.json` through the settings writer.
5. The loading HUD appears within 100 ms of mode selection and never
   lingers after the result returns.
6. `text-refiner.log` always reports `Accessibility trust` on startup.

If any of these regress, the release is blocked.
