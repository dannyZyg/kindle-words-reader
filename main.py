import os
import platform
import sqlite3
import threading
import time
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from db import KindleVocabDB


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates_env = Environment(loader=FileSystemLoader("templates"))

# What we expect the Kindle to be named when it is mounted
VALID_KINDLE_MOUNTS = [
    "Kindle",
    "NO NAME",
]

# We can add more here later as we discover them
MOUNT_POINTS_PER_SYSTEM = {"Darwin": "/Volumes"}

# What port to serve the local "API" on
PORT = 11000

db = None


def shutdown_server():
    print("Exiting...")
    os._exit(0)


@app.get("/lookups", response_class=HTMLResponse)
async def lookups(request: Request):
    global db

    exclude_duplicate_sentences = request.query_params.get('unique') == '1'
    page = int(request.query_params.get('page', 0))
    limit = 5

    try:
        results = db.get_lookups(limit=limit, exclude_duplicate_usage_lookups=exclude_duplicate_sentences, page=page)
    except sqlite3.DatabaseError as e:
        print(e)
        print(
            "Encountered database error during query, assuming Kindle has been unplugged so returning to wait mode."
        )
        # This will typically happen when the Kindle gets unplugged
        # We have to tell the server to shutdown in a separate thread
        # as this request is happening inside the server thread, and
        # so would get deadlocked.

        threading.Thread(target=shutdown_server).start()
    else:
        # If no exception has occurred, return the results

        rendered_rows = []
        template = templates_env.get_template("includes/table_row.html")
        next_page_num = page + 1

        for i, item in enumerate(results):
            is_last_item = i == len(results) - 1
            html_content = template.render(
                item=item,
                is_last_item=is_last_item,
                next_page_num=next_page_num,
                exclude_duplicate_sentences=int(exclude_duplicate_sentences),
            )
            rendered_rows.append(html_content)

        return HTMLResponse(content="".join(rendered_rows))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    template = templates_env.get_template("index.html")
    html_content = template.render()
    return HTMLResponse(content=html_content)


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

    db = KindleVocabDB(db_uri)
    config = uvicorn.Config(app=app, host="127.0.0.1", port=PORT)
    server = uvicorn.Server(config)

    try:
        server.run()
    except KeyboardInterrupt:
        shutdown_server()


if __name__ == "__main__":
    while True:
        print("Waiting for Kindle")
        vocab_db_path = wait_for_kindle()
        print(f"Found Kindle, serving DB on http://localhost:{PORT}")
        serve_db(vocab_db_path)
