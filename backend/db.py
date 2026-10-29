"""SQLite context managers that also release native handles deterministically."""
import sqlite3
class ClosingConnection(sqlite3.Connection):
    def __exit__(self,exc_type,exc_value,traceback):
        try:return super().__exit__(exc_type,exc_value,traceback)
        finally:self.close()
