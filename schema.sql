CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL CHECK (trim(full_name) <> ''),
    study_group TEXT NOT NULL CHECK (trim(study_group) <> ''),
    email TEXT NOT NULL CHECK (trim(email) <> '')
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL CHECK (trim(title) <> ''),
    teacher TEXT NOT NULL CHECK (trim(teacher) <> ''),
    hours INTEGER NOT NULL CHECK (typeof(hours) = 'integer' AND hours > 0)
);

CREATE TABLE IF NOT EXISTS enrollments (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_on TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    PRIMARY KEY (student_id, course_id)
);

CREATE INDEX IF NOT EXISTS enrollments_course_idx ON enrollments(course_id);
