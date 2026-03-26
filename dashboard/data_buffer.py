"""
data_buffer.py
Ring buffer thread-safe per i dati OBD2 in tempo reale.
"""

import threading
from collections import deque
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class DataBuffer:
    """
    Buffer circolare thread-safe che mantiene gli ultimi BUFFER_SIZE record.
    Ogni record è un dict con: timestamp, rpm, speed, throttle,
    engine_load, coolant_temp, gear, braking.
    """

    def __init__(self):
        self._buf = deque(maxlen=config.BUFFER_SIZE)
        self._lock = threading.Lock()

    def add(self, record: dict):
        with self._lock:
            self._buf.append(record)

    def get_all(self) -> list:
        with self._lock:
            return list(self._buf)

    def latest(self) -> dict | None:
        with self._lock:
            return self._buf[-1] if self._buf else None

    def __len__(self):
        with self._lock:
            return len(self._buf)
