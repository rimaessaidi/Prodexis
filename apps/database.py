import sqlite3
from threading import Lock

# Path to database
DB_PATH = 'apps/db.sqlite3'

class DatabaseConnection:
    _instance = None
    _lock = Lock()

    @staticmethod
    def get_instance():
        with DatabaseConnection._lock:
            if DatabaseConnection._instance is None:
                DatabaseConnection.initialize()
            return DatabaseConnection._instance._connection

    @staticmethod
    def initialize():
        with DatabaseConnection._lock:
            if DatabaseConnection._instance is None:
                DatabaseConnection._instance = DatabaseConnection()

    def __init__(self):
        if DatabaseConnection._instance is not None:
            raise Exception("This class is a singleton!")
        self._connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row

    @staticmethod
    def close_connection():
        with DatabaseConnection._lock:
            if DatabaseConnection._instance is not None:
                DatabaseConnection._instance._connection.close()
                DatabaseConnection._instance = None
    