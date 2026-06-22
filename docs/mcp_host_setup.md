# MCP host setup

This project exposes an MCP stdio server that lets AI hosts control the local
8bit music app.

## Run target

From the project root:

```powershell
pip install -r requirements-dev.txt
python -m mcp_server.eightbit_mcp_server
```

Packaged builds also create a console stdio launcher:

```powershell
dist\8bit-mcp-server.exe
```

When the PyQt app is running, the MCP server forwards commands to the app at
`http://127.0.0.1:8765`. If the app is not running, it falls back to an isolated
in-memory project for testing.

## Codex config example

Add a stdio MCP server entry to your Codex config and adjust the path if this
repo lives somewhere else:

```toml
[mcp_servers.eightbit]
command = "python"
args = ["-m", "mcp_server.eightbit_mcp_server"]
cwd = "F:\\Code\\8bit"
```

Packaged exe alternative:

```toml
[mcp_servers.eightbit]
command = "F:\\Code\\8bit\\dist\\8bit-mcp-server.exe"
```

Restart Codex after changing MCP config.

## Claude Desktop config example

Add this server to Claude Desktop's MCP config:

```json
{
  "mcpServers": {
    "eightbit": {
      "command": "python",
      "args": ["-m", "mcp_server.eightbit_mcp_server"],
      "cwd": "F:\\Code\\8bit"
    }
  }
}
```

Packaged exe alternative:

```json
{
  "mcpServers": {
    "eightbit": {
      "command": "F:\\Code\\8bit\\dist\\8bit-mcp-server.exe"
    }
  }
}
```

Restart Claude Desktop after changing MCP config.

## Typical AI workflow

Music generation:

1. Start the 8bit PyQt app.
2. Ask the AI host to call `eightbit_generate_music` with `style="epic"`.
3. Ask it to call `eightbit_insert_music_spec` with `dry_run=true`.
4. If the summary looks right, call `eightbit_insert_music_spec` with
   `dry_run=false` and optionally `auto_preview=true`.
5. Call `eightbit_preview_playback` or export the full project with
   `eightbit_export_audio`.

Sound-effect generation:

1. Start the 8bit PyQt app.
2. Ask the AI host to call `eightbit_insert_sfx_spec` with a dry run first.
3. If the summary looks right, call `eightbit_insert_sfx_spec` with
   `dry_run=false`.
4. Call `eightbit_preview_playback` to audition the inserted beat range, or set
   `auto_preview=true` on the insert call.
5. Call `eightbit_export_audio_range` with `sfx_only=true` to export a clean
   game sound-effect asset.

Useful context tool:

- `eightbit_get_ui_context`: reads the current playhead, playback state,
  selected track, selected tracks, and selection count from the running app.
- `eightbit_get_operation_log`: reads recent MCP/app-control operations.

Example custom SFX spec:

```json
{
  "spec": {
    "kind": "coin_ai",
    "label": "AI coin sparkle",
    "notes": [
      {"pitch": 84, "start_beat": 0.0, "duration_beats": 0.1, "velocity": 112, "waveform": "square", "duty_cycle": 0.25},
      {"pitch": 91, "start_beat": 0.1, "duration_beats": 0.09, "velocity": 118, "waveform": "square", "duty_cycle": 0.25},
      {"pitch": 96, "start_beat": 0.19, "duration_beats": 0.14, "velocity": 105, "waveform": "triangle"}
    ],
    "delay_params": {"delay_time": 0.06, "feedback": 0.18, "mix": 0.2, "enabled": true},
    "tremolo_params": {"rate": 10.0, "depth": 0.15, "enabled": true}
  },
  "start_beat": 4.0,
  "dry_run": true,
  "auto_preview": false
}
```

Example epic music generation call:

```json
{
  "style": "epic",
  "length_bars": 8,
  "bpm": 132,
  "key": "C",
  "intensity": 0.9
}
```

Example music insertion call using the generated `data` as `spec`:

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
        "name": "Drums",
        "track_type": "drum",
        "drum_events": [
          {"drum_type": "kick", "start_beat": 0.0, "duration_beats": 0.25, "velocity": 120}
        ]
      }
    ]
  },
  "start_beat": 0.0,
  "dry_run": true,
  "auto_preview": false
}
```

## Safety behavior

- Mutating SFX insert tools support `dry_run`.
- Mutating music insert tools support `dry_run`.
- Export tools require absolute file paths.
- Export tools refuse overwrites unless `overwrite=true`.
- When commands reach the running PyQt app, real file export asks the user for
  confirmation before writing.
- Mutating, playback, export, and undo commands are guarded by a local
  app-control lock so concurrent AI hosts receive a busy result instead of
  interleaving project changes.
