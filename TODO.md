# TODO

Known open items after the tooltip / plotter / locking work.

## Bugs

- **Dashboard tooltips don't appear.**
  `setToolTip` was set on `InfoCardWidget` / `StatusLightWidget` / `AnalogGaugeWidget`
  in `src/tabs/gauges_tab.py`, but hovering shows nothing. Hypotheses to check:
  - Child `QLabel`s fill the parent and capture hover without a tooltip of
    their own — Qt should bubble up, but some themes/stylesheet combos
    break that. Try propagating the tooltip to every child label.
  - `self.setStyleSheet("background: #0a0a18;")` on `GaugesTab` may be
    interfering with tooltip event delivery; verify by temporarily removing.
  - `AnalogGaugeWidget` paints with `QPainter` over the whole rect — confirm
    it doesn't call `setMouseTracking(False)` or override `event()` in a way
    that swallows `QEvent::ToolTip`.

- **Flash tab: a blank white horizontal strip appears below the button row.**
  Visible between the green "Upload + Reset + Flash" button and the log. Likely
  an unstyled container widget falling back to the Windows light theme. Find
  the offending widget and give it the app's dark background (`#1e1e1e` or
  the palette-based `_apply_dark_bg` helper from `widgets.py`).

## Nice to have

- Audit remaining interactive widgets without tooltips: serial panel "Send"
  button, VIO buttons (B1–B4, L1–L4, POT sliders), per-panel Clear Log,
  dashboard status column header cells.
- Dashboard source combo: dynamically refresh its list when serial panels
  are added/removed, so the user doesn't need to reopen the tab.
- Plotter legend: make individual entries clickable to toggle curve
  visibility (pyqtgraph's `LegendItem` supports this).
