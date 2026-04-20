"""Real-time scrolling plot widget using pyqtgraph."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

from plotter.plotter_backend import PlotterBackend


# Dark theme matching the app's look
pg.setConfigOptions(
    background="#16162a",
    foreground="#cccccc",
    antialias=True,
)


class ClickableLegendItem(pg.LegendItem):
    """LegendItem whose entries emit a signal when clicked."""
    # (curve, label_text) — caught by PlotterWidget to toggle visibility.
    sampleClicked = Signal(object, str)

    def mousePressEvent(self, ev):
        # Determine which legend entry the click hit by walking the layout.
        for sample, label in self.items:
            # sample.sceneBoundingRect() includes the color swatch;
            # label covers the text. Either is a valid hit target.
            rect = sample.sceneBoundingRect().united(label.sceneBoundingRect())
            if rect.contains(ev.scenePos()):
                # `sample.item` is the curve (PlotDataItem) associated with
                # this legend entry — pyqtgraph stores it there.
                curve = getattr(sample, "item", None)
                self.sampleClicked.emit(curve, label.text)
                ev.accept()
                return
        super().mousePressEvent(ev)


class PlotterWidget(QWidget):
    """pyqtgraph-based real-time scrolling plot.

    Refreshes at 30 fps. Each visible signal gets its own PlotDataItem
    curve, updated from the backend's ring buffers with scale+offset applied.
    """
    # Emitted when the user clicks a legend entry — so the SignalListWidget
    # can sync its visibility checkbox for that signal.
    signalVisibilityToggled = Signal(int, bool)  # (index, visible)
    # Emitted whenever the measurement-cursor pair moves. Consumers use this
    # to refresh a stats readout on demand (in addition to the 5 Hz poll).
    cursorPositionsChanged = Signal(float, float)  # (t1, t2)

    def __init__(self, backend: PlotterBackend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._window_seconds = 10.0
        self._curves: dict[int, pg.PlotDataItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.setLabel("left", "Value")
        # Enable mouse zoom/pan
        self._plot_widget.setMouseEnabled(x=True, y=True)
        layout.addWidget(self._plot_widget)

        plot_item = self._plot_widget.getPlotItem()
        # Ticks + values on all four sides.
        for side in ("top", "right"):
            plot_item.showAxis(side)
            plot_item.getAxis(side).setStyle(showValues=True)

        # Legend — auto-populated from each curve's `name`. Semi-transparent
        # background so it doesn't hide data. Click an entry to hide/show
        # the curve (and keep the side-panel checkbox in sync).
        self._legend = ClickableLegendItem(
            offset=(-10, 10),
            brush=pg.mkBrush("#00000099"),
            pen=pg.mkPen("#555"),
            labelTextColor="#dddddd",
        )
        self._legend.setParentItem(plot_item.vb)
        self._legend.sampleClicked.connect(self._on_legend_clicked)

        # Crosshair for hover
        self._vline = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen("#ffffff", width=0.5, style=pg.QtCore.Qt.DashLine),
        )
        self._plot_widget.addItem(self._vline, ignoreBounds=True)
        self._vline.setVisible(False)

        # Dots marking the (hover_x, y_i) intersection for each visible curve.
        self._hover_dots = pg.ScatterPlotItem(size=9, pen=pg.mkPen("#ffffff", width=1.5))
        self._hover_dots.setVisible(False)
        self._plot_widget.addItem(self._hover_dots, ignoreBounds=True)

        # Hover label — dark background box so numbers stay legible over curves.
        self._hover_label = pg.TextItem(
            anchor=(0, 1),
            color="#ffffff",
            fill=pg.mkBrush("#000000cc"),
            border=pg.mkPen("#888"),
        )
        self._hover_label.setVisible(False)
        self._plot_widget.addItem(self._hover_label, ignoreBounds=True)

        # Measurement cursor pair — LinearRegionItem gives us two draggable
        # lines with a shaded span in a single item. swapMode="block" keeps
        # t1 ≤ t2 so the stats code never has to order the bounds.
        self._cursor_region = pg.LinearRegionItem(
            values=[0, 1],
            brush=pg.mkBrush("#4488ff1e"),
            pen=pg.mkPen("#4488ff", width=1),
            hoverBrush=pg.mkBrush("#4488ff32"),
            movable=True,
            swapMode="block",
        )
        self._cursor_region.setVisible(False)
        self._cursor_region.setZValue(10)
        self._plot_widget.addItem(self._cursor_region, ignoreBounds=True)
        self._cursor_region.sigRegionChanged.connect(self._on_cursor_region_changed)
        self._cursors_enabled = False
        # Offsets from latest_t — the region is stored/updated as
        # "N seconds behind the live edge" so it slides with the
        # scrolling window instead of drifting off the left side.
        # None when cursors are off.
        self._cursor_offsets: tuple[float, float] | None = None

        # Last scene position the mouse reported, kept so the hover
        # tooltip can be re-evaluated against the *current* view during
        # scroll ticks even when the pointer is stationary.
        self._last_mouse_scene_pos = None

        self._plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
        # Hover throttling — bare mouse-move events fire at 60-120 Hz and
        # each update walks every channel + repositions an overlay, which
        # stalls the plot on hover. Cap at ~30 Hz via a monotonic timestamp.
        self._last_hover_ns = 0
        self._HOVER_MIN_GAP_NS = 33_000_000  # 33 ms → ~30 Hz
        # Last-snapped sample index — skip the full redraw if the nearest
        # sample hasn't changed since the previous hover tick.
        self._last_hover_idx = -1

        # Refresh timer — 30 fps
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        self._backend.channelCountChanged.connect(self._rebuild_curves)

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    @window_seconds.setter
    def window_seconds(self, v: float):
        self._window_seconds = max(1.0, v)

    def _rebuild_curves(self, count: int):
        """Add/remove curves to match the current channel count."""
        # Add new curves
        for i in range(count):
            if i not in self._curves:
                cfg = self._backend.configs[i] if i < len(self._backend.configs) else None
                color = cfg.color if cfg else "#ffffff"
                curve = self._plot_widget.plot(
                    pen=pg.mkPen(color, width=2),
                    name=cfg.name if cfg else f"CH{i}",
                )
                self._curves[i] = curve
                # Populate the custom legend + apply visibility from cfg.
                # pg.PlotItem.plot() doesn't auto-add to our ClickableLegendItem
                # (it's set as a ViewBox child, not the plot's default legend).
                self.update_curve_style(i)

        # Remove excess curves
        to_remove = [i for i in self._curves if i >= count]
        for i in to_remove:
            curve = self._curves.pop(i)
            try:
                self._legend.removeItem(curve)
            except Exception:
                pass
            self._plot_widget.removeItem(curve)

    def _on_legend_clicked(self, curve, label_text):
        """Legend entry clicked — toggle that curve's visibility."""
        # Find which config index this curve belongs to.
        for idx, c in self._curves.items():
            if c is curve:
                configs = self._backend.configs
                if idx < len(configs):
                    configs[idx].visible = not configs[idx].visible
                    self._backend.update_config(idx, configs[idx])
                    self.update_curve_style(idx)
                    self.signalVisibilityToggled.emit(idx, configs[idx].visible)
                return

    def update_curve_style(self, index: int):
        """Update a curve's pen color, visibility, and legend entry from config."""
        if index not in self._curves:
            return
        configs = self._backend.configs
        if index >= len(configs):
            return
        cfg = configs[index]
        curve = self._curves[index]
        curve.setPen(pg.mkPen(cfg.color, width=2))
        curve.setVisible(cfg.visible)
        # Rebuild this curve's legend entry — pyqtgraph's LegendItem doesn't
        # track name/visibility changes on its own.
        try:
            self._legend.removeItem(curve)
        except Exception:
            pass
        if cfg.visible:
            self._legend.addItem(curve, cfg.name)
        curve.opts["name"] = cfg.name

    def _refresh(self):
        """Called at 30 fps — update curve data and scroll X axis."""
        if self._backend.paused:
            return
        if not self._backend.check_dirty():
            return

        t_buf = self._backend.time_buffer()
        t_count = t_buf.count
        if t_count == 0:
            return

        # Determine how many samples to show based on window
        t_all = t_buf.get_array()
        latest_t = t_all[-1] if len(t_all) > 0 else 0

        # Find samples within the window
        t_min = latest_t - self._window_seconds
        mask = t_all >= t_min
        t_window = t_all[mask]

        configs = self._backend.configs
        for i, curve in self._curves.items():
            if i >= len(configs):
                continue
            cfg = configs[i]
            if not cfg.visible:
                curve.setVisible(False)
                continue
            curve.setVisible(True)

            ch_buf = self._backend.channel_buffer(i)
            ch_all = ch_buf.get_array()

            # Align lengths (time and channel buffers should match)
            n = min(len(t_all), len(ch_all))
            if n == 0:
                continue
            ch_slice = ch_all[-n:][mask[-n:]] if n <= len(mask) else ch_all
            t_slice = t_window

            # Align after masking
            m = min(len(t_slice), len(ch_slice))
            if m == 0:
                continue

            y = ch_slice[:m] * cfg.scale + cfg.offset
            curve.setData(t_slice[:m], y)

        # Scroll X axis
        self._plot_widget.setXRange(t_min, latest_t, padding=0)

        # Slide the measurement-cursor pair forward so it stays pinned
        # to its offsets from the live edge instead of falling off-screen.
        if self._cursors_enabled and self._cursor_offsets is not None:
            o1, o2 = self._cursor_offsets
            # Block signals: setRegion would otherwise fire sigRegionChanged
            # → _on_cursor_region_changed → recompute offsets (no-op but
            # wasteful, and a source of subtle drift if latest_t races).
            self._cursor_region.blockSignals(True)
            try:
                self._cursor_region.setRegion(
                    (latest_t - o1, latest_t - o2)
                )
            finally:
                self._cursor_region.blockSignals(False)

        # Re-run the hover update against the *current* view so the
        # tooltip tracks the mouse's actual location even when only the
        # plot is moving (stationary pointer, scrolling window).
        if self._last_mouse_scene_pos is not None:
            self._update_hover(self._last_mouse_scene_pos)

    def _on_mouse_moved(self, pos):
        """Mouse event → throttle → hover update."""
        if not self._plot_widget.sceneBoundingRect().contains(pos):
            self._vline.setVisible(False)
            self._hover_label.setVisible(False)
            self._hover_dots.setVisible(False)
            self._last_hover_idx = -1
            self._last_mouse_scene_pos = None
            return

        # Throttle — mouse-move fires at 60-120 Hz; the scroll-driven
        # hover refresh in _refresh is already rate-limited to 30 fps.
        import time as _time
        now_ns = _time.monotonic_ns()
        if now_ns - self._last_hover_ns < self._HOVER_MIN_GAP_NS:
            self._last_mouse_scene_pos = pos  # remember even when throttled
            return
        self._last_hover_ns = now_ns
        self._last_mouse_scene_pos = pos
        self._update_hover(pos)

    def _update_hover(self, pos):
        """Draw crosshair + per-curve dot + value tooltip for the given
        scene position. Shared by mouse-move and refresh-driven paths."""
        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        x = mouse_point.x()
        self._vline.setPos(x)
        self._vline.setVisible(True)

        configs = self._backend.configs
        t_all = self._backend.time_buffer().get_array()
        if len(t_all) == 0:
            self._hover_label.setVisible(False)
            self._hover_dots.setVisible(False)
            self._last_hover_idx = -1
            return

        # Nearest-sample index for the hover x.
        idx = min(np.searchsorted(t_all, x), len(t_all) - 1)
        # Skip the full redraw if we're still on the same sample — only
        # the label y needs to track vertical mouse motion for readability.
        if idx == self._last_hover_idx:
            self._hover_label.setPos(float(t_all[idx]), mouse_point.y())
            return
        self._last_hover_idx = idx
        x_snap = float(t_all[idx])

        dot_spots = []
        lines = [f"t = {x_snap:.2f}s"]
        for i in range(self._backend.channel_count):
            if i >= len(configs) or not configs[i].visible:
                continue
            ch = self._backend.channel_buffer(i).get_array()
            if idx >= len(ch):
                continue
            scaled = float(ch[idx]) * configs[i].scale + configs[i].offset
            lines.append(f"{configs[i].name}: {scaled:.3f}")
            dot_spots.append({
                "pos": (x_snap, scaled),
                "brush": pg.mkBrush(configs[i].color),
            })

        self._hover_dots.setData(dot_spots)
        self._hover_dots.setVisible(bool(dot_spots))
        self._hover_label.setText("\n".join(lines))
        # Snap the label's X to the sample's X (not raw mouse X) so the
        # tooltip and dot stay aligned instead of the label drifting while
        # the dot snaps — that visual mismatch was the "jitter" you saw.
        self._hover_label.setPos(x_snap, mouse_point.y())
        self._hover_label.setVisible(True)

    # ── Measurement cursors ───────────────────────────────────────
    def _on_cursor_region_changed(self):
        """User dragged a cursor — capture the new offsets from the live
        edge so the region continues to ride the scrolling window from
        its *new* position (rather than snapping back to the old offsets)."""
        t1, t2 = self._cursor_region.getRegion()
        t_all = self._backend.time_buffer().get_array()
        if self._cursors_enabled and len(t_all) > 0:
            latest_t = float(t_all[-1])
            self._cursor_offsets = (latest_t - float(t1), latest_t - float(t2))
        self.cursorPositionsChanged.emit(float(t1), float(t2))

    def set_cursors_enabled(self, on: bool):
        """Toggle the measurement cursor pair. On enable, seed the region
        at the 25% / 75% marks of the visible window so it's immediately
        useful without the user having to drag both ends into view."""
        self._cursors_enabled = bool(on)
        if on:
            t_all = self._backend.time_buffer().get_array()
            if len(t_all) > 0:
                latest_t = float(t_all[-1])
                t_lo = max(0.0, latest_t - self._window_seconds)
                span = latest_t - t_lo
                t1 = t_lo + span * 0.25
                t2 = t_lo + span * 0.75
                # Block signals here so the seed placement doesn't
                # round-trip through _on_cursor_region_changed before
                # we've decided the initial offsets.
                self._cursor_region.blockSignals(True)
                try:
                    self._cursor_region.setRegion((t1, t2))
                finally:
                    self._cursor_region.blockSignals(False)
                self._cursor_offsets = (latest_t - t1, latest_t - t2)
            else:
                self._cursor_offsets = None
        else:
            self._cursor_offsets = None
        self._cursor_region.setVisible(self._cursors_enabled)

    def cursors_enabled(self) -> bool:
        return self._cursors_enabled

    def cursor_positions(self) -> tuple[float, float]:
        """Return (t1, t2) of the cursor pair. (0,0) if cursors are off."""
        if not self._cursors_enabled:
            return (0.0, 0.0)
        t1, t2 = self._cursor_region.getRegion()
        return (float(t1), float(t2))

    # ── View controls ─────────────────────────────────────────────
    def auto_y(self):
        """Fit Y range to data visible in the current X window.

        One-shot: sets an explicit YRange (which disables pyqtgraph's
        built-in auto-range) so subsequent refreshes don't keep resizing
        as new samples arrive — the user gets a stable zoom until they
        either interact or click Auto-Y again.
        """
        t_all = self._backend.time_buffer().get_array()
        if len(t_all) == 0:
            return
        latest_t = float(t_all[-1])
        t_min = latest_t - self._window_seconds
        mask = t_all >= t_min
        configs = self._backend.configs
        lo, hi = None, None
        for i in self._curves:
            if i >= len(configs) or not configs[i].visible:
                continue
            ch = self._backend.channel_buffer(i).get_array()
            n = min(len(t_all), len(ch))
            if n == 0:
                continue
            ys = ch[-n:][mask[-n:]]
            if len(ys) == 0:
                continue
            cfg = configs[i]
            ys = ys * cfg.scale + cfg.offset
            y_lo, y_hi = float(np.min(ys)), float(np.max(ys))
            lo = y_lo if lo is None else min(lo, y_lo)
            hi = y_hi if hi is None else max(hi, y_hi)
        if lo is None or hi is None:
            return
        pad = max((hi - lo) * 0.05, 1e-3)
        self._plot_widget.setYRange(lo - pad, hi + pad, padding=0)

    def reset_view(self):
        """Restore default scrolling X and fit Y to visible data."""
        # X scrolling resumes automatically on the next _refresh tick
        # (setXRange is called there); just handle Y.
        self.auto_y()

    # ── Statistics helpers ────────────────────────────────────────
    def compute_stats(self, t_lo: float | None = None,
                      t_hi: float | None = None) -> dict:
        """Per-visible-channel stats over [t_lo, t_hi] (or the current
        visible window if either bound is None).

        Returns {channel_index: {name, color, min, max, mean, std,
        delta, n}}, where `delta` is (last - first) sample in the span —
        useful for integrated quantities like distance or total charge.
        """
        t_all = self._backend.time_buffer().get_array()
        if len(t_all) == 0:
            return {}
        if t_lo is None or t_hi is None:
            latest_t = float(t_all[-1])
            t_hi = latest_t
            t_lo = latest_t - self._window_seconds
        if t_hi <= t_lo:
            return {}
        mask = (t_all >= t_lo) & (t_all <= t_hi)
        if not np.any(mask):
            return {}
        configs = self._backend.configs
        out: dict = {}
        for i in self._curves:
            if i >= len(configs) or not configs[i].visible:
                continue
            ch = self._backend.channel_buffer(i).get_array()
            n = min(len(t_all), len(ch))
            if n == 0:
                continue
            ys = ch[-n:][mask[-n:]]
            if len(ys) == 0:
                continue
            cfg = configs[i]
            ys = ys * cfg.scale + cfg.offset
            out[i] = {
                "name": cfg.name,
                "color": cfg.color,
                "min": float(np.min(ys)),
                "max": float(np.max(ys)),
                "mean": float(np.mean(ys)),
                "std": float(np.std(ys)),
                "delta": float(ys[-1] - ys[0]),
                "n": int(len(ys)),
            }
        return out

    def compute_sample_rate(self) -> float:
        """Effective sample rate (samples/sec) over the last 2 s of the
        time buffer. Returns 0 when there's not enough data."""
        t_all = self._backend.time_buffer().get_array()
        if len(t_all) < 2:
            return 0.0
        t_end = float(t_all[-1])
        mask = t_all >= t_end - 2.0
        t_slice = t_all[mask]
        if len(t_slice) < 2:
            return 0.0
        duration = float(t_slice[-1] - t_slice[0])
        if duration <= 0:
            return 0.0
        return (len(t_slice) - 1) / duration

    def clear_plot(self):
        """Remove all curves and reset."""
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
        self._curves.clear()
