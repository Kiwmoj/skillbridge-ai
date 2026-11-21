import time
import unittest

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from workers.ai_worker import AIWorker


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_slow_operation_does_not_block_ui_event_loop(self):
        loop = QEventLoop()
        result = []
        timer_observation = []

        def slow_operation():
            time.sleep(0.5)
            return {"ready": True}

        worker = AIWorker(slow_operation)
        worker.succeeded.connect(lambda value: (result.append(value), loop.quit()))
        worker.failed.connect(lambda error: (result.append(error), loop.quit()))
        QTimer.singleShot(80, lambda: timer_observation.append(worker.isRunning()))
        QTimer.singleShot(2000, loop.quit)
        worker.start()
        loop.exec()
        worker.wait()
        self.assertEqual(result, [{"ready": True}])
        self.assertEqual(timer_observation, [True])


if __name__ == "__main__":
    unittest.main()
