# Architecture — Pink Robin Encoder

Windows-only desktop GUI (customtkinter) fronting a tailored FFmpeg build.

## Component map

```
src/app.py            App (CTk root): state, UI queue pump, task orchestration
src/gui_panels.py     View: layout + widgets (top bar, settings, preview, queue, status)
src/gui_callbacks.py  Controller: user events -> tasks / state changes
src/gui_tasks.py      Background work (threads): load, develop batch, mux, audio, stills
src/gui_updaters.py   Main-thread UI updates (via App.ui_update_queue)
src/encoding.py       FFmpeg command construction + multi-pass execution
src/analysis.py       ffprobe info, cropdetect, stills, color palettes
src/utils.py          Paths, settings, subprocess runner with progress parsing
src/config.py         Presets, theme, constants + validate_presets() schema
src/validators.py     Input validation / security boundary for all user input
src/a11y.py           Focus rings + status announcements (WCAG effort)
src/ui_runtime.py     Adaptive UI-queue pump, debouncing, toasts, process kill
src/ui_components.py  Dialogs (input, completion, update)
src/qc_tool.py        VMAF comparison window (libvmaf, required)
src/logger_setup.py   File+console logging, PRE_JSON_LOGS=1 for JSON lines
```

## Threading model

- Tk main thread owns ALL widgets. Background threads NEVER touch widgets;
  they `app.ui_update_queue.put(callable)` and `ui_runtime._process_ui_queue`
  drains ≤64 callbacks/frame with adaptive batching (see `ui_runtime.py`).
- FFmpeg runs via `utils.run_process` (Popen + reader threads + progress
  callback). Cancellation: `app.cancel_requested` flag + escalating
  terminate (`CTRL_BREAK_EVENT` → `terminate` → `kill`).

## Data flow (develop)

1. `develop_callback` snapshots UI into job dicts (`create_job_item_from_current_state`,
   deep-copied so later UI edits can't corrupt running jobs).
2. `_pre_flight_checks` validates metadata via `validators.py`.
3. `run_development_batch_task` expands jobs × presets, pre-estimates time,
   then `encoding.run_job` per preset (1-pass CRF or 2-pass ABR).
4. Progress callbacks carry batch-level ETA; completion shows `CompletionDialog`.

## FFmpeg contract

`tests/test_ffmpeg_usage_contract.py` scans `src/` and enforces the minimal
build defined in `scripts/build_ffmpeg_windows.sh`:
bundled = {libx264, libx265, libfdk-aac, soxr, vmaf, png, mjpeg, prores_ks,
crop/cropdetect/scale/format/setpts/nlmeans/cas/aresample/libvmaf};
banned = {vpx, mp3lame, opus, vorbis, theora, zimg, openjpeg, ass, ...}.
Add a filter/codec ⇒ update the test AND the build script together.

## Build & release

- FFmpeg: `scripts/build_ffmpeg_windows.sh` (MSYS2 MinGW64, also in CI:
  `.github/workflows/build-ffmpeg.yml` → `ffmpeg-windows` artifact).
- App: `python build.py` (Nuitka standalone → `dist/PinkRobinEncoder/`
  + `./bin` bundle → `.7z`). Entry: `.github/workflows/build-app.yml`.
- Checks: `python scripts/dev_check.py` (compile + ruff/mypy/bandit/pytest).

## Key decisions (ADRs)

- `docs/adr/0001-no-fallbacks.md` — required deps, fail fast.
- `docs/adr/0002-custom-ffmpeg.md` — minimal tailored build.
- `docs/adr/0003-nuitka-github-builds.md` — Nuitka + GitHub-built artifacts.
