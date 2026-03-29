import time

# Safely import the OS-specific locking modules
try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

try:
    import msvcrt

    _HAS_MSVCRT = True
except ImportError:
    _HAS_MSVCRT = False


class CacheLockTimeout(Exception):
    """Raised when a file lock cannot be acquired within the timeout period."""

    pass


class CacheLock:
    """
    A cross-platform, native OS file locker.
    Acts as a Context Manager to guarantee exclusive read/write access to a file.
    """

    def __init__(self, lock_file_path: str, timeout_seconds: int = 10):
        """
        Args:
            lock_file_path (str): The absolute path to the .lock file.
            timeout_seconds (int): How long to wait in queue before giving up.
        """
        self.lock_file_path = lock_file_path
        self.timeout_seconds = timeout_seconds
        self.file_descriptor = None

    def __enter__(self):
        """Attempts to acquire the lock when entering the 'with' block."""
        start_time = time.time()

        # Open the file in append mode ("a"). This safely creates the file if it
        self.file_descriptor = open(self.lock_file_path, "a")
        fd = self.file_descriptor.fileno()

        while True:
            try:
                if _HAS_FCNTL:
                    # POSIX (Mac/Linux): Apply an exclusive, non-blocking lock
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break

                elif _HAS_MSVCRT:
                    # Windows: Lock the first byte. The type: ignore stops Mac IDEs from panicking.
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore
                    break

                else:
                    raise RuntimeError("No native file locking support available on this OS.")

            except (IOError, OSError):
                # The file is currently locked by another worker!
                if (time.time() - start_time) >= self.timeout_seconds:
                    # Clean up open file handle before crashing
                    self.file_descriptor.close()
                    raise CacheLockTimeout(
                        f"Could not acquire lock on {self.lock_file_path} within {self.timeout_seconds} seconds."
                    )

                # Sleep briefly to prevent burning 100% CPU while polling the OS
                time.sleep(0.05)

        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Releases the lock and cleans up when exiting the 'with' block."""
        if self.file_descriptor:
            fd = self.file_descriptor.fileno()
            try:
                if _HAS_FCNTL:
                    # POSIX: Unlock
                    fcntl.flock(fd, fcntl.LOCK_UN)
                elif _HAS_MSVCRT:
                    # Windows: Unlock the first byte
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # type: ignore
            finally:
                # Always ensure the file handle is closed, even if the unlock fails
                self.file_descriptor.close()
