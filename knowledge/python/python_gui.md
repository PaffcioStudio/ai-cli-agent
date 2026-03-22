# Python GUI – Frameworki, wybór i praktyczne wzorce

## Ważne: PyQt6 vs PySide6 – użyj PySide6

PyQt6 i PySide6 są IDENTYCZNE pod względem API i możliwości. Obie biblioteki to bindingi Qt6 dla Pythona. Różnica jest tylko w licencji:

PyQt6 – licencja GPL + komercyjna. Jeśli tworzysz zamknięte oprogramowanie (closed-source) musisz KUPIĆ licencję komercyjną od Riverbank Computing. Koszt: kilkaset dolarów rocznie.

PySide6 – licencja LGPL + komercyjna Qt. Możesz używać w zamkniętych aplikacjach BEZPŁATNIE o ile dynamicznie linkujesz bibliotekę (co jest domyślne przy pip install). Oficjalnie wspierane przez Qt Company.

Decyzja: ZAWSZE używaj PySide6 chyba że użytkownik już ma projekt w PyQt6.
Migracja PyQt6 → PySide6: zamień import PyQt6 na PySide6, pyqtSignal → Signal, pyqtSlot → Slot.

## PySide6 – Qt dla Pythona

Kiedy używać: profesjonalne aplikacje desktopowe, złożone UI, dostęp do pełnego Qt (multimedia, sieć, bazy danych, OpenGL).

```bash
pip install PySide6
```

```python
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QFont, QColor, QIcon

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Moja Aplikacja')
        self.setMinimumSize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.label = QLabel('Witaj!')
        self.label.setAlignment(Qt.AlignCenter)

        self.input = QLineEdit()
        self.input.setPlaceholderText('Wpisz coś...')

        btn = QPushButton('Kliknij')
        btn.clicked.connect(self.on_click)

        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(btn)

    @Slot()
    def on_click(self):
        text = self.input.text()
        self.label.setText(f'Wpisałeś: {text}')

app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
```

### PySide6 – długotrwałe operacje w QThread (UI nie może się zamrażać!)

```python
class Worker(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def run(self):
        try:
            for i in range(100):
                # długa operacja
                import time; time.sleep(0.05)
                self.progress.emit(i + 1)
            self.finished.emit('Gotowe!')
        except Exception as e:
            self.error.emit(str(e))

# W MainWindow:
self.worker = Worker()
self.worker.progress.connect(self.progress_bar.setValue)
self.worker.finished.connect(self.on_finished)
self.worker.start()
```

### PySide6 – stylowanie (QSS = CSS dla Qt)

```python
app.setStyleSheet("""
    QMainWindow { background-color: #1e1e1e; }
    QPushButton {
        background-color: #0078d4;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-size: 14px;
    }
    QPushButton:hover { background-color: #106ebe; }
    QPushButton:pressed { background-color: #005a9e; }
    QLabel { color: #ffffff; font-size: 16px; }
    QLineEdit {
        background-color: #2d2d2d;
        color: white;
        border: 1px solid #555;
        padding: 6px;
        border-radius: 4px;
    }
""")
```

## CustomTkinter – tkinter z nowoczesnym wyglądem

Kiedy używać: szybkie narzędzia, prosty GUI, nie chcesz dużych zależności, dark mode out of the box.
Nie używać gdy: potrzebujesz zaawansowanych widgetów (tabele, drzewa, grafika), profesjonalnego UI.

```bash
pip install customtkinter
```

```python
import customtkinter as ctk

ctk.set_appearance_mode('dark')        # dark / light / system
ctk.set_default_color_theme('blue')    # blue / green / dark-blue

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Aplikacja')
        self.geometry('600x400')

        self.label = ctk.CTkLabel(self, text='Witaj!', font=('Helvetica', 20))
        self.label.pack(pady=20)

        self.entry = ctk.CTkEntry(self, placeholder_text='Wpisz tekst...')
        self.entry.pack(pady=10)

        self.btn = ctk.CTkButton(self, text='Kliknij', command=self.on_click)
        self.btn.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(pady=10)
        self.progress.set(0.5)

    def on_click(self):
        self.label.configure(text=self.entry.get())

app = App()
app.mainloop()
```

## Flet – Flutter dla Pythona (web + desktop + mobile)

Kiedy używać: chcesz jedną bazę kodu dla web i desktop, nowoczesny Material Design, reactive UI.
Nie używać gdy: potrzebujesz dostępu do systemu plików offline, zaawansowanej grafiki.

```bash
pip install flet
```

