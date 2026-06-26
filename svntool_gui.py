#!/usr/bin/env python3
"""SVN 工具箱 — Tkinter GUI 版"""
import sys, os, subprocess, threading, queue
from datetime import datetime

if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
    app_bundle = os.path.dirname(app_path)
    app_bundle = os.path.dirname(app_bundle)
    script_dir = os.path.dirname(app_bundle)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def find_svn():
    paths = ["/usr/bin/svn", "/opt/homebrew/bin/svn", "/usr/local/bin/svn", "svn"]
    for p in paths:
        try:
            result = subprocess.run([p, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return p
        except Exception:
            continue
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "缺少依赖",
        "⚠️ 未检测到 svn 命令行工具\n\n建议通过 Homebrew 安装：\n\n   brew install svn",
        parent=root
    )
    root.destroy()
    sys.exit(1)

SVN_BIN = find_svn()
SVN_ENV = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}

ST_MAP = {
    "?": "未版本控制", "M": "已修改", "!": "缺失",
    "A": "已添加", "D": "已删除", "C": "冲突",
    "~": "类型变更", "L": "锁定", "X": "外部引用",
}

def translate_st(code):
    if not code:
        return ""
    parts = [ST_MAP.get(ch, ch) for ch in code]
    return "+".join(parts)

def parse_st(raw):
    items = []
    for line in raw.split("\n"):
        line = line.rstrip()
        if not line:
            continue
        if len(line) >= 8:
            st = line[0:7].rstrip()
            fp = line[7:].strip()
        else:
            st = ""
            fp = line.strip()
        if fp:
            items.append((st, fp))
    return items

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

def scan_repos(root_dir):
    repos = []
    if os.path.exists(os.path.join(root_dir, ".svn")):
        repos.append((os.path.basename(root_dir), root_dir))
    for dirpath, dirnames, _ in os.walk(root_dir):
        depth = dirpath[len(root_dir):].count(os.sep)
        if depth >= 3:
            dirnames.clear()
            continue
        if ".svn" in dirnames and dirpath != root_dir:
            dirnames.remove(".svn")
            repos.append((os.path.relpath(dirpath, root_dir) or os.path.basename(dirpath), dirpath))
    repos.sort(key=lambda x: x[0].lower())
    return repos

def wrap_line(prefix, text, max_cols=80):
    """将 prefix + text 按 max_cols 换行，续行用等宽空格缩进"""
    indent = " " * len(prefix)
    first = prefix + text
    if len(first) <= max_cols:
        return [first]
    lines = [first[:max_cols]]
    rest = first[max_cols:]
    while len(rest) > max_cols - len(indent):
        lines.append(indent + rest[:(max_cols - len(indent))])
        rest = rest[(max_cols - len(indent)):]
    if rest:
        lines.append(indent + rest)
    return lines

