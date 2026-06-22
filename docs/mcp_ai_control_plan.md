# AI and MCP control plan

This plan treats MCP as a control surface for the running 8bit music app. The
first milestone is not MCP itself. The app must first expose reliable internal
music and SFX operations that can later be called by an MCP server.

## Goal

Allow an AI client such as Codex, Claude, or another MCP host to say:

> Generate a coin pickup sound, insert it into the current 8bit project, play it,
> and export it as a sound effect.

The intended flow is:

1. The AI client calls MCP tools.
2. The MCP server validates the request and sends local commands to the running
   8bit app.
3. The app applies the operation through its normal project model, refreshes the
   UI, and keeps the operation undoable.

## Architecture

```text
AI host
  -> MCP client
    -> 8bit MCP server
      -> local app control bridge
        -> PyQt app command layer
          -> Project / Track / Note / AudioEngine
```

The MCP server should not automate mouse clicks or edit project files behind the
app. It should call app commands that are also used by the UI.

## Phase 1: in-app SFX capability

Status: implemented as the first local foundation.

Success criteria:

- The app can generate at least one 8bit SFX preset without AI.
- The generated SFX is represented as notes and note-level sound parameters.
- The UI can insert the SFX into the current project.
- The inserted SFX uses an effect-role note track.
- The operation participates in undo/redo.
- Unit tests cover the SFX spec and insertion helpers.
- Track-level effect params can round-trip through project serialization.

Initial presets:

- `coin`: short upward arpeggio for item pickup.
- `jump`: fast upward chirp.
- `hit`: short noisy impact.
- `power_up`: rising multi-note flourish.
- `laser`: descending zap with highpass/vibrato track color.
- `explosion`: noisy impact with lowpass/tremolo track color.
- `select`: short menu confirmation.
- `error`: two-note warning beep with tremolo.
- `door`: small mechanical opening phrase.
- `heal`: soft upward recovery flourish with delay.

Current UI:

- The SFX menu exposes all presets.
- The SFX editor dialog can choose a preset, insertion beat, and auto-preview.
- Presets can actively configure SFX track filter, delay, tremolo, and vibrato
  params as part of the same undoable insert command.

## Phase 2: local app command bridge

Status: implemented for the first AI-control slice. The in-process command
boundary exists, and the running PyQt app now starts a localhost HTTP control
service that executes commands on the Qt main thread.

Success criteria:

- A local bridge can query current project state.
- A local bridge can apply a structured SFX insert command.
- Commands are accepted only from localhost.
- Mutating commands return a structured diff summary.
- Playback preview can be started and stopped through the bridge.
- Audio export supports dry-run and refuses overwrites unless requested.
- Beat-range audio export can render a short SFX or project slice.
- Beat-range audio export can render only effect-role SFX tracks.
- Running-app file exports require an app-side confirmation prompt.
- External clients can query playhead, playback state, selected track, selected
  tracks, and selection count.
- Insert tools can request `auto_preview=true` after a successful mutation.
- Multi-client writes, playback, export, and undo operations are guarded by a
  local app-control lock and return a busy result when another control command
  is already running.
- Recent app-control operations can be queried for debugging and AI audit trails.

Candidate commands:

- `get_project_state`
- `generate_sfx_spec`
- `insert_sfx`
- `insert_sfx_spec`
- `preview_playback`
- `get_ui_context`
- `stop_playback`
- `export_audio`
- `export_audio_range`
- `undo`
- `get_operation_log`

Deferred bridge commands:

- `preview_range` with automatic stop after range playback.

Current localhost endpoints:

- `GET /project`
- `GET /sfx-presets`
- `POST /sfx-spec`
- `POST /insert-sfx`
- `POST /insert-sfx-spec`
- `GET /ui-context`
- `GET /operation-log`
- `POST /preview`
- `POST /stop-playback`
- `POST /export-audio`
- `POST /export-audio-range`
- `POST /undo`

The default host is `127.0.0.1`, port `8765`.

## Phase 3: MCP server