```python
import flet as ft

def main(page: ft.Page):
    page.title = 'Aplikacja Flet'
    page.theme_mode = ft.ThemeMode.DARK

    def on_click(e):
        name_field.value = ''
        hello.value = f'Cześć, {name.value}!'
        page.update()

    name = ft.TextField(label='Twoje imię', autofocus=True)
    hello = ft.Text()
    btn = ft.ElevatedButton('Powitaj', on_click=on_click)

    page.add(name, btn, hello)

ft.app(target=main)               # desktop
ft.app(target=main, view=ft.AppView.WEB_BROWSER)  # web (port 8550)
```

## NiceGUI – aplikacje web jako Python

Kiedy używać: narzędzia wewnętrzne, dashboardy, prototypy dostępne przez przeglądarkę, chcesz HTML/CSS/JS bez ich pisania.

```bash
pip install nicegui
```

```python
from nicegui import ui

with ui.card():
    ui.label('Dashboard').classes('text-2xl font-bold')

    with ui.row():
        value = ui.number('Wartość', value=50, min=0, max=100)
        ui.slider(min=0, max=100).bind_value(value, 'value')

    @ui.refreshable
    def stats():
        ui.label(f'Aktualna wartość: {value.value}')

    ui.button('Odśwież', on_click=stats.refresh)

ui.run(port=8080, title='Moje narzędzie')
```

## pywebview – aplikacja webowa jako okno desktopowe

Kiedy używać: masz frontend HTML/CSS/JS (React, Vue, itp.) i chcesz zapakować jako aplikację desktopową. Backend Python, frontend web.

```bash
pip install pywebview
```

```python
import webview

def get_data():
    return {'items': [1, 2, 3]}

# Eksponuj funkcje Python do JS
class Api:
    def get_user(self):
        return {'name': 'Jan'}

    def save_file(self, content):
        with open('wynik.txt', 'w') as f:
            f.write(content)
        return True

api = Api()
window = webview.create_window(
    'Moja Aplikacja',
    'http://localhost:3000',  # lub ścieżka do pliku HTML
    js_api=api,
    width=1200,
    height=800
)
webview.start()

# W JavaScript: window.pywebview.api.get_user().then(u => console.log(u))
```

## Kivy – cross-platform (Android, iOS, Desktop)

Kiedy używać: chcesz natywną aplikację mobilną z Pythona, touch UI, OpenGL ES.
Nie używać gdy: zwykła aplikacja desktopowa (PySide6 lepszy), widget standardowe Qt są bogatsze.

```bash
pip install kivy
```

```python
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

class MainLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.label = Label(text='Witaj Kivy!', font_size=30)
        btn = Button(text='Kliknij', size_hint=(1, 0.2))
        btn.bind(on_press=self.on_press)
        self.add_widget(self.label)
        self.add_widget(btn)

    def on_press(self, instance):
        self.label.text = 'Kliknięto!'

class MyApp(App):
    def build(self):
        return MainLayout()

MyApp().run()
```

## GUI w Terminalu (TUI)

### Textual
Nowoczesny framework TUI. Komponenty, CSS, reactive. Najlepszy wybór dla nowych TUI.
```bash
pip install textual
```

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static, Input
from textual.containers import Container

class MyTUI(App):
    CSS = """
    Container { align: center middle; }
    Button { margin: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Static('Witaj w TUI!', id='output')
            yield Input(placeholder='Wpisz coś...', id='input')
            yield Button('Wyślij', variant='primary', id='send')
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        inp = self.query_one('#input', Input)
        self.query_one('#output', Static).update(inp.value)

app = MyTUI()
app.run()
```

### Rich (tylko wyświetlanie, nie interaktywny)
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()
console.print(Panel('[bold green]Sukces[/bold green]', title='Status'))

table = Table(show_header=True)
table.add_column('Nazwa', style='cyan')
table.add_column('Status', style='green')
table.add_row('Zadanie 1', 'OK')
console.print(table)
```

### curses (wbudowana, niskopoziomowa)
```python
import curses
def main(stdscr):
    curses.curs_set(0)
    stdscr.addstr(0, 0, 'Witaj w curses!', curses.A_BOLD)
    stdscr.getch()
curses.wrapper(main)
```

## Porównanie GUI – szybki wybór

Profesjonalna aplikacja desktopowa → PySide6
Szybkie narzędzie z dark mode → CustomTkinter
Narzędzie przez przeglądarkę / dashboard → NiceGUI lub Flet
Aplikacja mobilna (Android/iOS) → Kivy
Frontend web + Python backend jako .exe → pywebview
TUI (terminal) pełna interaktywność → Textual
TUI (terminal) tylko wyświetlanie → Rich

NIE UŻYWAJ: PyQt6 w zamkniętych projektach (licencja komercyjna = płatna)
NIE UŻYWAJ: tkinter w nowych projektach jeśli chcesz nowoczesny wygląd (użyj CustomTkinter)
NIE UŻYWAJ: wxPython, PyGTK w nowych projektach (stare, słabe wsparcie)
