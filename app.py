"""Ancient City Exporter — offline GUI, no Minecraft access required."""
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def validate(seed, border):
    if not re.fullmatch(r'[+-]?[0-9]+', seed.strip()):
        raise ValueError('Сид должен быть целым числом, без потери последних цифр.')
    seed = int(seed)
    if not -(2**63) <= seed < 2**63:
        raise ValueError('Сид вне диапазона signed 64-bit.')
    if not re.fullmatch(r'[0-9]+', border.strip()) or not 1 <= int(border) <= 15900:
        raise ValueError('Граница: от 1 до 15900 блоков от нуля.')
    return str(seed), str(int(border))


def engine_path():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return base / ('city-engine.exe' if sys.platform == 'win32' else 'city-engine')


class App:
    def __init__(self, root):
        self.root = root
        root.title('Ancient City Exporter')
        root.geometry('880x600')
        root.minsize(680, 440)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.result = ''
        self.meta = ''
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Города вардена → готовый маршрут', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Minecraft Java • обычная генерация • расчёт на компьютере').pack(anchor='w', pady=(4, 18))
        fields = ttk.Frame(frame)
        fields.pack(fill='x')
        self.seed = tk.StringVar(value='0')
        self.border = tk.StringVar(value='15900')
        self.version = tk.StringVar(value='1.21')
        self.inputs = []
        for col, (label, var, width) in enumerate([('Сид мира', self.seed, 30), ('Граница ±X / ±Z', self.border, 16)]):
            ttk.Label(fields, text=label).grid(row=0, column=col, sticky='w', padx=(0, 15))
            entry = ttk.Entry(fields, textvariable=var, width=width)
            entry.grid(row=1, column=col, sticky='ew', padx=(0, 15), pady=5)
            self.inputs.append(entry)
        ttk.Label(fields, text='Генератор Cubiomes').grid(row=0, column=2, sticky='w')
        self.versions = ttk.Combobox(fields, textvariable=self.version, values=['1.19', '1.20', '1.21'], state='readonly', width=12)
        self.versions.grid(row=1, column=2, sticky='w')
        fields.columnconfigure(0, weight=1)
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=12)
        self.start = ttk.Button(bar, text='Найти города', command=self.run)
        self.start.pack(side='left')
        self.stop = ttk.Button(bar, text='Отмена', command=self.cancel.set, state='disabled')
        self.stop.pack(side='left', padx=8)
        self.copy = ttk.Button(bar, text='Скопировать для скрипта', command=self.copy_result, state='disabled')
        self.copy.pack(side='right')
        self.save = ttk.Button(bar, text='Сохранить .txt', command=self.save_result, state='disabled')
        self.save.pack(side='right', padx=8)
        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.pack(fill='x')
        self.status = tk.StringVar(value='Введи сид и нажми «Найти города».')
        ttk.Label(frame, textvariable=self.status, wraplength=800).pack(anchor='w', pady=10)
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill='both', expand=True)
        self.output = tk.Text(text_frame, wrap='word', font=('Consolas', 11), state='disabled')
        scroll = ttk.Scrollbar(text_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(fill='both', expand=True)
        ttk.Label(frame, text='Вставь результат в «Свои города X Z; X Z». Кастомные миры и изменённые сервером чанки могут отличаться.', wraplength=800).pack(anchor='w', pady=(12, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(80, self.poll)

    def run(self):
        if self.running:
            return
        try:
            seed, border = validate(self.seed.get(), self.border.get())
        except ValueError as error:
            messagebox.showerror('Проверь параметры', str(error))
            return
        version = self.version.get()
        self.meta = f'Сид {seed} • ±{border} • генератор {version}'
        self.running = True
        self.cancel.clear()
        self.result = ''
        self.set_output('')
        self.start.configure(state='disabled')
        self.stop.configure(state='normal')
        self.copy.configure(state='disabled')
        self.save.configure(state='disabled')
        for entry in self.inputs:
            entry.configure(state='disabled')
        self.versions.configure(state='disabled')
        self.progress['value'] = 0
        self.status.set(self.meta + ' — поиск…')
        threading.Thread(target=self.worker, args=(seed, border, version), daemon=True).start()

    def worker(self, seed, border, version):
        process = None
        try:
            process = subprocess.Popen([str(engine_path()), seed, border, version], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            # Drain stdout concurrently: the engine must not block on a full pipe.
            output = []
            reader = threading.Thread(target=lambda: output.append(process.stdout.read()), daemon=True)
            reader.start()
            def cancel_process():
                while process.poll() is None:
                    if self.cancel.wait(0.1):
                        if process.poll() is None:
                            process.terminate()
                        return
            threading.Thread(target=cancel_process, daemon=True).start()
            errors = []
            for line in process.stderr:
                if line.startswith('PROGRESS '):
                    self.events.put(('progress', int(line.split()[1])))
                elif not line.startswith('COUNT '):
                    errors.append(line)
            code = process.wait()
            reader.join()
            if self.cancel.is_set():
                self.events.put(('cancelled', 'Поиск отменён. Частичный результат не используется.'))
            elif code:
                self.events.put(('error', ''.join(errors).strip() or f'Ошибка движка: {code}'))
            else:
                self.events.put(('done', ''.join(output).strip()))
        except Exception as error:
            if process and process.poll() is None:
                process.terminate()
            self.events.put(('error', str(error)))

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'progress':
                    self.progress['value'] = value
                    continue
                self.running = False
                self.start.configure(state='normal')
                self.stop.configure(state='disabled')
                for entry in self.inputs:
                    entry.configure(state='normal')
                self.versions.configure(state='readonly')
                if kind == 'done':
                    self.result = value
                    count = len(value.split(';')) if value else 0
                    self.status.set(f'{self.meta} — найдено городов: {count}')
                    self.set_output(value)
                    self.copy.configure(state='normal' if value else 'disabled')
                    self.save.configure(state='normal' if value else 'disabled')
                else:
                    self.status.set(value)
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def set_output(self, value):
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')
        self.output.insert('1.0', value)
        self.output.configure(state='disabled')

    def copy_result(self):
        if self.result:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.result)
            self.status.set(self.meta + ' — координаты скопированы')

    def save_result(self):
        path = filedialog.asksaveasfilename(defaultextension='.txt', initialfile='ancient-cities.txt', filetypes=[('Text', '*.txt')])
        if path:
            try:
                Path(path).write_text(self.result + '\n', encoding='utf-8')
            except OSError as error:
                messagebox.showerror('Не удалось сохранить', str(error))

    def close(self):
        self.cancel.set()
        self.root.destroy()


if __name__ == '__main__':
    App(tk.Tk()).root.mainloop()
