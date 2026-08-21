# modulos para trabajar mutiproceso
import time
import csv
import queue
import threading
from collections import deque

from PyQt6.QtCore import QThread, QTimer, Qt

class DiskWriterThread(QThread):
    def __init__(self, filename=None, block_size=500, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.block_size = block_size
        self.queue = queue.Queue()
        self._running = True

    def run(self):
        buffer = []
        while self._running or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.05)
                if isinstance(item, list) and len(item) > 0 and isinstance(item[0], list):
                    buffer.extend(item)
                else:
                    buffer.append(item)
                self.queue.task_done()
                if len(buffer) >= self.block_size:
                    self._flush_buffer(buffer)
                    buffer = []
            except queue.Empty:
                if buffer:
                    self._flush_buffer(buffer)
                    buffer = []
        if buffer:
            self._flush_buffer(buffer)
            buffer = []

    def _flush_buffer(self, buffer):
        if not buffer:
            return
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(buffer)
        except PermissionError:
            pass

    def stop(self):
        self._running = False
        self.wait()
