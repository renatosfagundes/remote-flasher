"""Numpy-backed circular buffer for real-time time-series data."""
import numpy as np


class RingBuffer:
    """Fixed-capacity circular buffer backed by a numpy array.

    Optimized for the plotter use-case: append one sample at a time,
    read the last N samples as a contiguous numpy array (zero-copy when
    the data hasn't wrapped, one copy when it has).
    """

    def __init__(self, capacity: int = 50_000, dtype=np.float64):
        self._buf = np.zeros(capacity, dtype=dtype)
        self._capacity = capacity
        self._count = 0
        self._head = 0  # next write position

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def count(self) -> int:
        return min(self._count, self._capacity)

    def append(self, value: float):
        self._buf[self._head] = value
        self._head = (self._head + 1) % self._capacity
        self._count += 1

    def get_array(self) -> np.ndarray:
        """Return all stored samples as a contiguous array (oldest first)."""
        n = self.count
        if n == 0:
            return np.empty(0, dtype=self._buf.dtype)
        if self._count <= self._capacity:
            # Haven't wrapped yet — simple slice
            return self._buf[:n].copy()
        # Wrapped — concatenate tail + head
        return np.concatenate((self._buf[self._head:], self._buf[:self._head]))

    def get_last(self, n: int) -> np.ndarray:
        """Return the last *n* samples (or fewer if not enough data)."""
        available = self.count
        n = min(n, available)
        if n == 0:
            return np.empty(0, dtype=self._buf.dtype)
        # Start index = head - n (may wrap)
        start = (self._head - n) % self._capacity
        if start < self._head:
            return self._buf[start:self._head].copy()
        # Wrapped
        return np.concatenate((self._buf[start:], self._buf[:self._head]))

    def clear(self):
        self._count = 0
        self._head = 0
