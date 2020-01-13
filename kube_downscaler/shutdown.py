import contextlib
import signal
import sys


class GracefulShutdown:
    shutdown_now = False
    safe_to_exit = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.shutdown_now = True
        if self.safe_to_exit:
            sys.exit(0)

    @contextlib.contextmanager
    def safe_exit(self):
        self.safe_to_exit = True
        yield
        self.safe_to_exit = False
