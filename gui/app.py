"""Главное окно приложения на Tkinter"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from sqlalchemy import func
import json
import os

from database.connection import get_session
from database.models import ExperimentData, Module, Version
from voting.median_voting import MedianVotingAlgorithm


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

    def __init__(self, parent, on_experiment_selected: Callable[[str], None] = None):
        super().__init__(parent)
        self.selected_experiment_name = None
        self.on_experiment_selected_callback = on_experiment_selected
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="📋 Выбор эксперимента", font=('Arial', 12, 'bold')).pack(pady=5, anchor=tk.W)

        ttk.Label(self, text="Двойной клик или кнопка для выбора",
                  font=('Arial', 9), foreground='gray').pack(anchor=tk.W, padx=5)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('Эксперимент', 'Модулей', 'Версий', 'Записей')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=8)

        self.tree.heading('Эксперимент', text='Название эксперимента')
        self.tree.heading('Модулей', text='Модулей')
        self.tree.heading('Версий', text='Версий')
        self.tree.heading('Записей', text='Записей')

        self.tree.column('Эксперимент', width=300)
        self.tree.column('Модулей', width=100, anchor=tk.CENTER)
        self.tree.column('Версий', width=100, anchor=tk.CENTER)
        self.tree.column('Записей', width=100, anchor=tk.CENTER)

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Одиночный клик - выделение
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        # Двойной клик - подтверждение выбора и переход к модулям
        self.tree.bind('<Double-1>', self.on_double_click)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)

        self.select_btn = ttk.Button(btn_frame, text="✅ Выбрать этот эксперимент",
                                     command=self.on_confirm_selection)
        self.select_btn.pack(side=tk.RIGHT, padx=5)
        self.select_btn.config(state='disabled')

        ttk.Button(btn_frame, text="🔄 Обновить", command=self.on_refresh).pack(side=tk.RIGHT, padx=5)

    def load_experiments(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        session = get_session()
        experiments = session.query(
            ExperimentData.experiment_name,
            func.count(ExperimentData.id).label('total_records'),
            func.count(func.distinct(ExperimentData.module_id)).label('modules_count'),
            func.count(func.distinct(ExperimentData.version_id)).label('versions_count')
        ).group_by(ExperimentData.experiment_name).all()

        for exp in experiments:
            self.tree.insert('', tk.END, values=(
                exp.experiment_name,
                exp.modules_count,
                exp.versions_count,
                exp.total_records
            ))

    def on_select(self, event):
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            self.selected_experiment_name = item['values'][0]
            self.select_btn.config(state='normal')

    def on_double_click(self, event):
        """Двойной клик - подтвердить выбор"""
        self.on_confirm_selection()

    def on_confirm_selection(self):
        """Подтверждение выбора эксперимента"""
        if self.selected_experiment_name and self.on_experiment_selected_callback:
            self.on_experiment_selected_callback(self.selected_experiment_name)

    def on_refresh(self):
        self.load_experiments()

    def get_selected_experiment_name(self) -> Optional[str]:
        return self.selected_experiment_name


class ModulePanel(ttk.Frame):
    """Панель выбора модулей с чекбоксами"""

    def __init__(self, parent):
        super().__init__(parent)
        self.experiment_name = None
        # Хранение состояния: {item_id: {'module_id': int, 'selected': bool}}
        self.module_states = {}
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="📦 Выбор модулей", font=('Arial', 12, 'bold')).pack(pady=5, anchor=tk.W)

        self.info_label = ttk.Label(self, text="Сначала выберите эксперимент на вкладке 1",
                                    font=('Arial', 9), foreground='gray')
        self.info_label.pack(pady=5, anchor=tk.W)

        ttk.Label(self, text="💡 Клик по колонке 'Выбрать' переключает чекбокс",
                  font=('Arial', 9), foreground='blue').pack(anchor=tk.W, padx=5)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('Выбрать', 'ID', 'Название', 'Версий', 'Итераций')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=10)

        self.tree.heading('Выбрать', text='✓ Выбрать')
        self.tree.heading('ID', text='ID')
        self.tree.heading('Название', text='Название модуля')
        self.tree.heading('Версий', text='Версий')
        self.tree.heading('Итераций', text='Итераций')

        self.tree.column('Выбрать', width=80, anchor=tk.CENTER)
        self.tree.column('ID', width=60, anchor=tk.CENTER)
        self.tree.column('Название', width=250)
        self.tree.column('Версий', width=100, anchor=tk.CENTER)
        self.tree.column('Итераций', width=100, anchor=tk.CENTER)

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Обработка клика для переключения чекбокса
        self.tree.bind('<Button-1>', self.on_tree_click)

        # Теги для цветов
        self.tree.tag_configure('selected', background='#d4edda')  # светло-зелёный
        self.tree.tag_configure('unselected', background='#ffffff')

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="✅ Выбрать все", command=self.on_select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Снять выделение", command=self.on_deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Обновить", command=self.on_refresh).pack(side=tk.RIGHT, padx=5)

    def set_experiment(self, experiment_name: str):
        """Загрузка модулей для выбранного эксперимента"""
        self.experiment_name = experiment_name
        self.info_label.config(text=f"Эксперимент: {experiment_name}", foreground='black')

        # Очистка
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.module_states.clear()

        session = get_session()

        # Получаем уникальные модули для этого эксперимента
        modules = session.query(
            ExperimentData.module_id,
            ExperimentData.module_name,
            func.count(func.distinct(ExperimentData.version_id)).label('versions_count'),
            func.count(func.distinct(ExperimentData.module_iteration_num)).label('iterations_count'),
            func.count(ExperimentData.id).label('total_records')
        ).filter(
            ExperimentData.experiment_name == experiment_name
        ).group_by(ExperimentData.module_id, ExperimentData.module_name).all()

        if not modules:
            self.info_label.config(text=f"Эксперимент '{experiment_name}': модули не найдены",
                                   foreground='red')
            return

        for module in modules:
            item_id = self.tree.insert('', tk.END, values=(
                '☑',  # Чекбокс выбран по умолчанию
                module.module_id,
                module.module_name or f"Module_{module.module_id}",
                module.versions_count,
                module.iterations_count
            ), tags=('selected',))

            self.module_states[item_id] = {
                'module_id': module.module_id,
                'selected': True
            }

        print(f"✓ Загружено модулей: {len(modules)} для эксперимента '{experiment_name}'")

    def on_tree_click(self, event):
        """Обработка клика по дереву для переключения чекбокса"""
        # Определяем, по какой колонке кликнули
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)

        if not item_id or item_id not in self.module_states:
            return

        # Переключаем только при клике на первую колонку (чекбокс)
        if column == '#1':
            self._toggle_item(item_id)

    def _toggle_item(self, item_id: str):
        """Переключение состояния чекбокса"""
        if item_id not in self.module_states:
            return

        current_state = self.module_states[item_id]['selected']
        new_state = not current_state
        self.module_states[item_id]['selected'] = new_state

        # Получаем текущие значения
        values = list(self.tree.item(item_id, 'values'))
        values[0] = '☑' if new_state else '☐'
        self.tree.item(item_id, values=values)

        # Обновляем тег для цвета
        self.tree.item(item_id, tags=('selected' if new_state else 'unselected',))

    def on_select_all(self):
        """Выбрать все модули"""
        for item_id in self.module_states.keys():
            self.module_states[item_id]['selected'] = True
            values = list(self.tree.item(item_id, 'values'))
            values[0] = '☑'
            self.tree.item(item_id, values=values, tags=('selected',))

    def on_deselect_all(self):
        """Снять выделение со всех"""
        for item_id in self.module_states.keys():
            self.module_states[item_id]['selected'] = False
            values = list(self.tree.item(item_id, 'values'))
            values[0] = '☐'
            self.tree.item(item_id, values=values, tags=('unselected',))

    def on_refresh(self):
        """Обновить список модулей"""
        if self.experiment_name:
            self.set_experiment(self.experiment_name)

    def get_selected_modules(self) -> List[int]:
        """Получение ID выбранных модулей"""
        return [
            state['module_id']
            for state in self.module_states.values()
            if state['selected']
        ]


class SamplingPanel(ttk.Frame):
    """Панель настройки выборки"""

    def __init__(self, parent):
        super().__init__(parent)
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="⚙️ Параметры выборки", font=('Arial', 12, 'bold')).pack(pady=5, anchor=tk.W)

        params_frame = ttk.LabelFrame(self, text="Фильтрация", padding=10)
        params_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(params_frame, text="Начальный ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.start_id_var = tk.IntVar(value=0)
        ttk.Spinbox(params_frame, from_=0, to=100000, textvariable=self.start_id_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(params_frame, text="Ограничение (0 - все):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.limit_var = tk.IntVar(value=0)
        ttk.Spinbox(params_frame, from_=0, to=10000, textvariable=self.limit_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(params_frame, text="Мин. надёжность:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.reliability_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(params_frame, from_=0.0, to=1.0, increment=0.05, textvariable=self.reliability_var, width=15, format="%.2f").grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        #ttk.Label(params_frame, text="Фильтр версий (V1,V2):").grid(row=3, column=0, sticky=tk.W, pady=5)
        #self.version_filter_var = tk.StringVar(value="")
        #ttk.Entry(params_frame, textvariable=self.version_filter_var, width=15).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

    def get_config(self) -> Dict[str, Any]:
        #version_filter = self.version_filter_var.get().strip()
        return {
            'start_id': self.start_id_var.get(),
            'limit': self.limit_var.get() if self.limit_var.get() > 0 else None,
            'min_reliability': self.reliability_var.get() if self.reliability_var.get() > 0 else None#,
            #'version_names': [v.strip() for v in version_filter.split(',') if v.strip()] if version_filter else None
        }


class VotingPanel(ttk.Frame):
    """Панель настройки голосования"""

    def __init__(self, parent):
        super().__init__(parent)
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="🗳️ Параметры голосования", font=('Arial', 12, 'bold')).pack(pady=5, anchor=tk.W)

        params_frame = ttk.LabelFrame(self, text="Алгоритм", padding=10)
        params_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(params_frame, text="Тип медианы:").pack(anchor=tk.W, pady=5)

        self.median_type_var = tk.StringVar(value="median")
        radio_frame = ttk.Frame(params_frame)
        radio_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(radio_frame, text="Обычная", variable=self.median_type_var, value="median").pack(anchor=tk.W)
        ttk.Radiobutton(radio_frame, text="Нижняя", variable=self.median_type_var, value="median_low").pack(anchor=tk.W)
        ttk.Radiobutton(radio_frame, text="Верхняя", variable=self.median_type_var, value="median_high").pack(anchor=tk.W)
        ttk.Radiobutton(radio_frame, text="Взвешенная", variable=self.median_type_var, value="weighted").pack(anchor=tk.W)

        epsilon_frame = ttk.Frame(params_frame)
        epsilon_frame.pack(fill=tk.X, pady=10)

        ttk.Label(epsilon_frame, text="Порог точности (epsilon):").pack(side=tk.LEFT)
        self.epsilon_var = tk.DoubleVar(value=0.01)
        ttk.Spinbox(epsilon_frame, from_=0.0, to=1.0, increment=0.001, textvariable=self.epsilon_var, width=10, format="%.3f").pack(side=tk.LEFT, padx=10)

    def get_config(self) -> Dict[str, Any]:
        return {
            'median_type': self.median_type_var.get(),
            'use_weighted': self.median_type_var.get() == 'weighted',
            'epsilon': self.epsilon_var.get()
        }


class ResultsPanel(ttk.Frame):
    """Панель результатов"""

    def __init__(self, parent):
        super().__init__(parent)
        self.results = None
        self._create_widgets()

    def _create_widgets(self):
        ttk.Label(self, text="📊 Результаты", font=('Arial', 12, 'bold')).pack(pady=5, anchor=tk.W)

        stats_frame = ttk.LabelFrame(self, text="Статистика", padding=10)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill=tk.X)

        self.total_versions_lbl = ttk.Label(stats_inner, text="Записей: 0")
        self.total_versions_lbl.grid(row=0, column=0, padx=10, pady=5)

        self.total_modules_lbl = ttk.Label(stats_inner, text="Модулей: 0")
        self.total_modules_lbl.grid(row=0, column=1, padx=10, pady=5)

        self.correct_lbl = ttk.Label(stats_inner, text="Корректно: 0")
        self.correct_lbl.grid(row=0, column=2, padx=10, pady=5)

        self.accuracy_lbl = ttk.Label(stats_inner, text="Точность: 0%", font=('Arial', 10, 'bold'))
        self.accuracy_lbl.grid(row=0, column=3, padx=10, pady=5)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('Module ID', 'Результат', 'Правильный', 'Статус', 'Отклонение', 'Версий')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=10)

        for col, text, width in zip(columns, columns, [80, 120, 120, 80, 100, 70]):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=tk.CENTER if col != 'Результат' else "center")

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scrollbar.grid(row=0, column=1, sticky='ns')
        x_scrollbar.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="💾 Сохранить JSON", command=self.on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="🗑️ Очистить", command=self.on_clear).pack(side=tk.RIGHT, padx=5)

        self.tree.tag_configure('correct', background='#d4edda')
        self.tree.tag_configure('incorrect', background='#f8d7da')

    def display_results(self, results: Dict[str, Any]):
        self.results = results
        summary = results['summary']

        self.total_versions_lbl.config(text=f"Записей: {summary['total_records']}")
        self.total_modules_lbl.config(text=f"Модулей: {summary['total_modules']}")
        self.correct_lbl.config(text=f"Корректно: {summary['correct_results']}")

        accuracy = summary['accuracy'] * 100
        self.accuracy_lbl.config(text=f"Точность: {accuracy:.2f}%")
        self.accuracy_lbl.config(foreground='green' if accuracy >= 90 else 'orange' if accuracy >= 70 else 'red')

        for item in self.tree.get_children():
            self.tree.delete(item)

        for module_id, module_result in results['modules'].items():
            status = "✓" if module_result['is_correct'] else "✗"
            deviation = f"{module_result['deviation']:.6f}" if module_result['deviation'] is not None else "N/A"
            correct = str(module_result['correct_answer']) if module_result['correct_answer'] else "N/A"

            self.tree.insert('', tk.END, values=(
                module_id,
                f"{module_result['voted_value']:.6f}",
                correct,
                status,
                deviation,
                module_result['versions_count']
            ), tags=('correct' if module_result['is_correct'] else 'incorrect',))

    def on_save(self):
        if not self.results:
            messagebox.showwarning("Предупреждение", "Нет результатов")
            return

        filepath = filedialog.asksaveasfilename(
            title="Сохранить",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Все файлы", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
                messagebox.showinfo("Успех", f"Сохранено:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка:\n{str(e)}")

    def on_clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.total_versions_lbl.config(text="Записей: 0")
        self.total_modules_lbl.config(text="Модулей: 0")
        self.correct_lbl.config(text="Корректно: 0")
        self.accuracy_lbl.config(text="Точность: 0%", foreground='black')
        self.results = None


class MainFrame(tk.Tk):
    """Главное окно"""

    def __init__(self, db_file_path: str):
        super().__init__()
        self.db_file_path = db_file_path
        self.title("Система медианного голосования")
        self.geometry("1200x800")

        self._create_widgets()
        self._create_menu()
        self._load_data()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ВАЖНО: передаём callback в ExperimentPanel
        self.experiment_panel = ExperimentPanel(
            self.notebook,
            on_experiment_selected=self._on_experiment_selected
        )
        self.module_panel = ModulePanel(self.notebook)
        self.sampling_panel = SamplingPanel(self.notebook)
        self.voting_panel = VotingPanel(self.notebook)
        self.results_panel = ResultsPanel(self.notebook)

        self.notebook.add(self.experiment_panel, text="1. Эксперимент")
        self.notebook.add(self.module_panel, text="2. Модули")
        self.notebook.add(self.sampling_panel, text="3. Выборка")
        self.notebook.add(self.voting_panel, text="4. Голосование")
        self.notebook.add(self.results_panel, text="5. Результаты")

        # Переключение вкладок по событию
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        self.run_btn = ttk.Button(btn_frame, text="🚀 Запустить голосование", command=self.on_run_voting)
        self.run_btn.config(width=30)
        self.run_btn.pack()

        self.status_bar = ttk.Label(self, text=f"Готов | {os.path.basename(self.db_file_path)}",
                                    relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _on_experiment_selected(self, experiment_name: str):
        """Callback при выборе эксперимента - загружаем модули и переключаемся"""
        print(f"Выбран эксперимент: {experiment_name}")
        self.module_panel.set_experiment(experiment_name)
        # Автоматически переключаемся на вкладку модулей
        self.notebook.select(1)
        self.status_bar.config(text=f"Выбран: {experiment_name} | {os.path.basename(self.db_file_path)}")

    def _on_tab_changed(self, event):
        """Обработка переключения вкладок"""
        current_tab = self.notebook.index(self.notebook.select())
        # Если переключаемся на вкладку модулей и есть выбранный эксперимент
        if current_tab == 1:
            exp_name = self.experiment_panel.get_selected_experiment_name()
            if exp_name and self.module_panel.experiment_name != exp_name:
                self.module_panel.set_experiment(exp_name)

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

    def _load_data(self):
        try:
            self.experiment_panel.load_experiments()
            self.status_bar.config(text="Готов | " + os.path.basename(self.db_file_path))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки:\n{str(e)}")

    def on_run_voting(self):
        exp_name = self.experiment_panel.get_selected_experiment_name()
        if not exp_name:
            messagebox.showwarning("Предупреждение", "Выберите эксперимент на вкладке 1")
            self.notebook.select(0)
            return

        module_ids = self.module_panel.get_selected_modules()
        if not module_ids:
            messagebox.showwarning("Предупреждение", "Выберите хотя бы один модуль на вкладке 2")
            self.notebook.select(1)
            return

        sampling_config = self.sampling_panel.get_config()
        voting_config = self.voting_panel.get_config()

        msg = (f"Запустить?\n\nЭксперимент: {exp_name}\n"
               f"Модулей: {len(module_ids)}\nТип: {voting_config['median_type']}\n"
               f"Epsilon: {voting_config['epsilon']}")

        if not messagebox.askyesno("Подтверждение", msg):
            return

        self.status_bar.config(text="Выполнение...")
        self.run_btn.config(state='disabled')
        self.update()

        try:
            results = self.run_voting(exp_name, module_ids, sampling_config, voting_config)
            if results:
                self.results_panel.display_results(results)
                self.status_bar.config(text="Готово")
                self.notebook.select(4)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка:\n{str(e)}")
            import traceback
            traceback.print_exc()
            self.status_bar.config(text="Ошибка")
        finally:
            self.run_btn.config(state='normal')

    def run_voting(self, experiment_name: str, module_ids: List[int],
                   sampling_config: Dict[str, Any], voting_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = get_session()

        query = session.query(ExperimentData).filter(
            ExperimentData.experiment_name == experiment_name,
            ExperimentData.module_id.in_(module_ids)
        )

        if sampling_config['start_id'] > 0:
            query = query.filter(ExperimentData.id >= sampling_config['start_id'])
        if sampling_config['min_reliability']:
            query = query.filter(ExperimentData.version_reliability >= sampling_config['min_reliability'])
        #if sampling_config['version_names']:
            #query = query.filter(ExperimentData.version_name.in_(sampling_config['version_names']))
        if sampling_config['limit']:
            query = query.limit(sampling_config['limit'])

        query = query.order_by(ExperimentData.module_id, ExperimentData.version_name)
        data_list = query.all()

        if not data_list:
            messagebox.showinfo("Информация", "Нет данных с такими фильтрами")
            return None

        # Группировка: module_id -> version_key -> [data, ...]
        grouped = {}
        for data in data_list:
            if data.module_id not in grouped:
                grouped[data.module_id] = {}
            v_key = data.version_name or f"V{data.version_id}"
            if v_key not in grouped[data.module_id]:
                grouped[data.module_id][v_key] = []
            grouped[data.module_id][v_key].append(data)

        algorithm = MedianVotingAlgorithm(epsilon=voting_config['epsilon'])

        results = {
            'experiment_name': experiment_name,
            'db_file': self.db_file_path,
            'timestamp': datetime.now().isoformat(),
            'filters': {'sampling': sampling_config, 'voting': voting_config},
            'modules': {},
            'summary': {
                'total_records': len(data_list),
                'total_modules': len(grouped),
                'correct_results': 0,
                'incorrect_results': 0,
                'accuracy': 0.0
            }
        }

        for module_id, versions_dict in grouped.items():
            # Берём по одной записи каждой версии для голосования
            # Группируем по module_iteration_num - для каждой итерации своё голосование
            iterations = {}
            for version_key, data_items in versions_dict.items():
                for data in data_items:
                    iter_num = data.module_iteration_num
                    if iter_num not in iterations:
                        iterations[iter_num] = []
                    # Добавляем только если ещё не добавили эту версию для этой итерации
                    if not any(d.version_id == data.version_id for d in iterations[iter_num]):
                        iterations[iter_num].append(data)

            # Если есть несколько итераций - голосуем для каждой, берём среднее/первую
            # Для простоты - голосуем по первой итерации с достаточным кол-вом версий
            for iter_num, versions_data in sorted(iterations.items()):
                if len(versions_data) >= 2:
                    if voting_config['use_weighted']:
                        result = algorithm.vote_weighted(versions_data)
                    else:
                        result = algorithm.vote(versions_data, voting_config['median_type'])

                    results['modules'][module_id] = result.to_dict()
                    results['modules'][module_id]['module_name'] = versions_data[0].module_name
                    results['modules'][module_id]['iteration'] = iter_num

                    if result.is_correct is not None:
                        if result.is_correct:
                            results['summary']['correct_results'] += 1
                        else:
                            results['summary']['incorrect_results'] += 1
                    break  # Обрабатываем только первую подходящую итерацию

        total = results['summary']['correct_results'] + results['summary']['incorrect_results']
        if total > 0:
            results['summary']['accuracy'] = results['summary']['correct_results'] / total

        return results

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
                    results = json.load(f)
                self.results_panel.display_results(results)
                self.notebook.select(4)
                messagebox.showinfo("Успех", "Загружено")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка:\n{str(e)}")

    def on_about(self):
        messagebox.showinfo("О программе", "Система медианного голосования\nВерсия 1.1\n\n(C) 2026")

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
        # Создаём временное tk приложение для отображения ошибки
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror("Ошибка", f"Ошибка инициализации БД:\n{str(e)}")
        temp_root.destroy()
        return
    app = MainFrame(db_file_path)
    app.mainloop()