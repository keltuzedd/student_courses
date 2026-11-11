"""Хранение данных и запросы SQLite."""
import sqlite3
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_DIR / "students_courses.sqlite3"


def open_database(path=DATABASE_PATH):
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.create_function("casefold", 1, str.casefold)
        connection.executescript((PROJECT_DIR / "schema.sql").read_text(encoding="utf-8"))
    except Exception:
        connection.close()
        raise
    return connection


def list_enrollments(connection, course_id=None):
    query = """
        SELECT s.id, c.id, s.full_name, s.study_group, c.title, e.enrolled_on
        FROM enrollments e
        JOIN students s ON s.id = e.student_id
        JOIN courses c ON c.id = e.course_id
    """
    params = ()
    if course_id is not None:
        query += " WHERE c.id = ?"
        params = (course_id,)
    query += " ORDER BY casefold(c.title), casefold(s.full_name), s.id, c.id"
    return connection.execute(query, params).fetchall()
