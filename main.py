import os
import platform
import sqlite3
import threading
import time
import uvicorn
from typing import Annotated
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from db import KindleVocabDB
from params import Filters, Sorting


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


def shutdown_server():
    print("Exiting...")
    if hasattr(app.state, 'db_instance') and app.state.db_instance:
        app.state.db_instance.close()
    os._exit(0)


def get_db(request: Request) -> KindleVocabDB:
    """Dependency that provides the shared KindleVocabDB instance."""
    # The instance is stored in the app state during startup
    db_instance = request.app.state.db_instance
    return db_instance


@app.get("/lookups", response_class=HTMLResponse)
async def lookups(request: Request, db: Annotated[KindleVocabDB, Depends(get_db)]):
    sorting = Sorting.from_query_params(request.query_params)
    filters = Filters.from_query_params(request.query_params)

    try:
        results = db.get_lookups(
            filters=filters,
        )
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
        return HTMLResponse(content="<p>Database error. Server shutting down.</p>", status_code=500)
    else:
        # If no exception has occurred, return the results

        rendered_rows = []
        row_template = templates_env.get_template("includes/table_row.html")

        for i, item in enumerate(results):
            is_last_item = i == len(results) - 1
            html_content = row_template.render(
                item=item,
                is_last_item=is_last_item,
                filters=filters,
                sorting=sorting,
            )
            rendered_rows.append(html_content)


        if results:
            # This will set up the page number in the form for the next page of the query
            page_num = f'<input type="hidden" id="page-filter-hidden" name="page" value="{ filters.page + 1 }" hx-swap-oob="true">'
        else:
            page_num = ""

        rows_html = "".join(rendered_rows)
        return HTMLResponse(content=rows_html + page_num)


@app.get("/", response_class=HTMLResponse)
async def index(_: Request, db: Annotated[KindleVocabDB, Depends(get_db)]):
    filters = Filters(show_unique_sentences="false")
    sorting = Sorting()

    books = db.get_books_with_lookups()
    template = templates_env.get_template("index.html")
    html_content = template.render(filters=filters, sorting=sorting, books=books)
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
    db_uri = f"file:{vocab_db_path}?mode=ro"

    try:
        db_instance = KindleVocabDB.instance(db_uri)
        app.state.db_instance = db_instance
        print("Database instance created and stored in app state.")
    except Exception as e:
        print(f"Failed to initialize database instance: {e}")
        return # Exit the function, preventing the server from starting

    config = uvicorn.Config(app=app, host="127.0.0.1", port=PORT)
    server = uvicorn.Server(config)

    print(f"Starting server on http://localhost:{PORT}")

    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutdown requested via KeyboardInterrupt...")
    finally:
        shutdown_server()

if __name__ == "__main__":
    while True:
        print("Waiting for Kindle")
        vocab_db_path = wait_for_kindle()
        print(f"Found Kindle, serving DB on http://localhost:{PORT}")
        serve_db(vocab_db_path)
