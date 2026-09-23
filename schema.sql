-- schema.sql
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS class_records;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('teacher', 'parent'))
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES users (id)
);

CREATE TABLE class_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    record_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('presente', 'ausente')),
    grade INTEGER NOT NULL,
    comments TEXT,
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);