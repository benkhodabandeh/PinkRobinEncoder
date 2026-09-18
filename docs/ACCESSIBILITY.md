# Accessibility Statement — Pink Robin Encoder

Target: **WCAG 2.1 AA** within the limits of the Tkinter/customtkinter stack.

## What works today

- **Full keyboard operation**: Tab/Shift+Tab reaches every control; `Ctrl+O`
  (load), `Ctrl+S` (develop), `Ctrl+Q` (QC tool), `Esc` (cancel), `F5`
  (reload still), `Del` (remove queue item), `↑/↓` (reorder) are bound
  globally in `App._setup_keyboard_shortcuts`.
- **Visible focus**: `src/a11y.py::add_focus_ring` draws a high-contrast ring
  (`#F0CB70` on `#0E1117`, contrast ≈ 8:1) on preset buttons when focused.
- **Status announcements**: preset toggles, queue operations, cancel, and
  completion post a text announcement to the status bar via
  `src/a11y.py::announce`, so state changes are perceivable without color.
- **No color-only meaning**: preset selected state uses fill + text-brightness
  change, and the status bar always carries the same information as text.

## Known limitations (honest)

- customtkinter renders custom-drawn widgets; **NVDA/JAWS narration of
  canvas-drawn controls is partial**. Native dialog text (messagebox,
  filedialog) narrates normally.
- No high-contrast OS-theme mirroring yet; the built-in dark theme meets
  4.5:1 for body text (`#F5F6F8` on `#0E1117` ≈ 15:1, `#A9B4C0` on
  `#0E1117` ≈ 7:1) but widget-level remapping is future work.
- No reduced-motion setting yet; the busy animation is the only motion and
  it stops on completion.

## Verification

- [ ] Tab through the full window with the keyboard; every action reachable.
- [ ] Toggle presets with `Space`/`Enter`; status bar announces each change.
- [ ] Run with NVDA: dialogs and entry fields narrate; log gaps in this file.
