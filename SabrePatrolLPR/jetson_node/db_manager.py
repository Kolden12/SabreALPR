import psycopg2
from psycopg2 import pool
import os
import logging
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "sabre_alpr")
DB_USER = os.getenv("DB_USER", "sabre_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sabre_strong_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

class DBManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            cls._instance._init_pool()
            cls._instance._init_db()
        return cls._instance

    def _init_pool(self):
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            logging.info("PostgreSQL connection pool created successfully")
        except Exception as e:
            logging.error(f"Error creating PostgreSQL connection pool: {e}")

    def _init_db(self):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                # plate_events table
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS plate_events (
                        event_id SERIAL PRIMARY KEY,
                        camera_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        high_res_path TEXT NOT NULL,
                        thumbnail_path TEXT NOT NULL,
                        plate_text TEXT,
                        confidence REAL,
                        is_processed BOOLEAN DEFAULT FALSE,
                        is_hit BOOLEAN DEFAULT FALSE
                    )
                ''')
                # hot_list table
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS hot_list (
                        plate_text TEXT PRIMARY KEY,
                        description TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                logging.info("Database tables initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            self.connection_pool.putconn(conn)

    def insert_raw_event(self, camera_id, high_res_path, thumbnail_path):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO plate_events (camera_id, high_res_path, thumbnail_path)
                    VALUES (%s, %s, %s) RETURNING event_id
                ''', (camera_id, high_res_path, thumbnail_path))
                event_id = cur.fetchone()[0]
                conn.commit()
                return event_id
        except Exception as e:
            logging.error(f"Error inserting raw event: {e}")
            conn.rollback()
            return None
        finally:
            self.connection_pool.putconn(conn)

    def update_processed_event(self, event_id, plate_text, confidence, is_hit, high_res_path=None):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                if high_res_path:
                    cur.execute('''
                        UPDATE plate_events
                        SET plate_text = %s, confidence = %s, is_hit = %s, is_processed = TRUE, high_res_path = %s
                        WHERE event_id = %s
                    ''', (plate_text, confidence, is_hit, high_res_path, event_id))
                else:
                    cur.execute('''
                        UPDATE plate_events
                        SET plate_text = %s, confidence = %s, is_hit = %s, is_processed = TRUE
                        WHERE event_id = %s
                    ''', (plate_text, confidence, is_hit, event_id))
                conn.commit()
        except Exception as e:
            logging.error(f"Error updating processed event: {e}")
            conn.rollback()
        finally:
            self.connection_pool.putconn(conn)

    def get_unprocessed_events(self):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT event_id, camera_id, high_res_path, thumbnail_path
                    FROM plate_events
                    WHERE is_processed = FALSE
                    ORDER BY timestamp ASC
                ''')
                return cur.fetchall()
        except Exception as e:
            logging.error(f"Error getting unprocessed events: {e}")
            return []
        finally:
            self.connection_pool.putconn(conn)

    def check_hot_list(self, plate_text):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM hot_list WHERE plate_text = %s', (plate_text,))
                return cur.fetchone() is not None
        except Exception as e:
            logging.error(f"Error checking hot list: {e}")
            return False
        finally:
            self.connection_pool.putconn(conn)

    def get_history(self, limit=50, offset=0):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT event_id, camera_id, timestamp, high_res_path, thumbnail_path, plate_text, confidence, is_hit
                    FROM plate_events
                    WHERE is_processed = TRUE
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s
                ''', (limit, offset))
                columns = [desc[0] for desc in cur.description]
                results = []
                for row in cur.fetchall():
                    d = dict(zip(columns, row))
                    # Map filesystem paths to URLs for the frontend
                    d['image_url'] = d['high_res_path'].replace("/mnt/nvme/sabre_data/crops", "/crops")
                    d['thumb_url'] = d['thumbnail_path'].replace("/mnt/nvme/sabre_data/crops", "/crops")
                    # Map 'plate_text' to 'plate' for UI consistency
                    d['plate'] = d['plate_text']
                    results.append(d)
                return results
        except Exception as e:
            logging.error(f"Error getting history: {e}")
            return []
        finally:
            self.connection_pool.putconn(conn)

    def close(self):
        self.connection_pool.closeall()
