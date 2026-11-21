"""Run blocking AI service calls outside the Qt UI thread."""
from PyQt6.QtCore import QThread, pyqtSignal


class AIWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, *args, **kwargs):
        super().__init__()
        self.operation = operation
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.succeeded.emit(self.operation(*self.args, **self.kwargs))
        except Exception as exc:  # surfaced as an in-app message; never swallowed
            self.failed.emit(str(exc))
