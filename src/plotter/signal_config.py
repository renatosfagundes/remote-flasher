"""Per-signal configuration for the plotter."""
from dataclasses import dataclass, field

# Default color palette (cycles for channels beyond 16)
CHANNEL_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#ecf0f1",
    "#e84393", "#00cec9", "#fdcb6e", "#6c5ce7",
    "#ff7675", "#74b9ff", "#55efc4", "#ffeaa7",
]


@dataclass
class SignalConfig:
    index: int
    name: str = ""
    color: str = ""
    scale: float = 1.0
    offset: float = 0.0
    visible: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = f"CH{self.index}"
        if not self.color:
            self.color = CHANNEL_COLORS[self.index % len(CHANNEL_COLORS)]