Status: implemented for the first end-to-end control loop. The MCP server
prefers the running PyQt app through the localhost service and falls back to an
isolated in-memory project when the app is not running.

Success criteria:

- The MCP server exposes read resources for project state and SFX presets.
- The MCP server exposes tools that map to the app command bridge.
- Mutating tools support dry-run mode.
- Destructive or file-writing tools require explicit approval in the host or app.
- AI-generated custom SFX payloads are validated before insertion.

Initial tools:

- `eightbit_get_project`
- `eightbit_get_ui_context`
- `eightbit_get_operation_log`
- `eightbit_list_sfx_presets`
- `eightbit_generate_sfx`
- `eightbit_insert_sfx`
- `eightbit_insert_sfx_spec`
- `eightbit_preview_playback`
- `eightbit_stop_playback`
- `eightbit_export_audio`
- `eightbit_export_audio_range`
- `eightbit_undo`

Current local run target:

```powershell
pip install -r requirements-dev.txt
python -m mcp_server.eightbit_mcp_server
```

Packaged builds also create:

```powershell
dist\8bit-mcp-server.exe
```

Verified stdio flow:

- Start the server with the MCP Python SDK stdio client.
- Call `list_tools`.
- Call `eightbit_insert_sfx` with `dry_run=true`.
- Call `eightbit_insert_sfx` with `dry_run=false`.
- Read `eightbit://project`.

Current app-control flow:

- If the PyQt app is running, MCP sends commands to `http://127.0.0.1:8765`.
- If the app is offline, MCP falls back to an isolated in-memory project for
  integration testing.
- `eightbit_export_audio` requires an absolute path and will not overwrite
  existing files unless `overwrite=true`.
- `eightbit_export_audio_range` uses beat positions so AI clients can export
  only the generated SFX window, for example beat `4.0` to `4.5`.
- Set `sfx_only=true` on `eightbit_export_audio_range` to mute non-effect
  tracks while exporting a game sound-effect asset.
- Set `auto_preview=true` on insert tools to audition the newly inserted SFX
  range immediately in the running app.
- Call `eightbit_get_operation_log` to inspect recent AI/app-control actions.

Host setup examples are in [mcp_host_setup.md](mcp_host_setup.md).

## Phase 4: AI-assisted SFX and arrangement

Success criteria:

- AI can map natural language to a structured `SfxSpec`.
- AI output is validated before any project mutation.
- The user can accept, reject, preview, or undo the generated result.

Example structured SFX payload:

```json
{
  "kind": "coin",
  "label": "Coin pickup",
  "notes": [
    {"pitch": 84, "start_beat": 0.0, "duration_beats": 0.12},
    {"pitch": 91, "start_beat": 0.12, "duration_beats": 0.10},
    {"pitch": 96, "start_beat": 0.22, "duration_beats": 0.16}
  ]
}
```

Current custom insertion tool payload:

```json
{
  "spec": {
    "kind": "custom_coin",
    "label": "Custom coin",
    "notes": [
      {
        "pitch": 84,
        "start_beat": 0.0,
        "duration_beats": 0.1,
        "velocity": 112,
        "waveform": "square",
        "duty_cycle": 0.25,
        "adsr": {"attack": 0.002, "decay": 0.04, "sustain": 0.25, "release": 0.03}
      }
    ]
  },
  "start_beat": 4.0,
  "dry_run": true
}
```

## Safety rules

- Read-only tools are safe by default.
- Mutating tools must return what changed.
- Export tools must not overwrite files without explicit confirmation.
- MCP should never receive API keys stored in the app settings.
- The app remains the source of truth for project state.

## Deferred work

- Add a richer graphical SFX editor for note-level pitch envelopes, ADSR, and
  per-note waveform editing.
- Add natural-language-to-SfxSpec generation inside the app instead of requiring
  the AI host to provide the structured payload.
- Add app transport selection beyond the default localhost bridge, such as
  Streamable HTTP or named-pipe IPC for app-hosted workflows.
- Extend app-side permission prompts beyond export to future destructive or
  bulk project-editing tools.
- Add a packaged config helper so users do not have to edit MCP JSON by hand.
