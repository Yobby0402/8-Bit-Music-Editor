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
- The right-side panel is now the unified entry for Properties, Score, Style,
  Playback, BPM, and SFX pages.
- The right-side panel uses a compact navigation rail and scroll-wrapped pages
  so SFX and settings controls remain usable in the dock width.
- The SFX editor lives in the right-side stacked panel and can choose a preset,
  insertion beat, and auto-preview.
- The SFX editor dialog can edit note-level pitch, start beat, duration,
  velocity, waveform, duty cycle, and ADSR values before insertion.
- The sequence area toolbar uses grouped compact track actions for add, delete,
  oscilloscope selection, and bulk track selection.
- The SFX editor dialog can ask the configured local OpenAI-compatible model to
  generate a structured SFX spec from a natural language prompt, then lets the
  user revise the generated notes before inserting them.
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
- `generate_music_spec`
- `insert_sfx`
- `insert_sfx_spec`
- `insert_music_spec`
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
- `POST /music-spec`
- `POST /insert-sfx`
- `POST /insert-sfx-spec`
- `POST /insert-music-spec`
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
- `eightbit_generate_music`
- `eightbit_insert_sfx`
- `eightbit_insert_sfx_spec`
- `eightbit_insert_music_spec`
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
- Set `auto_preview=true` on insert tools to audition the newly inserted
  range immediately in the running app.
- Call `eightbit_get_operation_log` to inspect recent AI/app-control actions.

Host setup examples are in [mcp_host_setup.md](mcp_host_setup.md).

## Phase 4: AI-assisted SFX and arrangement

Status: implemented for the first in-app SFX flow and first multi-track music
spec flow.

Success criteria:

- AI can map natural language to a structured `SfxSpec`.
- AI can generate or provide a structured `MusicSpec` with melody, bass,
  harmony, drums, BPM, structure, and style parameters.
- AI output is validated before any project mutation.
- The user can revise, accept, reject, preview, or undo the generated result.

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

Current generated music workflow:

1. Call `eightbit_generate_music` with `style="epic"`, `length_bars`, `bpm`,
   `key`, and `intensity`.
2. Inspect the returned multi-track spec.
3. Call `eightbit_insert_music_spec` with `dry_run=true`.
4. Call `eightbit_insert_music_spec` with `dry_run=false` and optionally
   `auto_preview=true`.

Example structured music payload:

```json
{
  "spec": {
    "kind": "epic_music",
    "label": "Epic 8bit Theme",
    "bpm": 132,
    "time_signature": [4, 4],
    "structure": [
      {"name": "intro", "start_beat": 0.0, "duration_beats": 8.0},
      {"name": "theme", "start_beat": 8.0, "duration_beats": 24.0}
    ],
    "style_params": {"style": "epic", "key": "C", "intensity": 0.85},
    "tracks": [
      {
        "name": "Lead",
        "track_type": "note",
        "role": "melody",
        "notes": [
          {"pitch": 72, "start_beat": 0.0, "duration_beats": 1.0, "velocity": 118, "waveform": "square"}
        ]
      },
      {
        "name": "Bass",
        "track_type": "note",
        "role": "bass",
        "notes": [
          {"pitch": 36, "start_beat": 0.0, "duration_beats": 1.0, "velocity": 110, "waveform": "triangle"}
        ]
      },
      {
        "name": "Harmony",
        "track_type": "note",
        "role": "harmony",
        "notes": [
          {"pitch": 60, "start_beat": 0.0, "duration_beats": 4.0, "velocity": 86, "waveform": "sawtooth"}
        ]
      },
      {
        "name": "Drums",
        "track_type": "drum",
        "drum_events": [
          {"drum_type": "kick", "start_beat": 0.0, "duration_beats": 0.25, "velocity": 120},
          {"drum_type": "snare", "start_beat": 1.0, "duration_beats": 0.25, "velocity": 112}
        ]
      }
    ]
  },
  "start_beat": 0.0,
  "dry_run": true,
  "auto_preview": false
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

- Add pitch-envelope drawing and richer per-note modulation editing.
- Add direct app-side controls for track filter, delay, tremolo, and vibrato
  params in the SFX editor.
- Add app transport selection beyond the default localhost bridge, such as
  Streamable HTTP or named-pipe IPC for app-hosted workflows.
- Extend app-side permission prompts beyond export to future destructive or
  bulk project-editing tools.
- Add a packaged config helper so users do not have to edit MCP JSON by hand.
