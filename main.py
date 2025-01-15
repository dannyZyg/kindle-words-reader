import json
import os
import platform
import sqlite3
import threading
import time

from http.server import BaseHTTPRequestHandler, HTTPServer

# What we expect the Kindle to be named when it is mounted
VALID_KINDLE_MOUNTS = [
    "Kindle",
    "NONAME",
]

# We can add more here later as we discover them
MOUNT_POINTS_PER_SYSTEM = {"Darwin": "/Volumes"}

# What port to serve the local "API" on
PORT = 11000

db = None


class KindleVocabServer(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    # Just blindly allow any request to / to get the WORDS table
    # in a JSON format
    def do_GET(self):
        global db
        cursor = db.cursor()
        try:
            results = cursor.execute("SELECT * FROM WORDS").fetchall()
        except sqlite3.DatabaseError:
            print(
                "Encountered database error during query, assuming Kindle has been unplugged so returning to wait mode."
            )
            # This will typically happen when the Kindle gets unplugged
            # We have to tell the server to shutdown in a separate thread
            # as this request is happening inside the server thread, and
            # so would get deadlocked.
            threading.Thread(target=self.server.shutdown).start()
        else:
            # If no exception has occurred, return the results
            data = [dict(row) for row in results]

            self._set_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))


def wait_for_kindle():
    while True:
        mount_point = MOUNT_POINTS_PER_SYSTEM.get(platform.system())
        if mount_point is None:
            raise RuntimeError(f"Unsupported OS: {platform.system()}")
        else:
            mounts = os.listdir(mount_point)

        try:
            found_mount = (set(mounts) & set(VALID_KINDLE_MOUNTS)).pop()
        except KeyError:
            continue

        maybe_kindle_path = os.path.join(mount_point, found_mount)
        vocab_db_path = os.path.join(
            maybe_kindle_path, "system", "vocabulary", "vocab.db"
        )

        try:
            os.stat(vocab_db_path)
        except FileNotFoundError:
            # Probably not a Kindle?
            print(
                f"vocab.db not found on likely mount point of {maybe_kindle_path}, sleeping."
            )
            time.sleep(5)
            continue

        return vocab_db_path


def serve_db(vocab_db_path):
    # Connect to the DB in read only mode and serve it up
    global db
    db_uri = f"file:{vocab_db_path}?mode=ro"

    db = sqlite3.connect(db_uri, uri=True)
    db.row_factory = sqlite3.Row

    httpd = HTTPServer(("", PORT), KindleVocabServer)
    httpd.serve_forever()


if __name__ == "__main__":
    while True:
        print("Waiting for Kindle")
        vocab_db_path = wait_for_kindle()
        print(f"Found Kindle, serving DB on http://localhost:{PORT}")
        serve_db(vocab_db_path)
