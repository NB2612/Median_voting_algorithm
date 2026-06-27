"""Главное окно приложения на Tkinter"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from sqlalchemy import func
import json
import os

from database.connection import get_session
from database.models import ExperimentData, VotingRun
from voting.median_voting import VotingAlgorithm


class DatabaseSelectorDialog(tk.Toplevel):
    """Диалог выбора файла БД"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Выбор файла базы данных")
        self.geometry("600x180")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result_path = None
        self._create_widgets()
        self.center_window()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Укажите путь к файлу SQLite:", font=('Arial', 10)).pack(pady=(0, 10), anchor=tk.W)

        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, font=('Arial', 10))
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.path_entry.bind('<Return>', lambda e: self.on_ok())

        ttk.Button(path_frame, text="Обзор...", command=self.on_browse).pack(side=tk.RIGHT)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(btn_frame, text="OK", command=self.on_ok, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.on_cancel, width=10).pack(side=tk.RIGHT)

        self.path_entry.focus_set()

    def center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    def on_browse(self):
        filepath = filedialog.askopenfilename(
            title="Выберите файл БД",
            filetypes=[("SQLite файлы", "*.db *.sqlite *.sqlite3"), ("Все файлы", "*.*")]
        )
        if filepath:
            self.path_var.set(filepath)

    def on_ok(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("Предупреждение", "Укажите путь к файлу")
            return
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", f"Файл не найден:\n{path}")
            return
        if not path.endswith(('.db', '.sqlite', '.sqlite3')):
            if not messagebox.askyesno("Предупреждение", "Файл не имеет расширения SQLite. Продолжить?"):
                return
        self.result_path = path
        self.destroy()

    def on_cancel(self):
        self.destroy()

    def get_path(self) -> Optional[str]:
        return self.result_path


class ExperimentPanel(ttk.Frame):
    """Панель выбора эксперимента"""

    def __init__(self, parent, on_run_clicked: Callable[[str], None] = None):
        super().__init__(parent)
        self.selected_experiment_name = None
        self.on_run_clicked_callback = on_run_clicked
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="📋 Выбор эксперимента", font=('Arial', 14, 'bold')).pack(pady=10, anchor=tk.W)

        ttk.Label(self, text="Выберите эксперимент и нажмите 'Запустить' для вычисления двух алгоритмов",
                  font=('Arial', 9), foreground='gray').pack(anchor=tk.W, padx=10)

        # Фрейм для таблицы
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Эксперимент', 'Записей', 'Уникальных значений')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=10)

        self.tree.heading('Эксперимент', text='Название эксперимента')
        self.tree.heading('Записей', text='Всего записей')
        self.tree.heading('Уникальных значений', text='Уникальных version_answer')

        self.tree.column('Эксперимент', width=350)
        self.tree.column('Записей', width=120, anchor=tk.CENTER)
        self.tree.column('Уникальных значений', width=150, anchor=tk.CENTER)

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<Double-1>', lambda e: self.on_run())

        # Кнопки
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10)

        self.run_btn = ttk.Button(btn_frame, text="🚀 Запустить оба алгоритма",
                                   command=self.on_run, width=30)
        self.run_btn.pack(side=tk.RIGHT, padx=5)
        self.run_btn.config(state='disabled')

        ttk.Button(btn_frame, text="🔄 Обновить", command=self.on_refresh).pack(side=tk.RIGHT, padx=5)

    def load_experiments(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        session = get_session()
        experiments = session.query(
            ExperimentData.experiment_name,
            func.count(ExperimentData.id).label('total_records'),
            func.count(func.distinct(ExperimentData.version_answer)).label('unique_answers')
        ).group_by(ExperimentData.experiment_name).all()

        for exp in experiments:
            self.tree.insert('', tk.END, values=(
                exp.experiment_name,
                exp.total_records,
                exp.unique_answers
            ))

    def on_select(self, event):
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            self.selected_experiment_name = item['values'][0]
            self.run_btn.config(state='normal')

    def on_run(self):
        if self.selected_experiment_name and self.on_run_clicked_callback:
            self.on_run_clicked_callback(self.selected_experiment_name)

    def on_refresh(self):
        self.load_experiments()

    def get_selected_experiment_name(self) -> Optional[str]:
        return self.selected_experiment_name


class ResultsPanel(ttk.Frame):
    """Панель результатов с одновременным отображением двух алгоритмов"""

    def __init__(self, parent):
        super().__init__(parent)
        self.all_runs = []
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="📊 Результаты голосования (сравнение алгоритмов)",
                  font=('Arial', 14, 'bold')).pack(pady=10, anchor=tk.W)

        # Кнопки управления
        btn_frame_top = ttk.Frame(self)
        btn_frame_top.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame_top, text="💾 Сохранить в БД", command=self.on_save_to_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_top, text="💾 Сохранить JSON", command=self.on_save_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_top, text="🗑️ Очистить все", command=self.on_clear_all).pack(side=tk.RIGHT, padx=5)

        # Информация о запусках
        self.runs_info_lbl = ttk.Label(self, text="Всего запусков: 0 | Совпадений: 0 | Расхождений: 0",
                                        font=('Arial', 10), foreground='blue')
        self.runs_info_lbl.pack(pady=5, anchor=tk.W)

        # Таблица результатов
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = (
            'ID', 'Эксперимент', 'Алгоритм',
            'Результат', 'Правильный', 'Статус', 'Отклонение',
            'Совпадает', 'Время'
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        column_widths = {
            'ID': 50, 'Эксперимент': 200, 'Алгоритм': 150,
            'Результат': 130, 'Правильный': 130, 'Статус': 70,
            'Отклонение': 110, 'Совпадает': 100, 'Время': 160
        }

        for col in columns:
            self.tree.heading(col, text=col)
            width = column_widths.get(col, 100)
            anchor = tk.CENTER if col not in ['Результат', 'Отклонение', 'Правильный'] else "e"
            self.tree.column(col, width=width, anchor=anchor)

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Теги для цветов
        self.tree.tag_configure('correct', background='#d4edda')
        self.tree.tag_configure('incorrect', background='#f8d7da')
        self.tree.tag_configure('match', foreground='green')
        self.tree.tag_configure('mismatch', foreground='red')

    def add_run(self, run_data: Dict[str, Any]):
        """Добавление нового запуска с результатами двух алгоритмов"""
        run_id = len(self.all_runs) + 1
        run_data['run_id'] = run_id
        run_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.all_runs.append(run_data)

        self._update_table()
        self._update_stats()

    def _update_table(self):
        """Обновление таблицы со всеми запусками"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for run in self.all_runs:
            experiment_name = run['experiment_name']
            timestamp = run['timestamp']

            median_result = run['median_result']
            majority_result = run['majority_result']

            # Проверяем совпадение
            match = abs(median_result['voted_value'] - majority_result['voted_value']) < 1e-9
            match_str = "✓ ДА" if match else "✗ НЕТ"
            match_tag = 'match' if match else 'mismatch'

            # Строка для медианы
            median_status = "✓" if median_result['is_correct'] else "✗"
            median_deviation = f"{median_result['deviation']:.6f}" if median_result['deviation'] is not None else "N/A"
            median_correct = str(median_result['correct_answer']) if median_result['correct_answer'] else "N/A"

            self.tree.insert('', tk.END, values=(
                run['run_id'],
                experiment_name,
                "Медиана",
                f"{median_result['voted_value']:.6f}",
                median_correct,
                median_status,
                median_deviation,
                match_str,
                timestamp
            ), tags=('correct' if median_result['is_correct'] else 'incorrect', match_tag))

            # Строка для абсолютного большинства
            majority_status = "✓" if majority_result['is_correct'] else "✗"
            majority_deviation = f"{majority_result['deviation']:.6f}" if majority_result['deviation'] is not None else "N/A"
            majority_correct = str(majority_result['correct_answer']) if majority_result['correct_answer'] else "N/A"

            self.tree.insert('', tk.END, values=(
                run['run_id'],
                experiment_name,
                "Абс. большинство",
                f"{majority_result['voted_value']:.6f}",
                majority_correct,
                majority_status,
                majority_deviation,
                match_str,
                timestamp
            ), tags=('correct' if majority_result['is_correct'] else 'incorrect', match_tag))

    def _update_stats(self):
        """Обновление статистики"""
        total_runs = len(self.all_runs)

        matches = 0
        mismatches = 0

        for run in self.all_runs:
            median_val = run['median_result']['voted_value']
            majority_val = run['majority_result']['voted_value']

            if abs(median_val - majority_val) < 1e-9:
                matches += 1
            else:
                mismatches += 1

        self.runs_info_lbl.config(
            text=f"Всего запусков: {total_runs} | Совпадений: {matches} | Расхождений: {mismatches}"
        )

    def on_save_to_db(self):
        """Сохранение всех запусков в базу данных"""
        if not self.all_runs:
            messagebox.showwarning("Предупреждение", "Нет результатов для сохранения")
            return

        session = get_session()
        saved_count = 0

        try:
            for run in self.all_runs:
                if run.get('saved_to_db', False):
                    continue

                # Сохраняем результат медианы
                voting_run = VotingRun(
                    experiment_name=run['experiment_name'],
                    algorithm_type='median',
                    median_type='median',
                    epsilon=run['epsilon'],
                    module_id=0,
                    module_name='all',
                    voted_value=run['median_result']['voted_value'],
                    correct_answer=run['median_result']['correct_answer'],
                    is_correct=1 if run['median_result']['is_correct'] else 0,
                    deviation=run['median_result']['deviation'],
                    versions_count=run['median_result']['values_count'],
                    versions_answers=json.dumps(run['median_result']['all_values']),
                    total_records=run['total_records'],
                    total_modules=1
                )
                session.add(voting_run)
                saved_count += 1

                # Сохраняем результат абсолютного большинства
                voting_run = VotingRun(
                    experiment_name=run['experiment_name'],
                    algorithm_type='absolute_majority',
                    median_type=None,
                    epsilon=run['epsilon'],
                    module_id=0,
                    module_name='all',
                    voted_value=run['majority_result']['voted_value'],
                    correct_answer=run['majority_result']['correct_answer'],
                    is_correct=1 if run['majority_result']['is_correct'] else 0,
                    deviation=run['majority_result']['deviation'],
                    versions_count=run['majority_result']['values_count'],
                    versions_answers=json.dumps(run['majority_result']['all_values']),
                    total_records=run['total_records'],
                    total_modules=1
                )
                session.add(voting_run)
                saved_count += 1

                run['saved_to_db'] = True

            session.commit()
            messagebox.showinfo("Успех", f"Сохранено {saved_count} записей в базу данных")

        except Exception as e:
            session.rollback()
            messagebox.showerror("Ошибка", f"Ошибка сохранения в БД:\n{str(e)}")
        finally:
            session.close()

    def on_save_json(self):
        """Сохранение в JSON"""
        if not self.all_runs:
            messagebox.showwarning("Предупреждение", "Нет результатов")
            return

        filepath = filedialog.asksaveasfilename(
            title="Сохранить",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Все файлы", "*.*")]
        )

        if filepath:
            try:
                data = {
                    'total_runs': len(self.all_runs),
                    'runs': self.all_runs
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                messagebox.showinfo("Успех", f"Сохранено:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка:\n{str(e)}")

    def on_clear_all(self):
        """Очистка всех результатов"""
        if not self.all_runs:
            return

        if not messagebox.askyesno("Подтверждение", "Очистить все результаты?"):
            return

        self.all_runs.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.runs_info_lbl.config(text="Всего запусков: 0 | Совпадений: 0 | Расхождений: 0")


class MainFrame(tk.Tk):
    """Главное окно"""

    def __init__(self, db_file_path: str):
        super().__init__()
        self.db_file_path = db_file_path
        self.title("Система голосования: медиана vs абсолютное большинство")
        self.geometry("1200x700")

        self.algorithm = VotingAlgorithm()

        self._create_widgets()
        self._create_menu()
        self._load_data()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.experiment_panel = ExperimentPanel(
            self.notebook,
            on_run_clicked=self._on_run_clicked
        )
        self.results_panel = ResultsPanel(self.notebook)

        self.notebook.add(self.experiment_panel, text="1. Эксперимент")
        self.notebook.add(self.results_panel, text="2. Результаты (сравнение)")

        self.status_bar = ttk.Label(self, text=f"Готов | {os.path.basename(self.db_file_path)}",
                                    relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _on_run_clicked(self, experiment_name: str):
        """Запуск двух алгоритмов для выбранного эксперимента"""
        self.status_bar.config(text=f"Выполнение для '{experiment_name}'...")
        self.update()

        try:
            result = self.run_both_voting(experiment_name)
            if result:
                self.results_panel.add_run(result)
                self.status_bar.config(text=f"Готово | {experiment_name}")
                self.notebook.select(1)

                # Показываем статистику
                median_val = result['median_result']['voted_value']
                majority_val = result['majority_result']['voted_value']
                match = "✓ ДА" if abs(median_val - majority_val) < 1e-9 else "✗ НЕТ"

                messagebox.showinfo(
                    "Результаты сравнения",
                    f"Эксперимент: {experiment_name}\n"
                    f"Всего значений: {result['total_records']}\n\n"
                    f"Медиана: {median_val:.6f}\n"
                    f"Абс. большинство: {majority_val:.6f}\n\n"
                    f"Совпадают: {match}"
                )

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка:\n{str(e)}")
            import traceback
            traceback.print_exc()
            self.status_bar.config(text="Ошибка")

    def run_both_voting(self, experiment_name: str) -> Optional[Dict[str, Any]]:
        """
        Запуск ОБОИХ алгоритмов по ВСЕМ значениям эксперимента сразу

        Правильный ответ для каждого алгоритма вычисляется СВОИМ методом:
        - Для медианы: медиана всех correct_answer
        - Для абсолютного большинства: самое частое correct_answer (мода)
        """
        session = get_session()

        # Получаем ВСЕ записи эксперимента
        query = session.query(ExperimentData).filter(
            ExperimentData.experiment_name == experiment_name
        ).order_by(ExperimentData.version_answer)

        data_list = query.all()

        if not data_list:
            messagebox.showinfo("Информация", f"Нет данных для эксперимента '{experiment_name}'")
            return None

        # Извлекаем ВСЕ version_answer
        all_values = [d.version_answer for d in data_list]

        # Извлекаем ВСЕ correct_answer (только ненулевые)
        all_correct_answers = [d.correct_answer for d in data_list if d.correct_answer is not None]

        print(f"\n{'=' * 80}")
        print(f"ОТЛАДКА: Эксперимент '{experiment_name}'")
        print(f"{'=' * 80}")
        print(f"Всего записей: {len(all_values)}")
        print(f"Уникальных version_answer: {len(set(all_values))}")
        print(f"Всего correct_answer: {len(all_correct_answers)}")
        print(f"Уникальных correct_answer: {len(set(all_correct_answers))}")
        print()

        # Анализ частот version_answer
        from collections import Counter
        values_counter = Counter(all_values)
        correct_counter = Counter(all_correct_answers)

        print("ТОП-5 самых частых version_answer:")
        for i, (value, count) in enumerate(values_counter.most_common(5), 1):
            print(f"  {i}. {value:<20} встречается {count} раз")

        print()
        print("ТОП-5 самых частых correct_answer:")
        for i, (value, count) in enumerate(correct_counter.most_common(5), 1):
            print(f"  {i}. {value:<20} встречается {count} раз")

        print(f"{'=' * 80}\n")

        # Запускаем МЕДИАНОЕ голосование
        # Правильный ответ = медиана всех correct_answer
        median_result = self.algorithm.vote_median(all_values, all_correct_answers)
        print(f"РЕЗУЛЬТАТ МЕДИАНЫ:")
        print(f"  - Голосование: {median_result.voted_value}")
        print(f"  - Правильный ответ (медиана correct_answer): {median_result.correct_answer}")
        print(f"  - Правильно: {median_result.is_correct}")
        print(f"  - Отклонение: {median_result.deviation}")
        print()

        # Запускаем АБСОЛЮТНОЕ БОЛЬШИНСТВО
        # Правильный ответ = самое частое correct_answer (мода)
        majority_result = self.algorithm.vote_absolute_majority(all_values, all_correct_answers)
        print(f"РЕЗУЛЬТАТ АБСОЛЮТНОГО БОЛЬШИНСТВА:")
        print(f"  - Голосование: {majority_result.voted_value}")
        print(f"  - Правильный ответ (мода correct_answer): {majority_result.correct_answer}")
        print(f"  - Абсолютное большинство (>50%): {majority_result.additional_info.get('has_absolute_majority')}")
        print(f"  - Правильно: {majority_result.is_correct}")
        print(f"  - Отклонение: {majority_result.deviation}")
        print(f"{'=' * 80}\n")

        return {
            'experiment_name': experiment_name,
            'db_file': self.db_file_path,
            'epsilon': self.algorithm.epsilon,
            'total_records': len(all_values),
            'saved_to_db': False,
            'median_result': median_result.to_dict(),
            'majority_result': majority_result.to_dict()
        }

    def _load_data(self):
        try:
            self.experiment_panel.load_experiments()
            self.status_bar.config(text="Готов | " + os.path.basename(self.db_file_path))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки:\n{str(e)}")

    def _create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Загрузить результаты", command=self.on_load_results)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        menubar.add_cascade(label="Файл", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Обновить", command=self.on_refresh)
        menubar.add_cascade(label="Вид", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.on_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.config(menu=menubar)

    def on_refresh(self):
        self.experiment_panel.load_experiments()
        messagebox.showinfo("Информация", "Обновлено")

    def on_load_results(self):
        filepath = filedialog.askopenfilename(
            title="Загрузить",
            filetypes=[("JSON", "*.json"), ("Все файлы", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                runs = data.get('runs', [data])
                for run in runs:
                    self.results_panel.add_run(run)

                self.notebook.select(1)
                messagebox.showinfo("Успех", f"Загружено {len(runs)} запусков")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка:\n{str(e)}")

    def on_about(self):
        info = (
            "Система сравнения алгоритмов голосования\n"
            "Версия 4.0\n\n"
            "Алгоритмы:\n"
            "1. Медиана (statistics.median)\n"
            "2. Абсолютное большинство\n\n"
            "Вычисления по ВСЕМ значениям эксперимента\n\n"
            "(C) 2026"
        )
        messagebox.showinfo("О программе", info)

    def on_close(self):
        from database.connection import close_database
        close_database()
        self.destroy()


def start_gui(db_file_path: str):
    """Запуск GUI"""
    from database.connection import init_database
    try:
        init_database(db_file_path)
    except Exception as e:
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror("Ошибка", f"Ошибка инициализации БД:\n{str(e)}")
        temp_root.destroy()
        return
    app = MainFrame(db_file_path)
    app.mainloop()