"""
Fake Game Status (Windows) - واجهة رسومية
------------------------------------------
يجعل ديسكورد يظن أنك تلعب لعبة تختارها، مع:
  - بحث في قائمة ألعاب ديسكورد (أكثر من 24 ألف لعبة)
  - اسم مخصص لأي لعبة غير موجودة
  - قائمة ألعاب خاصة بك تتبدّل تلقائياً كل مدة تحددها
  - وضع عشوائي يختار الألعاب من تلقاء نفسه

التشغيل كسكريبت:  انقر مرتين على الملف (يحتاج بايثون)
التحويل إلى exe:  شغّل build_exe.bat
"""

import ctypes
import difflib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

APP_NAME = "Fake Game Status"
DETECTABLE_URL = "https://discord.com/api/v9/applications/detectable"
FROZEN = getattr(sys, "frozen", False)
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "FakeGameStatus"
BIN_DIR = DATA_DIR / "bin"
CACHE = DATA_DIR / "detectable_cache.json"
SETTINGS = DATA_DIR / "settings.json"
CHILD_LOG = DATA_DIR / "child_error.txt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ================= العملية الوهمية (نافذة اللعبة) =================
def pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not h:
        return False
    alive = k32.WaitForSingleObject(h, 0) == 0x102  # WAIT_TIMEOUT
    k32.CloseHandle(h)
    return alive


def child_main(title: str, parent_pid: int, log: str):
    """نافذة صغيرة باسم اللعبة؛ ديسكورد لا يكتشف إلا البرامج التي لها نافذة."""
    try:
        root = tk.Tk()
        root.title(title)
        root.geometry("320x100")
        root.resizable(False, False)
        tk.Label(root, text="Playing: " + title, font=("Segoe UI", 11, "bold")).pack(pady=(16, 4))
        tk.Label(root, text="Controlled by Fake Game Status.\nYou can minimize this window.",
                 fg="gray").pack()

        def watch():  # تُغلق تلقائياً إذا أُغلق البرنامج الرئيسي
            if not pid_alive(parent_pid):
                root.destroy()
                return
            root.after(2000, watch)

        watch()
        root.mainloop()
    except Exception:
        Path(log).write_text(traceback.format_exc(), encoding="utf-8")
        raise


def safe_rel_path(exe_rel: str) -> list:
    rel = exe_rel.replace(">", "").replace("\\", "/")
    parts = [re.sub(r'[:*?"<>|]', "", p) for p in rel.split("/")]
    parts = [p for p in parts if p not in ("", ".", "..")]
    if not parts:
        parts = ["CustomGame.exe"]
    if not parts[-1].lower().endswith(".exe"):
        parts[-1] += ".exe"
    return parts


def make_fake_exe(exe_rel: str) -> Path:
    target = BIN_DIR.joinpath(*safe_rel_path(exe_rel))
    target.parent.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        # نسخة من البرنامج نفسه باسم exe اللعبة
        src = Path(sys.executable)
        if not target.exists() or target.stat().st_size != src.stat().st_size:
            shutil.copy2(src, target)
    else:
        base = Path(sys.base_prefix)
        src = base / "pythonw.exe"
        if not src.exists():
            src = Path(sys.executable)
        if not target.exists():
            shutil.copy2(src, target)
            for dll in base.glob("*.dll"):
                dest = target.parent / dll.name
                if not dest.exists():
                    shutil.copy2(dll, dest)
    return target


def child_env() -> dict:
    env = dict(os.environ)
    if FROZEN:
        # حتى تعمل النسخة المنسوخة كبرنامج مستقل (PyInstaller)
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for k in ("_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE",
                  "_PYI_PARENT_PROCESS_LEVEL", "_PYI_SPLASH_IPC"):
            env.pop(k, None)
        return env
    base = Path(sys.base_prefix)
    env["PYTHONHOME"] = str(base)
    for var, pat, marker in (("TCL_LIBRARY", "tcl8*", "init.tcl"), ("TK_LIBRARY", "tk8*", "tk.tcl")):
        found = [p for p in sorted((base / "tcl").glob(pat)) if (p / marker).exists()]
        if found:
            env[var] = str(found[-1])
    return env


def child_cmd(exe: Path, title: str) -> list:
    args = ["--child", title, str(os.getpid()), str(CHILD_LOG)]
    if FROZEN:
        return [str(exe)] + args
    return [str(exe), str(Path(__file__).resolve())] + args


