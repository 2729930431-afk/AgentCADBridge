"""An OS-backed lock shared by CLI and every Agent process in the Windows session."""

import os
import time
from contextlib import contextmanager
from pathlib import Path


def state_dir() -> Path:
    path = Path(
        os.environ.get(
            "CADBRIDGE_STATE_DIR", str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CADBridge")
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def cad_lock(timeout: float = 15):
    # A global product lock intentionally serializes all CADBridge COM work.
    import msvcrt

    path = state_dir() / "execution.lock"
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("CADBridge is busy in another process; no operation was started")
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
