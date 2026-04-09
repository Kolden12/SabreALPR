import os
import time
import csv
import threading
from PyQt5.QtCore import QObject, pyqtSignal

class DataMonitor(QObject):
    # Signals for UI updates: dict containing plate data, boolean for hit
    new_read_signal = pyqtSignal(dict, bool)

    def __init__(self, results_file="Z:\\results.txt", watchlist_file="watchlist.csv"):
        super().__init__()
        self.results_file = results_file
        self.watchlist_file = watchlist_file
        self._run_flag = True
        self.last_size = 0
        self.watchlist = self.load_watchlist()

        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.watch_file, daemon=True)
        self.monitor_thread.start()

    def load_watchlist(self):
        watchlist = set()
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        # Expecting Plate, State as first two columns (at least)
                        if len(row) >= 2:
                            plate = row[0].strip().upper()
                            state = row[1].strip().upper()
                            watchlist.add((plate, state))
            except Exception as e:
                print(f"Error reading watchlist: {e}")
        return watchlist

    def reload_watchlist(self):
        self.watchlist = self.load_watchlist()

    def watch_file(self):
        # Initial wait for file to exist
        while self._run_flag and not os.path.exists(self.results_file):
            time.sleep(2)

        if not self._run_flag:
            return

        self.last_size = os.path.getsize(self.results_file)

        while self._run_flag:
            try:
                if not os.path.exists(self.results_file):
                    time.sleep(1)
                    continue

                current_size = os.path.getsize(self.results_file)
                if current_size > self.last_size:
                    # New data added
                    with open(self.results_file, 'r', encoding='utf-8') as f:
                        f.seek(self.last_size)
                        new_data = f.read()
                        self.last_size = current_size

                    # Parse new lines
                    reader = csv.reader(new_data.strip().splitlines())
                    for row in reader:
                        if len(row) >= 6:
                            # 2026-04-09 13:45:01, ABC1234, TX, Black, Ford, Explorer
                            timestamp = row[0].strip()
                            plate = row[1].strip()
                            state = row[2].strip()
                            color = row[3].strip()
                            make = row[4].strip()
                            model = row[5].strip()

                            confidence = 100.0
                            if len(row) >= 7:
                                try:
                                    confidence = float(row[6].strip())
                                except ValueError:
                                    pass

                            is_hit = (plate.upper(), state.upper()) in self.watchlist

                            read_data = {
                                "timestamp": timestamp,
                                "plate": plate,
                                "state": state,
                                "color": color,
                                "make": make,
                                "model": model,
                                "confidence": confidence
                            }

                            self.new_read_signal.emit(read_data, is_hit)

                elif current_size < self.last_size:
                    # File was truncated/rotated
                    self.last_size = 0

            except Exception as e:
                print(f"Error in data monitor: {e}")

            time.sleep(0.5)

    def stop(self):
        self._run_flag = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