class SVNRunner:
    def __init__(self):
        self.output_queue = queue.Queue()

    def run_async(self, cmd, cwd, prefix, done_msg="", callback=None):
        self.output_queue.put(("__PREFIX__", prefix))
        def worker():
            try:
                proc = subprocess.Popen(cmd, cwd=cwd, env=SVN_ENV,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                for line in proc.stdout:
                    self.output_queue.put(("line", line))
                proc.wait()
                if proc.stderr:
                    err = proc.stderr.read()
                    if err.strip():
                        self.output_queue.put(("line", f"[stderr] {err}"))
                if done_msg:
                    self.output_queue.put(("line", f"\n{done_msg}\n"))
            except Exception as e:
                self.output_queue.put(("line", f"❌ 执行出错: {e}\n"))
            finally:
                self.output_queue.put(("__DONE__", callback))
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def run_seq(self, cwd, prefix, done_msg, commands, callback=None):
        """顺序执行多个命令（popen + 实时输出）"""
        self.output_queue.put(("__PREFIX__", prefix))
        def worker():
            for label, cmd in commands:
                self.output_queue.put(("line", f"{label}\n"))
                try:
                    proc = subprocess.Popen(cmd, cwd=cwd, env=SVN_ENV,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                    for line in proc.stdout:
                        self.output_queue.put(("line", line))
                    proc.wait()
                    if proc.stderr:
                        err = proc.stderr.read()
                        if err.strip():
                            self.output_queue.put(("line", f"[stderr] {err}"))
                except Exception as e:
                    self.output_queue.put(("line", f"❌ 执行出错: {e}\n"))
            if done_msg:
                self.output_queue.put(("line", f"\n{done_msg}\n"))
            self.output_queue.put(("__DONE__", callback))
        t = threading.Thread(target=worker, daemon=True)
        t.start()

class SVNToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SVN 工具箱")
        self.root.resizable(True, True)
        self.root.minsize(900, 600)

        self.svn = SVNRunner()
        self.repos = []
        self.current_repo = None
        self._first_block = True

        self.build_ui()
        self.poll_output()
        self.center_and_top()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._insert_text("SVN仓库列表中……\n")
        threading.Thread(target=self._init_repos, daemon=True).start()

    # ----- 键盘 -----
    def _key_repo_up(self):
        if not self.repos:
            return
        sel = self.repo_listbox.curselection()
        idx = sel[0] - 1 if sel else len(self.repos) - 1
        if idx >= 0:
            self.repo_listbox.selection_clear(0, 'end')
            self.repo_listbox.selection_set(idx)
            self.repo_listbox.activate(idx)
            self.repo_listbox.see(idx)
            self.on_repo_select()

    def _key_repo_down(self):
        if not self.repos:
            return
        sel = self.repo_listbox.curselection()
        idx = sel[0] + 1 if sel else 0
        if idx < len(self.repos):
            self.repo_listbox.selection_clear(0, 'end')
            self.repo_listbox.selection_set(idx)
            self.repo_listbox.activate(idx)
            self.repo_listbox.see(idx)
            self.on_repo_select()

    def _key_enter(self):
        w = self.root.focus_get()
        if w and isinstance(w, ttk.Button) and w.instate(['!disabled']):
            w.invoke()

    # ----- 窗口 -----
    def _init_repos(self):
        self.repos = scan_repos(script_dir)
        self.root.after(0, self._on_repos_loaded)

    def _on_repos_loaded(self):
        self.clear_output()
        if self.repos:
            self.populate_repos()
        else:
            self._insert_text("当前目录及子目录中未发现 SVN 工作副本。\n")

    def on_close(self):
        if messagebox.askyesno("退出", "确认退出 SVN 工具箱？", parent=self.root):
            self.root.destroy()

    def center_and_top(self):
        w, h = 900, 600
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes('-topmost', True)
        self.root.after(500, lambda: self.root.attributes('-topmost', False))

    def _make_dlg(self, title, width=900):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        dlg.geometry(f"{width}x600+{x}+{y}")
        return dlg

    # ----- UI -----
    def build_ui(self):
        self.root.bind("<Up>", lambda e: self._key_repo_up())
        self.root.bind("<Down>", lambda e: self._key_repo_down())
        self.root.bind("<Return>", lambda e: self._key_enter())
        self.root.bind("<Escape>", lambda e: self.root.focus_set())

        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        # 左侧仓库列表
        left_frame = ttk.LabelFrame(self.paned, text="仓库列表", padding=4, width=180)
        self.paned.add(left_frame, weight=0)
        self.repo_listbox = tk.Listbox(left_frame, exportselection=False, font=("Menlo", 11))
        self.repo_listbox.pack(fill=tk.BOTH, expand=True)
        self.repo_listbox.bind("<<ListboxSelect>>", self.on_repo_select)

        # 右侧
        right_container = ttk.Frame(self.paned)
        self.paned.add(right_container, weight=3)

        # 输出面板
        right_frame = ttk.LabelFrame(right_container, text="输出面板", padding=4)
        right_frame.pack(fill=tk.BOTH, expand=True)

        # Text（无换行，仅垂直滚动条隐藏）
        text_container = tk.Frame(right_frame)
        text_container.pack(fill=tk.BOTH, expand=True)
        self.output_text = tk.Text(
            text_container, wrap=tk.NONE, font=("Menlo", 11),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            state='disabled')
        v_scroll = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=v_scroll.set)
        self.output_text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        v_scroll.grid_remove()
        text_container.columnconfigure(0, weight=1)
        text_container.rowconfigure(0, weight=1)

        # 底部按钮栏
        btn_frame = ttk.Frame(right_container, padding=(0, 4, 0, 6))
        btn_frame.pack(fill=tk.X)

        self.btn_refresh = ttk.Button(btn_frame, text="刷新仓库列表", command=self.cmd_refresh)
        self.btn_refresh.pack(side=tk.LEFT)

        btn_right = ttk.Frame(btn_frame)
        btn_right.pack(side=tk.RIGHT)
        buttons = [
            ("提交", self.cmd_commit),
            ("更新", self.cmd_up),
            ("撤销", self.cmd_revert),
            ("解决冲突", self.cmd_resolve),
            ("刷新状态", self.cmd_status),
        ]
        self._svn_btns = []
        for text, cmd in buttons:
            b = ttk.Button(btn_right, text=text, command=cmd)
            b.pack(side=tk.RIGHT, padx=2)
            self._svn_btns.append(b)
        self.set_svn_buttons(tk.DISABLED)

    def set_svn_buttons(self, state):
        for b in self._svn_btns:
            if self.current_repo:
                b.configure(state=state)

    # ----- 仓库 -----
    def populate_repos(self):
        self.repo_listbox.delete(0, tk.END)
        for name, _ in self.repos:
            self.repo_listbox.insert(tk.END, f"📁 {name}")
        if self.repos:
            self.repo_listbox.selection_set(0)
            self.on_repo_select()

    def on_repo_select(self, event=None):
        sel = self.repo_listbox.curselection()
        if sel:
            idx = sel[0]
            name, path = self.repos[idx]
            self.current_repo = path
            self.root.title(f"{name or '当前目录'} — SVN 工具箱")
            for b in self._svn_btns:
                b.configure(state=tk.NORMAL)
            self.clear_output()
            self.output_header(f"仓库切换到：{name or '当前目录'}")
            self._refresh_status()

    # ----- 输出 -----
    def _insert_text(self, text):
        self.output_text.configure(state='normal')
        self.output_text.insert(tk.END, text)
        self.output_text.configure(state='disabled')
        self.output_text.see(tk.END)

    def output_header(self, label, action=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self._first_block:
            self._insert_text("\n")
        else:
            self._first_block = False
        text = f"[{label}] {now}"
        if action:
            text += f" {action}"
        self._insert_text(text + "\n")

    def clear_output(self):
        self.output_text.configure(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state='disabled')
        self._first_block = True

    def poll_output(self):
        try:
            while True:
                msg = self.svn.output_queue.get_nowait()
                msg_type, data = msg
                if msg_type == "__PREFIX__":
                    if data is not None:
                        if isinstance(data, tuple):
                            self.output_header(data[0], data[1])
                        else:
                            self.output_header(data)
                elif msg_type == "__DONE__":
                    self.set_svn_buttons(tk.NORMAL)
                    if data:
                        self.root.after(100, lambda cb=data: cb())
                else:
                    self._insert_text(data)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_output)

    def run_async(self, cmd, label, done_msg="", callback=None):
        if not self.current_repo:
            return
        self.set_svn_buttons(tk.DISABLED)
        self.svn.run_async(cmd, self.current_repo, label, done_msg, callback)

    # ----- SVN 状态 -----
    def _get_st_raw(self):
        result = subprocess.run([SVN_BIN, "st"], cwd=self.current_repo,
                                capture_output=True, text=True, timeout=30, env=SVN_ENV)
        return result.stdout

    def _st_line(self, st, fp):
        """生成一行状态日志"""
        cn = translate_st(st)
        display_cn = cn.ljust(6, '\u3000')
        return f"{st:<6}  {display_cn} {fp}\n"

    def _st_line_compact(self, st, fp):
        """紧凑版状态行（用于弹框内文件名前不加折行前缀）"""
        cn = translate_st(st)
        display_cn = cn.ljust(6, '\u3000')
        return f"{st:<6}  {display_cn} {fp}"

    def _refresh_status(self):
        if not self.current_repo:
            return
        self.output_header("仓库状态", "开始获取仓库状态...")
        self.root.update_idletasks()
        raw = self._get_st_raw()
        if not raw.strip():
            self._insert_text("没有变更的文件。\n")
        else:
            for st, fp in parse_st(raw):
                self._insert_text(self._st_line(st, fp))

    # ----- 刷新状态 -----
    def cmd_status(self):
        self._refresh_status()

    # ----- 更新 -----
    def cmd_up(self):
        if not self.current_repo:
            return
        self.output_header("更新", "开始拉取更新...")
        self.run_async([SVN_BIN, "up"], None, "✅ 更新完毕",
                        callback=lambda: self._refresh_status())

    # ----- 撤销 -----
    def cmd_revert(self):
        if not self.current_repo:
            return
        raw = self._get_st_raw()
        items = parse_st(raw)
        modified = [(st, fp) for st, fp in items if "M" in st]
        if not modified:
            messagebox.showinfo("撤销", "没有可撤销的修改文件。", parent=self.root)
            return

        test_font = tkfont.Font(family="Menlo", size=11)
        max_px = max(test_font.measure(self._st_line_compact(st, fp)) for st, fp in modified)
        dlg_width = max(900, int(max_px) + 80)
        dlg = self._make_dlg("撤销本地修改", width=dlg_width)

        # 全选
        cat_frame = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        cat_frame.pack(fill=tk.X)
        all_var = tk.BooleanVar(value=True)
        file_vars = {}

        def _toggle_all():
            for var in file_vars.values():
                var.set(all_var.get())
        tk.Checkbutton(cat_frame, text="全选", variable=all_var,
                        command=_toggle_all).pack(side=tk.LEFT, padx=2)

        # 文件列表
        list_container = tk.Frame(dlg)
        list_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        list_container.rowconfigure(0, weight=1)
        list_container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(list_container, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#1e1e1e")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for st, fp in modified:
            var = tk.BooleanVar(value=True)
            file_vars[fp] = var
            row = tk.Frame(scroll_frame, bg="#1e1e1e")
            row.pack(fill=tk.X)

            def _file_toggle():
                all_on = all(v.get() for v in file_vars.values())
                all_var.set(all_on)
            ck = tk.Checkbutton(row, variable=var, bg="#1e1e1e", fg="#d4d4d4",
                                selectcolor="#1e1e1e", activebackground="#1e1e1e",
                                activeforeground="#d4d4d4", command=_file_toggle)
            ck.pack(side=tk.LEFT)
            label = tk.Label(row, text=self._st_line_compact(st, fp), fg="#d4d4d4",
                              bg="#1e1e1e", font=("Menlo", 11), anchor="w")
            label.pack(side=tk.LEFT, fill=tk.X)

        # 滚轮
        def _on_mousewheel(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        def _on_list_enter(e):
            dlg.bind("<MouseWheel>", _on_mousewheel)
        def _on_list_leave(e):
            dlg.unbind("<MouseWheel>")
        list_container.bind("<Enter>", _on_list_enter, add="+")
        list_container.bind("<Leave>", _on_list_leave, add="+")

        # 底部按钮
        bottom = ttk.Frame(dlg, padding=(8, 4, 8, 8))
        bottom.pack(fill=tk.X)
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, text="此操作不可恢复！").grid(row=0, column=0, sticky="w")

        btn_inner = ttk.Frame(bottom)
        btn_inner.grid(row=0, column=1, sticky="e")

        def do_revert():
            selected = [fp for fp, var in file_vars.items() if var.get()]
            if not selected:
                messagebox.showinfo("提示", "请选择要撤销的文件。", parent=dlg)
                return
            dlg.destroy()
            commands = [(f"  ↺ svn revert: {fp}", [SVN_BIN, "revert", fp]) for fp in selected]
            self.output_header("撤销修改", "开始撤销修改...")
            self.set_svn_buttons(tk.DISABLED)
            self.svn.run_seq(self.current_repo, None, "✅ 撤销完毕", commands,
                              callback=lambda: self._refresh_status())

        ok_btn = ttk.Button(btn_inner, text="撤销选中 (Enter)", command=do_revert)
        ok_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_inner, text="取消 (Esc)", command=lambda: dlg.destroy()).pack(side=tk.LEFT)

        dlg.bind("<Return>", lambda e: do_revert())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        ok_btn.focus_set()
        self.root.wait_window(dlg)

    # ----- 提交 -----
    def cmd_commit(self):
        if not self.current_repo:
            return
        raw = self._get_st_raw()
        items = parse_st(raw)
        allowed = [it for it in items if "C" not in it[0] and "X" not in it[0]]
        if not allowed:
            messagebox.showinfo("提交", "没有可提交的文件。", parent=self.root)
            return

        # 计算弹框宽度（用像素宽度，中英文字符宽度不同）
        test_font = tkfont.Font(family="Menlo", size=11)
        max_px = max(test_font.measure(self._st_line_compact(st, fp)) for st, fp in allowed)
        dlg_width = max(900, int(max_px) + 80)
        dlg = self._make_dlg("SVN 提交", width=dlg_width)

        # 分类统计
        cats = {}
        for st, fp in allowed:
            for ch in st:
                cats.setdefault(ch, []).append((st, fp))
        cat_order = ["?", "M", "!", "A", "D", "~", "L"]
        cat_vars = {}
        file_vars = {}

        # 顶部分类复选框
        cat_frame = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        cat_frame.pack(fill=tk.X)

        def _toggle_cat(ch):
            v = cat_vars[ch]
            select = v.get()
            for st, fp in cats.get(ch, []):
                file_vars[(st, fp)].set(select)
            _update_all()

        def _toggle_all():
            select = cat_vars["*"].get()
            for ch in cat_order:
                if ch in cat_vars:
                    cat_vars[ch].set(select)
            for key in file_vars:
                file_vars[key].set(select)

        def _update_all():
            all_on = all(v.get() for v in file_vars.values())
            cat_vars["*"].set(all_on)
            for ch in cat_order:
                if ch in cats:
                    items_cat = cats[ch]
                    cat_vars[ch].set(all(v.get() for v in [file_vars[k] for k in items_cat]))

        cat_vars["*"] = tk.BooleanVar(value=True)
        tk.Checkbutton(cat_frame, text="全选", variable=cat_vars["*"],
                        command=_toggle_all).pack(side=tk.LEFT, padx=2)

        for ch in cat_order:
            if ch not in cats:
                continue
            var = tk.BooleanVar(value=True)
            name = ST_MAP.get(ch, ch)
            ck = tk.Checkbutton(cat_frame, text=f"{ch} {name}", variable=var,
                                command=lambda c=ch: _toggle_cat(c))
            ck.pack(side=tk.LEFT, padx=2)
            cat_vars[ch] = var

        # 文件列表
        list_container = tk.Frame(dlg)
        list_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        list_container.rowconfigure(0, weight=1)
        list_container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(list_container, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#1e1e1e")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for st, fp in allowed:
            var = tk.BooleanVar(value=True)
            file_vars[(st, fp)] = var
            row = tk.Frame(scroll_frame, bg="#1e1e1e")
            row.pack(fill=tk.X)

            def _file_toggle():
                _update_all()

            ck = tk.Checkbutton(row, variable=var, bg="#1e1e1e", fg="#d4d4d4",
                                selectcolor="#1e1e1e", activebackground="#1e1e1e",
                                activeforeground="#d4d4d4", command=_file_toggle)
            ck.pack(side=tk.LEFT)
            label = tk.Label(row, text=self._st_line_compact(st, fp), fg="#d4d4d4",
                              bg="#1e1e1e", font=("Menlo", 11), anchor="w")
            label.pack(side=tk.LEFT, fill=tk.X)

        # 鼠标滚轮 — Enter/Leave 方式绑定到 Toplevel
        def _on_list_enter(e):
            dlg.bind("<MouseWheel>", _on_mousewheel)
            dlg.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            dlg.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        def _on_list_leave(e):
            dlg.unbind("<MouseWheel>")
            dlg.unbind("<Button-4>")
            dlg.unbind("<Button-5>")

        def _on_mousewheel(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        list_container.bind("<Enter>", _on_list_enter, add="+")
        list_container.bind("<Leave>", _on_list_leave, add="+")

        # 底部按钮
        bottom = ttk.Frame(dlg, padding=(8, 4, 8, 8))
        bottom.pack(fill=tk.X)

        result = [False]

        def on_commit():
            result[0] = True
            dlg.destroy()

        commit_btn = ttk.Button(bottom, text="提交选中的文件 (Enter)", command=on_commit)
        commit_btn.pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(bottom, text="取消 (Esc)", command=lambda: dlg.destroy()).pack(side=tk.RIGHT, padx=4)

        dlg.bind("<Return>", lambda e: on_commit())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        commit_btn.focus_set()
        self.root.wait_window(dlg)

        if not result[0]:
            return

        selected = [fp for (st, fp), var in file_vars.items() if var.get()]
        if not selected:
            return

        from tkinter import simpledialog
        msg = simpledialog.askstring("备注", "输入提交备注（留空使用时间戳）:", parent=self.root)
        if msg is None:
            return
        if not msg.strip():
            msg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        adds = [fp for (st, fp), var in file_vars.items() if var.get() and "?" in st]
        rms = [fp for (st, fp), var in file_vars.items() if var.get() and "!" in st]

        # 流式：先 add/rm，再 ci
        commands = []
        for fp in adds:
            commands.append((f"  + svn add: {fp}", [SVN_BIN, "add", fp]))
        for fp in rms:
            commands.append((f"  - svn rm: {fp}", [SVN_BIN, "rm", fp]))
        commands.append((f">>> svn ci -m \"{msg}\"", [SVN_BIN, "ci", "-m", msg] + selected))

        self.output_header(f"提交 · {msg}", "开始提交文件...")
        self.set_svn_buttons(tk.DISABLED)
        self.svn.run_seq(self.current_repo, None, "✅ 提交完毕", commands,
                          callback=lambda: self._refresh_status())

    # ----- 解决冲突 -----
    def cmd_resolve(self):
        if not self.current_repo:
            return
        raw = self._get_st_raw()
        items = parse_st(raw)
        conflicts = [(st, fp) for st, fp in items if "C" in st]
        if not conflicts:
            messagebox.showinfo("解决冲突", "没有冲突文件。", parent=self.root)
            return

        test_font = tkfont.Font(family="Menlo", size=11)
        max_px = max(test_font.measure(self._st_line_compact(st, fp)) for st, fp in conflicts)
        dlg_width = max(900, int(max_px) + 80)
        dlg = self._make_dlg("解决冲突", width=dlg_width)

        cat_frame = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        cat_frame.pack(fill=tk.X)
        all_var = tk.BooleanVar(value=True)
        file_vars = {}

        def _toggle_all():
            for var in file_vars.values():
                var.set(all_var.get())
        tk.Checkbutton(cat_frame, text="全选", variable=all_var,
                        command=_toggle_all).pack(side=tk.LEFT, padx=2)

        # 文件列表
        list_container = tk.Frame(dlg)
        list_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        list_container.rowconfigure(0, weight=1)
        list_container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(list_container, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#1e1e1e")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for st, fp in conflicts:
            var = tk.BooleanVar(value=True)
            file_vars[fp] = var
            row = tk.Frame(scroll_frame, bg="#1e1e1e")
            row.pack(fill=tk.X)

            def _file_toggle():
                all_on = all(v.get() for v in file_vars.values())
                all_var.set(all_on)
            ck = tk.Checkbutton(row, variable=var, bg="#1e1e1e", fg="#d4d4d4",
                                selectcolor="#1e1e1e", activebackground="#1e1e1e",
                                activeforeground="#d4d4d4", command=_file_toggle)
            ck.pack(side=tk.LEFT)
            label = tk.Label(row, text=self._st_line_compact(st, fp), fg="#d4d4d4",
                              bg="#1e1e1e", font=("Menlo", 11), anchor="w")
            label.pack(side=tk.LEFT, fill=tk.X)

        # 滚轮 — Enter/Leave
        def _on_list_enter(e):
            dlg.bind("<MouseWheel>", _on_mousewheel)
            dlg.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            dlg.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        def _on_list_leave(e):
            dlg.unbind("<MouseWheel>")
            dlg.unbind("<Button-4>")
            dlg.unbind("<Button-5>")

        def _on_mousewheel(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        list_container.bind("<Enter>", _on_list_enter, add="+")
        list_container.bind("<Leave>", _on_list_leave, add="+")

        # 底部按钮
        bottom = ttk.Frame(dlg, padding=(8, 4, 8, 8))
        bottom.pack(fill=tk.X)

        def do_resolve(mode):
            selected = [fp for fp, var in file_vars.items() if var.get()]
            if not selected:
                messagebox.showinfo("提示", "请选择要解决的冲突文件。", parent=dlg)
                return
            dlg.destroy()
            label = "使用他人版本" if mode == "theirs-full" else "使用自己版本"
            commands = [(f"  ↺ svn resolve {fp}: {label}", [SVN_BIN, "resolve", "--accept", mode, fp]) for fp in selected]
            self.output_header(label, "开始解决冲突...")
            self.set_svn_buttons(tk.DISABLED)
            self.svn.run_seq(self.current_repo, None, "✅ 解决完毕", commands,
                              callback=lambda: self._refresh_status())

        ttk.Button(bottom, text="使用他人版本", command=lambda: do_resolve("theirs-full")).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="使用自己版本", command=lambda: do_resolve("mine-full")).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="取消 (Esc)", command=lambda: dlg.destroy()).pack(side=tk.RIGHT, padx=2)

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        self.root.wait_window(dlg)

    # ----- 刷新 -----
    def cmd_refresh(self):
        self.repos = scan_repos(script_dir)
        self.populate_repos()

if __name__ == "__main__":
    root = tk.Tk()
    app = SVNToolGUI(root)
    root.mainloop()
