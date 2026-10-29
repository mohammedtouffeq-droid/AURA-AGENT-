import sqlite3
import threading
import queue
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SQLiteConnectionPool")

class SQLiteConnectionPool:
    def __init__(self, db_path, max_connections=5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = queue.Queue(maxsize=max_connections)
        
        # Write Lock: Ensures only one thread writes at a time to prevent "database is locked" errors
        self._write_lock = threading.Lock()
        
        # Initialize the pool
        for _ in range(max_connections):
            self._pool.put(self._create_connection())

    def _create_connection(self):
        # Using check_same_thread=False allows connections to be shared across threads 
        # (though we manage them via a pool)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # Enable WAL mode for read concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    @contextmanager
    def get_connection(self, write=False):
        """Context manager to get a connection from the pool."""
        conn = self._pool.get()
        try:
            if write:
                with self._write_lock:
                    yield conn
            else:
                yield conn
        finally:
            self._pool.put(conn)

    def close_all(self):
        while not self._pool.empty():
            conn = self._pool.get()
            conn.close()

# --- Example Usage ---
if __name__ == "__main__":
    import time
    from concurrent.futures import ThreadPoolExecutor

    DB_FILE = "test_app.db"
    pool = SQLiteConnectionPool(DB_FILE)

    def reader_task(id):
        with pool.get_connection(write=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            print(f"Reader {id} finished")

    def writer_task(id):
        with pool.get_connection(write=True) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (?)", (id,))
            conn.commit()
            print(f"Writer {id} finished")

    # Simulate concurrent access
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(5):
            executor.submit(reader_task, i)
            executor.submit(writer_task, i)

    pool.close_all()
