import sqlite3
import os
import threading
from config import CONFIG_DIR

# DB path in the user's APPDATA folder (or local dir)
DB_PATH = os.path.join(CONFIG_DIR, "sabre_lpr_history.db")

class DBManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DBManager, cls).__new__(cls)
                cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # Create reads table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_text TEXT NOT NULL,
                confidence_score REAL,
                timestamp TEXT,
                gps_coordinates TEXT,
                image_path TEXT,
                color_overview_path TEXT,
                state TEXT,
                make TEXT,
                model TEXT,
                color TEXT
            )
        ''')
        self.conn.commit()

    def insert_read(self, plate, conf, ts, gps, img_path, color_path, state, make, model, color):
        with self._lock:
            self.cursor.execute('''
                INSERT INTO reads (
                    plate_text, confidence_score, timestamp, gps_coordinates,
                    image_path, color_overview_path, state, make, model, color
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (plate, conf, ts, gps, img_path, color_path, state, make, model, color))
            self.conn.commit()
            return self.cursor.lastrowid

    def update_image_paths(self, old_path, new_path):
        """Updates paths in bulk to avoid pulling entire DB into memory."""
        with self._lock:
            self.cursor.execute('''
                UPDATE reads
                SET image_path = ?
                WHERE image_path = ?
            ''', (new_path, old_path))

            self.cursor.execute('''
                UPDATE reads
                SET color_overview_path = ?
                WHERE color_overview_path = ?
            ''', (new_path, old_path))
            self.conn.commit()

    def close(self):
        self.conn.close()
