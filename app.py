"""Графический интерфейс системы учёта студентов и курсов."""
import re
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from database import list_enrollments, open_database


def table(parent, headings, widths):
    frame = ttk.Frame(parent)
    columns = tuple(str(index) for index in range(len(headings)))
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    for column, heading, width in zip(columns, headings, widths):
        tree.heading(column, text=heading)
        tree.column(column, width=width, minwidth=70, stretch=(width > 100))
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    frame.pack(fill="both", expand=True)
    return tree


def replace_rows(tree, rows):
    selection = tree.selection()
    tree.delete(*tree.get_children())
    for row_id, values in rows:
        tree.insert("", "end", iid=row_id, values=values)
    if selection and tree.exists(selection[0]):
        tree.selection_set(selection[0])


def student_values(values):
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values[2]):
        raise ValueError("Введите email в формате name@example.com.")
    return values


def course_values(values):
    hours = values[2]
    if not re.fullmatch(r"[0-9]{1,9}", hours) or int(hours) == 0:
        raise ValueError("Укажите целое число часов от 1 до 999 999 999.")
    return (*values[:2], int(hours))


class RecordsTab(ttk.Frame):
    """Форма и таблица для справочника студентов или курсов."""

    def __init__(self, parent, app, name, fields, headings, widths, validate):
        super().__init__(parent, padding=16)
        self.app = app
        self.name = name
        self.fields = fields
        self.validate = validate
        self.record_id = None
        self.inputs = [tk.StringVar(master=self) for _ in fields]

        form = ttk.LabelFrame(self, text="Карточка", padding=12)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(1, weight=1)
        for row, (heading, variable) in enumerate(zip(headings, self.inputs)):
            ttk.Label(form, text=heading).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=3)

        actions = ttk.Frame(form)
        actions.grid(row=len(fields), column=1, sticky="w", pady=(8, 0))
        for label, command in (
            ("Добавить", self.add), ("Сохранить изменения", self.update_record),
            ("Удалить", self.delete), ("Очистить форму", self.clear),
        ):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 6))

        search = ttk.Frame(self)
        search.pack(fill="x", pady=(0, 8))
        ttk.Label(search, text="Поиск").pack(side="left", padx=(0, 8))
        self.search = tk.StringVar(master=self)
        ttk.Entry(search, textvariable=self.search).pack(side="left", fill="x", expand=True)
        ttk.Button(search, text="Сбросить", command=lambda: self.search.set("")).pack(side="left", padx=(8, 0))
        self.tree = table(self, ("ID", *headings), (70, *widths))
        self.tree.bind("<<TreeviewSelect>>", self.load_selected)
        self.search.trace_add("write", lambda *_: self.refresh())

    def refresh(self):
        columns = ", ".join(self.fields)
        conditions = " OR ".join(f"instr(casefold(CAST({field} AS TEXT)), ?) > 0" for field in self.fields)
        term = self.search.get().strip().casefold()
        rows = self.app.db.execute(
            f"SELECT id, {columns} FROM {self.name} WHERE {conditions} "
            f"ORDER BY casefold({self.fields[0]}), id",
            (term,) * len(self.fields),
        )
        replace_rows(self.tree, ((str(row[0]), row) for row in rows))
        if self.record_id is not None and not self.tree.exists(str(self.record_id)):
            self.clear()

    def clear(self):
        self.record_id = None
        self.tree.selection_remove(*self.tree.selection())
        for variable in self.inputs:
            variable.set("")

    def load_selected(self, _event):
        selection = self.tree.selection()
        if selection:
            record_id = int(selection[0])
            if record_id != self.record_id:
                self.record_id = record_id
                for variable, value in zip(self.inputs, self.tree.item(selection[0], "values")[1:]):
                    variable.set(value)

    def read_form(self):
        values = tuple(variable.get().strip() for variable in self.inputs)
        if not all(values):
            raise ValueError("Заполните все поля карточки.")
        return self.validate(values)

    def require_selection(self):
        if self.record_id is None:
            raise ValueError("Выберите строку в таблице.")
        return self.record_id

    def add(self):
        try:
            values = self.read_form()
        except ValueError as error:
            self.app.show_error(error)
            return
        columns = ", ".join(self.fields)
        placeholders = ", ".join("?" for _ in self.fields)
        if self.app.write(f"INSERT INTO {self.name} ({columns}) VALUES ({placeholders})", values, "Запись добавлена."):
            self.clear()

    def update_record(self):
        try:
            record_id = self.require_selection()
            values = self.read_form()
        except ValueError as error:
            self.app.show_error(error)
            return
        assignments = ", ".join(f"{field} = ?" for field in self.fields)
        self.app.write(f"UPDATE {self.name} SET {assignments} WHERE id = ?", (*values, record_id), "Изменения сохранены.")

    def delete(self):
        try:
            record_id = self.require_selection()
        except ValueError as error:
            self.app.show_error(error)
            return
        if messagebox.askyesno("Удаление", "Удалить выбранную запись и все связанные записи на курсы?", parent=self):
            if self.app.write(f"DELETE FROM {self.name} WHERE id = ?", (record_id,), "Запись удалена."):
                self.clear()


class EnrollmentsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        form = ttk.LabelFrame(self, text="Новая запись", padding=12)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(1, weight=1)
        self.students = self.combo(form, 0, "Студент")
        self.courses = self.combo(form, 1, "Курс")
        ttk.Button(form, text="Записать на курс", command=self.add).grid(row=2, column=1, sticky="w", pady=(8, 0))

        filters = ttk.Frame(self)
        filters.pack(fill="x", pady=(0, 8))
        filters.columnconfigure(1, weight=1)
        self.course_filter = self.combo(filters, 0, "Участники курса")
        self.course_filter.bind("<<ComboboxSelected>>", lambda _: self.refresh_table())
        ttk.Button(filters, text="Отменить запись", command=self.delete).grid(row=0, column=2, padx=(8, 0))
        self.tree = table(self, ("ФИО", "Группа", "Курс", "Дата записи"), (245, 100, 240, 110))
        self.count = ttk.Label(self)
        self.count.pack(anchor="w", pady=(8, 0))
        self.student_ids = []
        self.course_ids = []

    @staticmethod
    def combo(parent, row, label):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        combo = ttk.Combobox(parent, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=3)
        return combo

    @staticmethod
    def set_choices(combo, labels, default=""):
        current = combo.get()
        combo.configure(values=labels)
        combo.set(current if current in labels else default)

    def refresh(self):
        students = self.app.db.execute(
            "SELECT id, full_name, study_group FROM students ORDER BY casefold(full_name), id"
        ).fetchall()
        courses = self.app.db.execute(
            "SELECT id, title FROM courses ORDER BY casefold(title), id"
        ).fetchall()
        self.student_ids = [row[0] for row in students]
        self.course_ids = [row[0] for row in courses]
        student_labels = [f"{name} · {group} [#{key}]" for key, name, group in students]
        course_labels = [f"{title} [#{key}]" for key, title in courses]
        self.set_choices(self.students, student_labels)
        self.set_choices(self.courses, course_labels)
        self.set_choices(self.course_filter, ["Все курсы", *course_labels], "Все курсы")
        self.refresh_table()

    def refresh_table(self):
        index = self.course_filter.current()
        course_id = self.course_ids[index - 1] if index > 0 else None
        rows = list_enrollments(self.app.db, course_id)
        replace_rows(self.tree, ((f"{student}:{course}", values) for student, course, *values in rows))
        self.count.configure(text=f"Всего записей: {len(rows)}")

    def add(self):
        student_index = self.students.current()
        course_index = self.courses.current()
        if student_index < 0 or course_index < 0:
            self.app.show_error("Выберите студента и курс.")
            return
        if self.app.write(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
            (self.student_ids[student_index], self.course_ids[course_index]),
            "Студент записан на курс.",
            duplicate_message="Этот студент уже записан на выбранный курс.",
        ):
            if self.course_filter.current() > 0:
                self.course_filter.set(self.courses.get())
                self.refresh_table()

    def delete(self):
        selection = self.tree.selection()
        if not selection:
            self.app.show_error("Выберите запись в списке участников.")
            return
        student_id, course_id = map(int, selection[0].split(":"))
        if messagebox.askyesno("Отмена записи", "Снять выбранного студента с курса?", parent=self):
            self.app.write(
                "DELETE FROM enrollments WHERE student_id = ? AND course_id = ?",
                (student_id, course_id), "Запись на курс отменена.",
            )


class Application:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        root.title("Студенты и курсы")
        root.geometry("940x640")
        root.minsize(760, 490)

        header = ttk.Frame(root, padding=(16, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Студенты и курсы", font=("TkDefaultFont", 19, "bold")).pack(anchor="w")
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=16)

        self.students = RecordsTab(
            notebook, self, "students", ("full_name", "study_group", "email"),
            ("ФИО", "Группа", "Email"), (250, 115, 240), student_values,
        )
        self.courses = RecordsTab(
            notebook, self, "courses", ("title", "teacher", "hours"),
            ("Название", "Преподаватель", "Часы"), (255, 245, 80), course_values,
        )
        self.enrollments = EnrollmentsTab(notebook, self)
        notebook.add(self.students, text="Студенты")
        notebook.add(self.courses, text="Курсы")
        notebook.add(self.enrollments, text="Записи на курсы")

        self.status = tk.StringVar(master=root, value="Готово к работе")
        ttk.Label(root, textvariable=self.status, padding=(16, 9)).pack(fill="x")
        self.refresh()

    def refresh(self):
        self.students.refresh()
        self.courses.refresh()
        self.enrollments.refresh()

    def show_error(self, error):
        messagebox.showerror("Проверьте данные", str(error), parent=self.root)

    def write(self, query, params, success, duplicate_message=None):
        try:
            with self.db:
                result = self.db.execute(query, params)
        except sqlite3.IntegrityError as error:
            if duplicate_message and error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
                self.show_error(duplicate_message)
            else:
                self.show_error("Нарушено ограничение базы данных. Проверьте выбранные записи.")
            return False
        except sqlite3.Error as error:
            self.show_error(f"Ошибка базы данных: {error}")
            return False

        self.refresh()
        if result.rowcount == 0:
            self.show_error("Запись уже удалена. Список обновлён.")
            return False
        self.status.set(success)
        return True


def main():
    root = tk.Tk()
    try:
        db = open_database()
    except (OSError, sqlite3.Error) as error:
        root.withdraw()
        messagebox.showerror("Ошибка запуска", f"Не удалось открыть базу данных: {error}", parent=root)
        root.destroy()
        return
    try:
        Application(root, db)
        root.mainloop()
    finally:
        db.close()


if __name__ == "__main__":
    main()