def kill_tree(proc):
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, creationflags=NO_WINDOW)
        else:
            proc.terminate()


# ================= قائمة ألعاب ديسكورد =================
def norm(text: str) -> str:
    t = " " + text.lower() + " "
    t = t.replace(" iii ", " 3 ").replace(" ii ", " 2 ")
    return re.sub(r"[^a-z0-9]", "", t)


def win_exes(g: dict) -> list:
    return [e["name"] for e in g.get("executables") or []
            if e.get("os") in ("win32", None) and not e.get("is_launcher")
            and e.get("name", "").lower().endswith(".exe")]


def load_games(refresh=False) -> list:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if refresh or not CACHE.exists() or time.time() - CACHE.stat().st_mtime > 86400:
        req = urllib.request.Request(DETECTABLE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            CACHE.write_bytes(r.read())
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    games = []
    for g in raw:
        exes = win_exes(g)
        if exes and g.get("name"):
            names = [g["name"]] + list(g.get("aliases") or [])
            games.append({"name": g["name"], "exe": exes[0], "keys": [norm(n) for n in names],
                          "acr": [a for a in {acronym(n) for n in names} if a]})
    return games


def acronym(name: str) -> str:
    """Grand Theft Auto V -> gtav (لتعمل اختصارات مثل GTA V)"""
    words = re.findall(r"[a-z0-9]+", name.lower())
    if len(words) < 2:
        return ""
    return "".join(w if w.isdigit() or w in ("ii", "iii", "iv", "v", "vi") else w[0] for w in words)


def search(games: list, query: str) -> list:
    q = norm(query)
    if not q:
        return []
    words = [norm(w) for w in query.split() if norm(w)]
    exact, partial = [], []
    for g in games:
        acr = g.get("acr", []) if len(q) >= 3 else []
        if q in g["keys"] or q in acr:
            exact.append(g)
        elif (any(q in k for k in g["keys"]) or any(a.startswith(q) for a in acr)
              or all(any(w in k for k in g["keys"]) for w in words)):
            partial.append(g)
    # الأسماء التي تبدأ بالنص أولاً ثم الأقصر
    partial.sort(key=lambda g: (not any(k.startswith(q) for k in g["keys"] + g.get("acr", [])),
                                len(g["name"])))
    res = exact + partial
    if not res:
        index = {}
        for g in games:
            for k in g["keys"]:
                index.setdefault(k, g)
        for k in difflib.get_close_matches(q, index.keys(), n=15, cutoff=0.6):
            if index[k] not in res:
                res.append(index[k])
    return res[:200]


# ================= الواجهة =================
class App:
    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("560x640")
        self.root.minsize(520, 600)

        self.games, self.results = [], []
        self.loading = None          # نتيجة تحميل القائمة من الخيط
        self.proc = None
        self.current = None
        self.started = 0.0
        self.rotating = False
        self.next_at = 0.0
        self.rot_index = -1

        s = self.load_settings()
        self.my_list = s.get("my_list", [])            # [{"name":..., "exe":...}]
        self.mode = tk.StringVar(value=s.get("mode", "list"))
        self.interval = tk.StringVar(value=str(s.get("interval", 10)))
        self.shuffle = tk.BooleanVar(value=s.get("shuffle", False))

        self.build_ui()
        self.refresh_my_list()
        self.start_loading(False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tick()

    # ---------- إعدادات ----------
    def load_settings(self) -> dict:
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}

    def save_settings(self):
        try:
            SETTINGS.write_text(json.dumps({
                "my_list": self.my_list, "mode": self.mode.get(),
                "interval": self.get_interval(), "shuffle": self.shuffle.get(),
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def get_interval(self) -> float:
        try:
            v = max(1.0, float(self.interval.get()))
            return int(v) if v.is_integer() else v
        except ValueError:
            return 10

    # ---------- بناء الواجهة ----------
    def build_ui(self):
        pad = {"padx": 10, "pady": 4}
        top = ttk.LabelFrame(self.root, text=" Search Discord's game list ")
        top.pack(fill="both", expand=True, **pad)

        row = ttk.Frame(top)
        row.pack(fill="x", padx=6, pady=6)
        self.q = tk.StringVar()
        ent = ttk.Entry(row, textvariable=self.q)
        ent.pack(side="left", fill="x", expand=True)
        ent.bind("<Return>", lambda e: self.do_search())
        ttk.Button(row, text="Search", command=self.do_search).pack(side="left", padx=4)
        ttk.Button(row, text="Refresh list", command=lambda: self.start_loading(True)).pack(side="left")

        self.info = ttk.Label(top, text="Loading game list...", foreground="gray")
        self.info.pack(anchor="w", padx=6)

        self.res_box = self.listbox(top, 8)
        self.res_box.bind("<Double-Button-1>", lambda e: self.play_selected())

        btns = ttk.Frame(top)
        btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="Play now", command=self.play_selected).pack(side="left")
        ttk.Button(btns, text="Add to my list", command=self.add_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="Custom name...", command=self.custom_game).pack(side="left")

        mid = ttk.LabelFrame(self.root, text=" My games (for rotation) ")
        mid.pack(fill="both", expand=True, **pad)
        self.my_box = self.listbox(mid, 6)
        self.my_box.bind("<Double-Button-1>", lambda e: self.play_from_my_list())
        b2 = ttk.Frame(mid)
        b2.pack(fill="x", padx=6, pady=6)
        ttk.Button(b2, text="Play now", command=self.play_from_my_list).pack(side="left")
        ttk.Button(b2, text="Remove", command=self.remove_selected).pack(side="left", padx=4)
        ttk.Button(b2, text="Clear", command=self.clear_list).pack(side="left")

        auto = ttk.LabelFrame(self.root, text=" Auto change ")
        auto.pack(fill="x", **pad)
        r1 = ttk.Frame(auto)
        r1.pack(fill="x", padx=6, pady=4)
        ttk.Radiobutton(r1, text="Rotate my list", variable=self.mode, value="list").pack(side="left")
        ttk.Radiobutton(r1, text="Random games (automatic)", variable=self.mode,
                        value="random").pack(side="left", padx=12)
        r2 = ttk.Frame(auto)
        r2.pack(fill="x", padx=6, pady=4)
        ttk.Label(r2, text="Change every").pack(side="left")
        ttk.Spinbox(r2, from_=1, to=1440, width=6, textvariable=self.interval).pack(side="left", padx=4)
        ttk.Label(r2, text="minutes").pack(side="left")
        ttk.Checkbutton(r2, text="Shuffle", variable=self.shuffle).pack(side="left", padx=14)
        ttk.Button(r2, text="Start auto", command=self.start_rotation).pack(side="right")

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=(4, 10))
        self.status = ttk.Label(bottom, text="Not playing", font=("Segoe UI", 10, "bold"))
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Stop", command=self.stop_all).pack(side="right")

    def listbox(self, parent, height):
        f = ttk.Frame(parent)
        f.pack(fill="both", expand=True, padx=6)
        lb = tk.Listbox(f, height=height, activestyle="none")
        sb = ttk.Scrollbar(f, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return lb

    # ---------- تحميل القائمة ----------
    def start_loading(self, refresh):
        self.info.config(text="Loading game list from Discord...")

        def work():
            try:
                self.loading = ("ok", load_games(refresh))
            except Exception as e:
                self.loading = ("err", str(e))

        threading.Thread(target=work, daemon=True).start()

    def finish_loading(self):
        kind, val = self.loading
        self.loading = None
        if kind == "ok":
            self.games = val
            self.info.config(text=f"{len(val)} games loaded. Type a name and press Search.")
        else:
            self.info.config(text=f"Could not load list ({val}). Custom names still work.")

    # ---------- البحث والقائمة ----------
    def do_search(self):
        if not self.games:
            return messagebox.showinfo(APP_NAME, "The game list is not loaded yet.")
        self.results = search(self.games, self.q.get())
        self.res_box.delete(0, "end")
        for g in self.results:
            self.res_box.insert("end", f"{g['name']}    ({g['exe']})")
        if self.results:
            self.res_box.selection_set(0)
            self.info.config(text=f"{len(self.results)} result(s).")
        else:
            self.info.config(text="Not in Discord's list. Use 'Custom name...' instead.")

    def selected_result(self):
        sel = self.res_box.curselection()
        if not sel:
            messagebox.showinfo(APP_NAME, "Select a game from the results first.")
            return None
        g = self.results[sel[0]]
        return {"name": g["name"], "exe": g["exe"]}

    def refresh_my_list(self):
        self.my_box.delete(0, "end")
        for g in self.my_list:
            tag = "  [custom]" if g.get("custom") else ""
            self.my_box.insert("end", g["name"] + tag)

    def add_to_list(self, g):
        if any(x["name"] == g["name"] for x in self.my_list):
            return
        self.my_list.append(g)
        self.refresh_my_list()
        self.save_settings()

    def add_selected(self):
        g = self.selected_result()
        if g:
            self.add_to_list(g)

    def remove_selected(self):
        sel = self.my_box.curselection()
        if sel:
            del self.my_list[sel[0]]
            self.refresh_my_list()
            self.save_settings()

    def clear_list(self):
        if self.my_list and messagebox.askyesno(APP_NAME, "Clear your whole list?"):
            self.my_list = []
            self.refresh_my_list()
            self.save_settings()

    def custom_game(self):
        name = simpledialog.askstring(APP_NAME, "Game name (any text):", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        exe = re.sub(r'[\\/:*?"<>|]', "", name).strip() or "CustomGame"
        g = {"name": name, "exe": exe + ".exe", "custom": True}
        if messagebox.askyesno(APP_NAME, "Also add it to your list for rotation?"):
            self.add_to_list(g)
        self.play(g)
        messagebox.showinfo(APP_NAME,
            "Custom game - first time only:\n\n"
            "Discord > User Settings > Registered Games > 'Add it!'\n"
            f"Pick '{g['exe']}', then click its name and rename it to:\n{name}\n\n"
            "Discord remembers it after that.")

    # ---------- التشغيل ----------
    def play(self, g, rotation=False):
        self.stop_proc()
        if not rotation:
            self.rotating = False
        try:
            exe = make_fake_exe(g["exe"])
            CHILD_LOG.unlink(missing_ok=True)
            self.proc = subprocess.Popen(child_cmd(exe, g["name"]), env=child_env())
        except Exception as e:
            self.rotating = False
            messagebox.showerror(APP_NAME, f"Could not start the fake game:\n{e}")
            return
        self.current = g["name"]
        self.started = time.time()

    def play_selected(self):
        g = self.selected_result()
        if g:
            self.play(g)

    def play_from_my_list(self):
        sel = self.my_box.curselection()
        if sel:
            self.play(self.my_list[sel[0]])

    def start_rotation(self):
        if self.mode.get() == "list" and not self.my_list:
            return messagebox.showinfo(APP_NAME, "Add some games to your list first.")
        if self.mode.get() == "random" and not self.games:
            return messagebox.showinfo(APP_NAME, "The game list is not loaded yet.")
        self.save_settings()
        self.rotating = True
        self.rot_index = -1
        self.next_game()

    def next_game(self):
        if self.mode.get() == "random":
            g = random.choice(self.games)
            g = {"name": g["name"], "exe": g["exe"]}
        else:
            n = len(self.my_list)
            if n == 0:
                return self.stop_all()
            if self.shuffle.get() and n > 1:
                choices = [i for i in range(n) if i != self.rot_index]
                self.rot_index = random.choice(choices)
            else:
                self.rot_index = (self.rot_index + 1) % n
            g = self.my_list[self.rot_index]
        self.play(g, rotation=True)
        self.next_at = time.time() + self.get_interval() * 60

    def stop_proc(self):
        kill_tree(self.proc)
        self.proc = None
        self.current = None

    def stop_all(self):
        self.rotating = False
        self.stop_proc()

    # ---------- التحديث كل ثانية ----------
    def tick(self):
        if self.loading:
            self.finish_loading()

        if self.proc and self.proc.poll() is not None:   # أُغلقت نافذة اللعبة
            quick = time.time() - self.started < 6
            self.proc, self.current = None, None
            if quick:
                self.rotating = False
                err = CHILD_LOG.read_text(encoding="utf-8") if CHILD_LOG.exists() else "(no details)"
                messagebox.showerror(APP_NAME, f"The fake game window failed to start:\n\n{err[-1500:]}")
            elif self.rotating:
                self.next_game()

        if self.rotating and self.current and time.time() >= self.next_at:
            self.next_game()

        if self.current:
            m, s = divmod(int(time.time() - self.started), 60)
            text = f"Playing: {self.current}   ({m}:{s:02d})"
            if self.rotating:
                left = max(0, int(self.next_at - time.time()))
                text += f"   next in {left // 60}:{left % 60:02d}"
        else:
            text = "Not playing"
        self.status.config(text=text)
        self.root.after(1000, self.tick)

    def on_close(self):
        self.save_settings()
        self.stop_all()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--child":
        child_main(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        App().run()
