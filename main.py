"""Точка входа"""

import sys
import os
import argparse
import tkinter as tk
from tkinter import messagebox, filedialog


def parse_args():
    parser = argparse.ArgumentParser(description="Система медианного голосования")
    parser.add_argument('database', nargs='?', help='Путь к БД')
    parser.add_argument('-d', '--db', dest='database', help='Путь к БД')
    return parser.parse_args()


def select_db_dialog():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    while True:
        filepath = filedialog.askopenfilename(
            title="Выберите файл БД SQLite",
            filetypes=[("SQLite", "*.db *.sqlite *.sqlite3"), ("Все файлы", "*.*")]
        )
        if filepath:
            break
        if not messagebox.askyesno("Выход", "Файл не выбран. Выйти?"):
            continue
        root.destroy()
        return None

    root.destroy()
    return filepath


def main():
    print("=" * 60)
    print("Система медианного голосования")
    print("=" * 60)

    args = parse_args()
    db_path = args.database

    if not db_path:
        print("Файл БД не указан. Открываю диалог...")
        db_path = select_db_dialog()
        if not db_path:
            print("Завершено")
            sys.exit(0)

    if not os.path.exists(db_path):
        print(f"✗ Файл не найден: {db_path}")
        sys.exit(1)

    if not db_path.endswith(('.db', '.sqlite', '.sqlite3')):
        print(f"⚠ Файл не имеет расширения SQLite")
        if input("Продолжить? (y/n): ").strip().lower() != 'y':
            sys.exit(0)

    print(f"✓ БД: {db_path}")
    print(f"✓ Размер: {os.path.getsize(db_path)} байт")
    print("Запуск GUI...")

    from gui.app import start_gui
    start_gui(db_path)


if __name__ == "__main__":
    main()