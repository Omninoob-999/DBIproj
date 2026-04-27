import logging
import queue
import threading
from datetime import datetime
from pymongo import MongoClient

# Thread-safe queue
log_queue = queue.Queue()


class MongoQueueHandler(logging.Handler):
    def emit(self, record):
        if record.name.startswith(("pymongo", "aiosqlite")):
            return

        try:
            log_entry = {
                "timestamp": datetime.utcnow(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            log_queue.put(log_entry)

        except Exception as e:
            print("Logging enqueue error:", e)


def mongo_worker(mongo_uri="mongodb://localhost:27017", db_name="logs_db"):
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db["app_logs"]

    while True:
        try:
            log = log_queue.get()
            collection.insert_one(log)

        except Exception as e:
            print("Mongo logging error:", e)
