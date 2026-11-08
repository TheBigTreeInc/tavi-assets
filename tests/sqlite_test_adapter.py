"""Test-only sqlite3 execution adapter for hosts without optional SQLAlchemy.

Implements ONLY SQL calls exercised by the LoopRD registry tests. It is never
packaged as an application dependency or used by production LoopRD handlers.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def text(query):
    return query


class Result:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def mappings(self):
        return self

    def all(self):
        return [dict(row) for row in self.cursor.fetchall()]

    def first(self):
        row = self.cursor.fetchone()
        return dict(row) if row is not None else None

    def scalar(self):
        row = self.cursor.fetchone()
        return row[0] if row is not None else None


class Session:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.conn.rollback()
        self.conn.close()

    def execute(self, stmt, params=None):
        return Result(self.conn.execute(stmt, params or {}))

    def commit(self):
        self.conn.commit()


class Engine:
    def __init__(self, url):
        assert url.startswith('sqlite:///'), 'test adapter allows SQLite only'
        self.path = Path(url[len('sqlite:///'):])

    @contextmanager
    def begin(self):
        with Session(self.path) as session:
            try:
                yield session
                session.commit()
            except BaseException:
                session.conn.rollback()
                raise


def create_engine(url):
    return Engine(url)


def sessionmaker(*, bind):
    return lambda: Session(bind.path)
