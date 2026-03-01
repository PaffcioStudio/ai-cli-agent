import sys
import threading
import time

# ── Rich imports (z graceful fallback na plain ANSI jeśli rich nie zainstalowane) ──
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.syntax import Syntax
    from rich.table import Table
    from rich import box
    from rich.style import Style
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ── Fallback ANSI colors ──
class Colors:
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'
    GRAY    = '\033[90m'


# ── Paleta motywu ──
THEME = {
    "section_border": "bright_cyan",
    "section_title":  "bold bright_cyan",
    "success":        "bold green",
    "warning":        "bold yellow",
    "error":          "bold red",
    "ai_message":     "bold magenta",
    "ai_label":       "bright_magenta",
    "status":         "bright_blue",
    "action_safe":    "green",
    "action_modify":  "yellow",
    "action_danger":  "bold red",
    "action_index":   "bright_white",
    "verbose":        "bright_black",
    "prompt_arrow":   "bold bright_green",
    "dim":            "bright_black",
    "spinner":        "bright_cyan",
}


class UI:
    def __init__(self, quiet=False, verbose=False, config=None):
        self.quiet        = quiet
        self.verbose_mode = verbose
        self.config       = config or {}

        ui_cfg = self.config.get('ui', {})
        self.use_colors          = ui_cfg.get('color_output', True)
        self.use_spinner         = ui_cfg.get('spinner', True)
        self.show_action_summary = ui_cfg.get('show_action_summary', True)
        self.use_rich            = RICH_AVAILABLE and self.use_colors and ui_cfg.get('rich', True)

        if self.use_rich:
            self._console = Console(highlight=False, markup=True)
        else:
            self._console = None

        self.spinner_active = False
        self.spinner_thread = None
        self._live = None

    # ── helpery ──────────────────────────────────────────────────

    def _print(self, msg, color="", end="\n"):
        if not self.quiet:
            if self.use_colors and color:
                print(f"{color}{msg}{Colors.RESET}", end=end)
            else:
                print(msg, end=end)
            sys.stdout.flush()

    def _rprint(self, renderable):
        if not self.quiet and self.use_rich and self._console:
            self._console.print(renderable)

    def _stop_live(self):
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                pass
            self._live = None

    # ── sekcje ───────────────────────────────────────────────────

    def section(self, title: str):
        if self.quiet:
            return
        self._stop_live()
        if self.use_rich:
            self._console.print()
            self._console.print(
                Rule(f"[{THEME['section_title']}]{title}[/]",
                     style=THEME["section_border"])
            )
        else:
            self._print(f"\n{'='*50}", Colors.CYAN)
            self._print(title.upper(), Colors.CYAN + Colors.BOLD)
            self._print(f"{'='*50}", Colors.CYAN)

    def rule(self, title: str = ""):
        if self.quiet:
            return
        self._stop_live()
        if self.use_rich:
            self._rprint(Rule(title, style=THEME["dim"]))
        else:
            self._print(f"  {'─'*46}", Colors.GRAY)

    # ── komunikaty ───────────────────────────────────────────────

    def status(self, msg: str):
        self._stop_live()
        if self.use_rich:
            self._rprint(f"[{THEME['status']}]  → {msg}[/]")
        else:
            self._print(f"[AI] {msg}", Colors.BLUE)

    def success(self, msg: str):
        self._stop_live()
        if self.use_rich:
            self._rprint(f"[{THEME['success']}]  ✓ {msg}[/]")
        else:
            self._print(f"✓ {msg}", Colors.GREEN)

    def warning(self, msg: str):
        self._stop_live()
        if self.use_rich:
            self._rprint(f"[{THEME['warning']}]  ⚠ {msg}[/]")
        else:
            self._print(f"⚠ {msg}", Colors.YELLOW)

    def error(self, msg: str):
        self._stop_live()
        if self.use_rich:
            self._rprint(f"[{THEME['error']}]  ✗ {msg}[/]")
        else:
            self._print(f"✗ {msg}", Colors.RED)

    def ai_message(self, msg: str):
        self._stop_live()
        if self.quiet:
            return
        if self.use_rich:
            self._console.print(
                Panel(
                    f"[{THEME['ai_message']}]{msg}[/]",
                    title=f"[{THEME['ai_label']}]✦ AI[/]",
                    border_style="magenta",
                    padding=(0, 1),
                    expand=False,
                )
            )
        else:
            self._print(f"[AI] {msg}", Colors.MAGENTA)

    # ── podgląd akcji ────────────────────────────────────────────

    def action_preview(self, index: int, description: str):
        self._stop_live()
        if self.quiet:
            return
        if self.use_rich:
            # dobierz kolor wg treści opisu
            if description.startswith("❌") or "delete" in description.lower():
                style = THEME["action_danger"]
            elif description.startswith("🔧") or "patch_file" in description or "edit_file" in description:
                style = "yellow"
            elif description.startswith("⚠") or "🔴" in description:
                style = THEME["action_modify"]
            else:
                style = THEME["action_safe"]

            self._console.print(
                f"  [bold bright_white]{index:>2}.[/] [{style}]{description}[/]"
            )
        else:
            self._print(f"  {index}. {description}", Colors.GRAY)

    # ── spinner ──────────────────────────────────────────────────

    def spinner_start(self, msg: str = "Pracuję..."):
        if self.quiet or not self.use_spinner:
            return
        self._stop_live()

        if self.use_rich:
            spinner_widget = Spinner("dots", text=f"[{THEME['spinner']}]{msg}[/]")
            self._live = Live(
                spinner_widget,
                console=self._console,
                refresh_per_second=12,
                transient=True,
            )
            try:
                self._live.start()
            except Exception:
                self._live = None
        else:
            self.spinner_active = True
            self.spinner_msg = msg

            def _spin():
                frames = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
                i = 0
                while self.spinner_active:
                    f = frames[i % len(frames)]
                    sys.stdout.write(f"\r{Colors.CYAN}{f} {self.spinner_msg}{Colors.RESET}")
                    sys.stdout.flush()
                    time.sleep(0.1)
                    i += 1
                sys.stdout.write("\r" + " " * (len(self.spinner_msg) + 3) + "\r")
                sys.stdout.flush()

            self.spinner_thread = threading.Thread(target=_spin, daemon=True)
            self.spinner_thread.start()

    def spinner_stop(self):
        self._stop_live()
        self.spinner_active = False
        if self.spinner_thread:
            self.spinner_thread.join(timeout=0.5)
            self.spinner_thread = None

    # ── verbose ──────────────────────────────────────────────────

    def verbose(self, msg: str):
        if not self.verbose_mode:
            return
        self._stop_live()
        if self.use_rich:
            self._rprint(f"[{THEME['verbose']}]    {msg}[/]")
        else:
            self._print(f"    {msg}", Colors.GRAY)

    # ── input / potwierdzenia ─────────────────────────────────────

    def confirm_actions(self) -> bool:
        self._stop_live()
        try:
            if self.use_rich:
                self._console.print()
                response = self._console.input(
                    f"[{THEME['warning']}]  Wykonać? \\[T/n]: [/]"
                ).strip().lower()
            else:
                response = input(
                    f"\n{Colors.YELLOW}{Colors.BOLD}Wykonać? [T/n]: {Colors.RESET}"
                ).strip().lower()
            return response in ['', 't', 'tak', 'y', 'yes']
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    def prompt(self, question: str, default=None):
        self._stop_live()
        if default:
            question = f"{question} [{default}]"
        try:
            if self.use_rich:
                response = self._console.input(
                    f"[{THEME['status']}]{question}: [/]"
                ).strip()
            else:
                response = input(
                    f"{Colors.CYAN}{question}: {Colors.RESET}"
                ).strip()
            return response or default
        except (EOFError, KeyboardInterrupt):
            print()
            return default

    # ── diff preview ─────────────────────────────────────────────

    def show_diff_preview(self, file_path: str, old_content: str, new_content: str):
        if not self.config.get('ui', {}).get('show_diff_preview', True):
            return
        if self.quiet:
            return
        self._stop_live()

        if self.use_rich:
            old_lines = old_content.splitlines()
            new_lines = new_content.splitlines()
            table = Table(box=box.MINIMAL, show_header=False, padding=(0, 1))
            table.add_column("ln",  style="bright_black", width=4)
            table.add_column("ch",  width=1)
            table.add_column("content")
            changes = 0
            for i, (old, new) in enumerate(zip(old_lines, new_lines), 1):
                if old != new:
                    if changes >= 10:
                        break
                    table.add_row(str(i), "-", Text(old, style="red strike"))
                    table.add_row("",    "+", Text(new, style="green"))
                    changes += 1
            self._console.print(
                Panel(table,
                      title=f"[bright_cyan]diff: {file_path}[/]",
                      border_style="bright_cyan",
                      padding=(0, 0))
            )
        else:
            print()
            self._print(f"Diff: {file_path}", Colors.CYAN)
            self._print("-" * 50, Colors.GRAY)
            old_lines = old_content.splitlines()
            new_lines = new_content.splitlines()
            changes = 0
            for old, new in zip(old_lines, new_lines):
                if old != new and changes < 10:
                    self._print(f"- {old}", Colors.RED)
                    self._print(f"+ {new}", Colors.GREEN)
                    changes += 1
            self._print("-" * 50, Colors.GRAY)

    # ── extras ───────────────────────────────────────────────────

    def code(self, source: str, language: str = "python"):
        """Wyświetl blok kodu z podświetlaniem składni."""
        self._stop_live()
        if self.quiet:
            return
        if self.use_rich:
            from rich.syntax import Syntax
            syntax = Syntax(source, language,
                            theme="monokai",
                            line_numbers=True,
                            background_color="default")
            self._console.print(Panel(syntax,
                                       border_style="bright_black",
                                       padding=(0, 0)))
        else:
            self._print(source, Colors.WHITE)

    def print_table(self, headers: list, rows: list, title: str = ""):
        """Wyświetl tabelę."""
        self._stop_live()
        if self.quiet:
            return
        if self.use_rich:
            table = Table(*headers,
                           box=box.ROUNDED,
                           border_style="bright_black",
                           header_style=THEME["section_title"],
                           title=title or None,
                           show_lines=False)
            for row in rows:
                table.add_row(*[str(c) for c in row])
            self._console.print(table)
        else:
            if title:
                self._print(title, Colors.CYAN)
            self._print("  ".join(str(h) for h in headers), Colors.BOLD)
            for row in rows:
                self._print("  ".join(str(c) for c in row))
