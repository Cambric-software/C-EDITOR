"""
C EDITOR  v4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Single-window suite with a left sidebar navigator.
All 6 departments live inside one window — no separate Toplevel windows.

Departments (sidebar tabs):
  Documents   · rich-text editor, styles, drawing, templates
  Design      · Canva-style drag-and-drop canvas
  Spreadsheet · Excel-style grid with SUM/AVERAGE formulas
  Slides      · presentation builder + full-screen presenter
  Video       · multi-track timeline editor
  Animation   · 2D frame-by-frame studio

Translation  → Google Translate (free, online, no key needed)
Diacritics   → Harakat online API (no key needed) + manual palette
"""
from __future__ import annotations

import copy, html, json, math, os, re, tempfile, ctypes, threading
import tkinter as tk
from dataclasses import dataclass, asdict, field
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog, font
from tkinter.scrolledtext import ScrolledText
from typing import Optional, List, Dict, Any
from uuid import uuid4
import urllib.request, urllib.parse, urllib.error

# ── Windows DPI ───────────────────────────────────────────────────────────────
if os.name == "nt":
    try:    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass

# ── Paths ─────────────────────────────────────────────────────────────────────
APP      = "C EDITOR"
FORMAT   = "CEditor"
VERSION  = 4
ROOT     = Path(__file__).resolve().parent
ASSETS   = ROOT / "assets"
DATA     = Path.home() / ".c_editor"
RECOVERY = DATA / "recovery"
for _d in (DATA, RECOVERY, DATA/"assets", DATA/"templates"):
    _d.mkdir(exist_ok=True)
SETTINGS_FILE = DATA / "settings.json"

# ── Language / size tables ────────────────────────────────────────────────────
LANGS = ["English","Arabic","French","German","Spanish",
         "Italian","Chinese","Japanese","Korean","Russian","Turkish","Hindi"]

LANG_CODES = {
    "english":"en","arabic":"ar","french":"fr","german":"de",
    "spanish":"es","italian":"it","chinese":"zh-CN","japanese":"ja",
    "korean":"ko","russian":"ru","turkish":"tr","hindi":"hi",
}

PAGE_SIZES: Dict[str,tuple] = {
    "A4":(794,1123),"A5":(559,794),"A3":(1123,1587),
    "Letter":(816,1056),"Legal":(816,1344),
}

TEMPLATES = [
    ("School","Homework Sheet"),("School","Worksheet"),("School","Quiz"),
    ("School","Test"),("School","Answer Sheet"),("School","Revision Sheet"),
    ("School","Study Guide"),("School","Flashcards"),("School","Vocabulary Sheet"),
    ("School","Reading Comprehension"),("School","Math Worksheet"),
    ("School","Science Worksheet"),("School","Arabic Worksheet"),("School","Essay Sheet"),
    ("Documents","Blank Document"),("Documents","Professional Report"),
    ("Documents","Letter"),("Documents","Meeting Notes"),("Documents","Research Notes"),
    ("Documents","Certificate"),("Documents","Resume/CV"),("Documents","Invoice"),
    ("Documents","Form"),("Documents","Project Proposal"),
    ("Planning","Daily Planner"),("Planning","Weekly Planner"),
    ("Planning","Monthly Planner"),("Planning","Timetable"),
    ("Planning","Study Planner"),("Planning","Habit Tracker"),
    ("Creative","Poster"),("Creative","Flyer"),("Creative","Mind Map"),
    ("Creative","Storyboard"),("Creative","Presentation Page"),
    ("Creative","Social Media Post"),("Creative","Newsletter"),
]

def page_size(name:str, landscape:bool=False) -> tuple:
    w,h = PAGE_SIZES.get(name,(794,1123))
    return (h,w) if landscape else (w,h)

def new_id() -> str:
    return str(uuid4())

def shaped(s:str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s

# ══════════════════════════════════════════════════════════════════════════════
#  Colour palette  (used throughout the UI)
# ══════════════════════════════════════════════════════════════════════════════
PALETTE = {
    "bg":        "#F0F4F8",   # window background
    "surface":   "#FFFFFF",   # cards, panels
    "surface2":  "#E8EEF6",   # secondary surface
    "sidebar":   "#1E2D40",   # left sidebar dark
    "sidebar_hl":"#2D4460",   # sidebar hover
    "sidebar_sel":"#315C8A",  # sidebar selected
    "accent":    "#315C8A",   # primary blue
    "accent2":   "#2563EB",   # bright accent
    "danger":    "#DC2626",   # red actions
    "success":   "#16A34A",   # green
    "text":      "#1E293B",   # body text
    "muted":     "#64748B",   # secondary text
    "border":    "#CBD5E1",   # dividers
    "yellow":    "#F59E0B",   # highlights
    # dark mode\n"dark_bg":   "#0F172A",
    "dark_surface":"#1E293B",
    "dark_text": "#F1F5F9",
    "dark_muted":"#94A3B8",
    "dark_border":"#334155",
}

# ══════════════════════════════════════════════════════════════════════════════
#  Data models
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Page:
    id:       str  = field(default_factory=new_id)
    text:     str  = ""
    drawings: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    notes:    str  = ""

@dataclass
class Document:
    title:            str   = "Untitled document"
    content_language: str   = "English"
    page_size:        str   = "A4"
    orientation:      str   = "Portrait"
    margin:           int   = 56
    theme:            str   = "#315C8A"
    header:           str   = ""
    footer:           str   = ""
    page_numbers:     bool  = True
    pages:            list  = field(default_factory=lambda:[Page()])
    styles:           dict  = field(default_factory=lambda:{
    "Normal":   {"font":"Segoe UI","size":12,"color":"#1E293B"},
        "Title":    {"font":"Segoe UI","size":26,"color":"#315C8A","bold":True},
        "Heading 1":{"font":"Segoe UI","size":18,"color":"#315C8A","bold":True},
        "Heading 2":{"font":"Segoe UI","size":14,"color":"#1D4E89","bold":True},
        "Heading 3":{"font":"Segoe UI","size":12,"color":"#1E293B","bold":True},
        "Quote":    {"font":"Segoe UI","size":12,"color":"#64748B","italic":True},
        "Code":     {"font":"Courier New","size":11,"color":"#1a1a1a"},
        "Question": {"font":"Segoe UI","size":13,"color":"#111827","bold":True},
    })
    metadata: dict = field(default_factory=dict)
    def payload(self)->dict:
        return {"format":FORMAT,"version":VERSION,"document":asdict(self)}
    @classmethod
    def load(cls,data:dict)->"Document":
        if data.get("format")!=FORMAT:
            raise ValueError("Not a Homework Document Studio project.")
        raw=data["document"]
        raw["pages"]=[Page(**p) for p in raw.get("pages",[])] or [Page()]
        return cls(**{k:v for k,v in raw.items() if k in cls.__dataclass_fields__})

@dataclass
class DesignObject:
    kind:       str   = "rect"
    x:          float = 100.0
    y:          float = 100.0
    w:          float = 200.0
    h:          float = 100.0
    rotation:   float = 0.0
    fill:       str   = "#315C8A"
    stroke:     str   = ""
    stroke_w:   int   = 2
    opacity:    float = 1.0
    text:       str   = "Text"
    font_fam:   str   = "Segoe UI"
    font_sz:    int   = 22
    font_bold:  bool  = False
    font_it:    bool  = False
    text_color: str   = "#FFFFFF"
    image_path: str   = ""
    locked:     bool  = False
    id:         str   = field(default_factory=new_id)

@dataclass
class DesignPage:
    objects:    List[DesignObject] = field(default_factory=list)
    background: str = "#FFFFFF"
    id:         str = field(default_factory=new_id)

@dataclass
class DesignProject:
    title:  str  = "Untitled Design"
    width:  int  = 1080
    height: int  = 1080
    pages:  List[DesignPage] = field(default_factory=lambda:[DesignPage()])
    def payload(self)->dict:
        return {"format":"HomeworkDesignStudio","version":2,"project":asdict(self)}

# ══════════════════════════════════════════════════════════════════════════════
#  Online helpers  (translation + diacritics)
# ══════════════════════════════════════════════════════════════════════════════

def _google_translate(text:str, target:str, source:str="auto") -> str:
    """
    Free Google Translate endpoint (no API key).
    Tries gtx endpoint first, then lingva as fallback.
    """
    def _chunk(t, n=4500):
        return [t[i:i+n] for i in range(0, len(t), n)]

    last_error = None
    for chunk in _chunk(text):
        # Endpoint 1: Google gtx
        try:
            params = urllib.parse.urlencode({
                "client": "gtx", "sl": source, "tl": target, "dt": "t", "q": chunk
            })
            url = "https://translate.googleapis.com/translate_a/single?" + params
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
            return translated
        except Exception as e:
            last_error = e

        # Endpoint 2: Lingva
        try:
            src2 = source if source != "auto" else "auto"
            url2 = ("https://lingva.ml/api/v1/" + src2 + "/" + target + "/"
                    + urllib.parse.quote(chunk))
            req2 = urllib.request.Request(
                url2, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=12) as r2:
                data2 = json.loads(r2.read().decode("utf-8"))
            return data2.get("translation", "")
        except Exception as e2:
            last_error = e2

    raise RuntimeError(
        "Translation failed.\nLast error: " + str(last_error)
    )


def _harakat_api(text: str) -> str:
    """
    Add Arabic diacritics (tashkeel).

    Backends tried in order:
    1. tashkeel.app  — free, active, well-maintained REST API
    2. mishkal       — offline Python library (pip install mishkal)
    3. Basic rule-based fallback (vowels on common patterns)

    harakat.ae was removed — abandoned project, broken API.
    """
    # Backend 1: tashkeel.app (modern, maintained Arabic NLP API)
    try:
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tashkeel.app/tashkeel",
            data=payload,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8")
        data = json.loads(body)
        result = (data.get("result") or data.get("text")
                  or data.get("tashkeel") or data.get("output"))
        if result and len(result) >= len(text) * 0.8:
            return result
    except Exception:
        pass

    # Backend 2: Arabic-NLP diacritizer (another public endpoint)
    try:
        params = urllib.parse.urlencode({"text": text})
        url = "https://arabic-diacritizer.herokuapp.com/diacritize?" + params
        req2 = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=12) as r2:
            body2 = r2.read().decode("utf-8")
        data2 = json.loads(body2)
        result2 = data2.get("result") or data2.get("text")
        if result2:
            return result2
    except Exception:
        pass

    # Backend 3: mishkal (offline library)
    try:
        from mishkal.tashkeel import TashkeelClass
        return TashkeelClass().tashkeel(text)
    except ImportError:
        pass
    except Exception:
        pass

    # Backend 4: camel-tools (offline, more powerful)
    try:
        from camel_tools.utils.dediac import dediac_ar
        from camel_tools.tagger.default import DefaultTagger
        tagger = DefaultTagger.pretrained()
        return tagger.tag(text.split()).__str__()
    except Exception:
        pass

    raise RuntimeError(
        "Arabic diacritics service unavailable.\n\n"
        "Options:\n"
        "  pip install mishkal       (offline, simple)\n"
        "  pip install camel-tools   (offline, advanced)\n\n"
        "The Manual Marks tab still works without internet.\n"
        "Use it to add individual diacritics by clicking them."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Main application  —  Studio
# ══════════════════════════════════════════════════════════════════════════════

class Studio(tk.Tk):

    # ─────────────────────────────────────────────────────── init ───────────
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry("1600x960")
        self.minsize(1100,700)

        # document state
        self.doc      = Document()
        self.path:    Optional[Path] = None
        self.current  = 0
        self.dirty    = False
        self.history: List[str] = []
        self.future:  List[str] = []
        self.loading  = False

        # design state
        self.design_proj  = DesignProject()
        self.design_page  = 0
        self._sel_obj:    Optional[DesignObject] = None
        self._drag_start: Optional[tuple] = None
        self._drag_orig:  Optional[tuple] = None

        # video / animation project dicts (inline, no Toplevel)
        self._video_project    = self._empty_video()
        self._video_sel_track  = 0
        self._video_sel_clip:  Optional[int] = None
        self._anim_project     = self._empty_anim()
        self._anim_frame       = 0
        self._anim_layer       = 1
        self._anim_playing     = False
        self._anim_color       = "#315C8A"

        # ui vars
        self.zoom       = tk.IntVar(value=80)
        self.status     = tk.StringVar(value="Ready")
        self.page_status= tk.StringVar()
        self.draw_tool  = tk.StringVar(value="Select")
        self.draw_tool.trace_add("write", lambda *_: self._draw_visibility())
        self._draw_color_var = tk.StringVar(value="#315C8A")

        # slides
        self._slides:    List[dict] = [self._empty_slide()]
        self._cur_slide  = 0

        # spreadsheet
        self._sheet_data:Dict[str,dict] = {}
        self._sheet_sel  = (0,0)
        self._ROWS=50; self._COLS=26; self._COL_W=90; self._ROW_H=24; self._HDR=24

        # preferences
        self.preferences = {
        "ui_theme":            "Light",
            "font_scale":          100,
            "autosave_seconds":    45,
            "show_tips":           True,
            "auto_correct":        True,
            "smart_typography":    True,
            "default_language":    "English",
            "presentation_seconds":4,
        }
        self._load_prefs()

        # logo
        try:
            self._logo = tk.PhotoImage(file=str(ASSETS/"studio_logo.png"))
            self.iconphoto(True, self._logo)
        except Exception:
            self._logo = None

        self._apply_theme()
        self._build()
        self._load_page()
        self._snapshot()
        self.after(self.preferences["autosave_seconds"]*1000, self._autosave)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<F1>", lambda e: self._show_shortcuts())
        self.after(800, self._load_plugins)

    # ─────────────────────────────────────────── blank project skeletons ────
    def _empty_video(self)->dict:
        return {
        "title":"Untitled Video","size":"1920x1080","fps":30,
            "tracks":[
                {"id":"v1","kind":"video","name":"Video 1","clips":[],"muted":False,"color":"#2563EB"},
                {"id":"v2","kind":"video","name":"Video 2","clips":[],"muted":False,"color":"#1D4E89"},
                {"id":"a1","kind":"audio","name":"Audio 1","clips":[],"muted":False,"color":"#16A34A"},
                {"id":"a2","kind":"audio","name":"Audio 2","clips":[],"muted":False,"color":"#15803D"},
                {"id":"t1","kind":"title","name":"Titles", "clips":[],"muted":False,"color":"#7C3AED"},
            ],
            "markers":[],"captions":[],
        }
    def _empty_clip(self,path:str)->dict:
        return {"path":path,"start":"0","end":"","offset":0.0,
                "volume":1.0,"opacity":1.0,"speed":1.0,
                "transition":"Cut","muted":False,"label":"","filter":"None",
                "color_grading":{"brightness":0,"contrast":0,"saturation":0}}
    def _empty_anim(self)->dict:
        return {
        "title":"Untitled Animation","width":960,"height":540,"fps":12,
            "total_frames":24,"background":"#FFFFFF",
            "layers":[
                {"id":"bg","name":"Background","visible":True,"locked":False,"opacity":1.0,"frames":{}},
                {"id":"drw","name":"Drawing",   "visible":True,"locked":False,"opacity":1.0,"frames":{}},
                {"id":"fg","name":"Foreground", "visible":True,"locked":False,"opacity":1.0,"frames":{}},
            ],
        }
    def _empty_slide(self)->dict:
        return {"text":"New Slide\n\nAdd your content here.",
                "notes":"","layout":"Title + Content",
                "background":"#1E2D40","accent":"#3B82F6","transition":"Fade"}

    # ───────────────────────────────────────────────── preferences / theme ───
    def _load_prefs(self):
        try:
            saved=json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.preferences.update({k:v for k,v in saved.items() if k in self.preferences})
        except Exception: pass

    def _save_prefs(self):
        SETTINGS_FILE.write_text(json.dumps(self.preferences,indent=2),encoding="utf-8")

    def _apply_theme(self):
        theme = self.preferences["ui_theme"]
        dark = theme == "Dark"
        P    = PALETTE
        self._dark = dark
        if theme == "Dark":
            bg      = "#0F172A"
            surface = "#1E293B"
            surface2= "#273449"
            fg      = "#E2E8F0"
            muted   = "#94A3B8"
            border  = "#334155"
            accent  = "#3B82F6"
        elif theme == "Ocean":
            bg      = "#0D2137"
            surface = "#0F3460"
            surface2= "#16213E"
            fg      = "#E0F4FF"
            muted   = "#7ECBFF"
            border  = "#1A4A7A"
            accent  = "#00B4D8"
            dark    = True
        elif theme == "Sunset":
            bg      = "#1A0A2E"
            surface = "#2D1B4E"
            surface2= "#3D2464"
            fg      = "#FFE4E1"
            muted   = "#FFB3A7"
            border  = "#5C3370"
            accent  = "#FF6B6B"
            dark    = True
        elif theme == "Forest":
            bg      = "#0D1F0D"
            surface = "#1A3320"
            surface2= "#243D2A"
            fg      = "#E8F5E9"
            muted   = "#81C784"
            border  = "#2E5733"
            accent  = "#4CAF50"
            dark    = True
        else:  # Light
            bg      = P["bg"]
            surface = P["surface"]
            surface2= P["surface2"]
            fg      = P["text"]
            muted   = P["muted"]
            border  = P["border"]
            accent  = P["accent"]
        self._bg = bg; self._surface = surface; self._fg = fg
        self.configure(bg=bg)
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure(".",            font=("Segoe UI",10),background=bg,foreground=fg)
        style.configure("TFrame",       background=bg)
        style.configure("TLabel",       background=bg,foreground=fg)
        style.configure("TLabelframe",  background=bg,foreground=fg)
        style.configure("TLabelframe.Label",background=bg,foreground=fg)
        style.configure("TNotebook",    background=bg,borderwidth=0,tabmargins=0)
        style.configure("TNotebook.Tab",padding=(14,8),background=surface,foreground=fg)
        style.map("TNotebook.Tab",
                  background=[("selected",accent)],
                  foreground=[("selected","#FFFFFF")])
        style.configure("TButton",      padding=(10,6),background=surface,
                        foreground=fg,borderwidth=1,relief="flat")
        style.map("TButton",
                  background=[("active",surface2),("pressed",accent)],
                  foreground=[("pressed","#FFFFFF")])
        style.configure("Accent.TButton",background=accent,foreground="#FFFFFF",
                        padding=(12,7),borderwidth=0)
        style.map("Accent.TButton",background=[("active","#2563EB")])
        style.configure("Danger.TButton",background=P["danger"],foreground="#FFFFFF",
                        padding=(10,6),borderwidth=0)
        style.configure("TEntry",       fieldbackground=surface,foreground=fg,
                        borderwidth=1,relief="flat",insertcolor=fg)
        style.configure("TCombobox",    fieldbackground=surface,foreground=fg,
                        borderwidth=1,relief="flat")
        style.map("TCombobox",fieldbackground=[("readonly",surface)],
                  foreground=[("readonly",fg)],selectbackground=[("readonly",accent)])
        style.configure("TSpinbox",     fieldbackground=surface,foreground=fg)
        style.configure("TSeparator",   background=border)
        style.configure("Treeview",     background=surface,foreground=fg,
                        fieldbackground=surface,rowheight=24,borderwidth=0)
        style.configure("Treeview.Heading",background=surface2,
                        foreground=fg,font=("Segoe UI",9,"bold"),relief="flat")
        style.map("Treeview",background=[("selected",accent)],
                  foreground=[("selected","#FFFFFF")])
        style.configure("TScrollbar",   background=border,troughcolor=bg,
                        arrowsize=12,relief="flat",borderwidth=0)
        style.configure("TScale",       background=bg,troughcolor=border)
        style.configure("TCheckbutton", background=bg,foreground=fg)
        style.configure("TRadiobutton", background=bg,foreground=fg)
        scale=max(80,min(140,int(self.preferences["font_scale"])))/100
        try: self.tk.call("tk","scaling",(self.winfo_fpixels("1i")/72)*scale)
        except Exception: pass

    # ─────────────────────────────────────────────────────── BUILD UI ────────
    def _b(self, parent, text, cmd, **kw):
        return ttk.Button(parent, text=text, command=cmd, **kw)

    def _build(self):
        self._menu()

        # ── outer layout: sidebar | content ──────────────────────────────────
        outer = tk.Frame(self, bg=self._bg)
        outer.pack(fill="both",expand=True)

        self._sidebar = tk.Frame(outer, bg=PALETTE["sidebar"], width=200)
        self._sidebar.pack(side="left",fill="y")
        self._sidebar.pack_propagate(False)

        content = tk.Frame(outer, bg=self._bg)
        content.pack(side="left",fill="both",expand=True)

        self._build_sidebar(self._sidebar)

        # ── content = toolbar strip + department notebook ─────────────────────
        self._toolbar_frame = tk.Frame(content, bg=self._bg)
        self._toolbar_frame.pack(fill="x")

        self._dept_nb = ttk.Notebook(content)
        self._dept_nb.pack(fill="both",expand=True,padx=0,pady=0)

        # create frames for all 6 departments
        self._frames:Dict[str,tk.Frame] = {}
        dept_names = ["documents","design","spreadsheet","slides","video","animation","creations"]
        for name in dept_names:
            f = tk.Frame(self._dept_nb, bg=self._bg)
            self._dept_nb.add(f, text="")   # label controlled by sidebar
            self._frames[name] = f

        self._dept_nb.bind("<<NotebookTabChanged>>", self._on_dept_change)

        self._build_documents(self._frames["documents"])
        self._build_design(self._frames["design"])
        self._build_spreadsheet(self._frames["spreadsheet"])
        self._build_slides(self._frames["slides"])
        self._build_video(self._frames["video"])
        self._build_animation(self._frames["animation"])
        self._build_creations(self._frames["creations"])

        # ── status bar ────────────────────────────────────────────────────────
        sb = tk.Frame(self, bg=PALETTE["sidebar"], height=26)
        sb.pack(fill="x",side="bottom")
        sb.pack_propagate(False)
        tk.Label(sb,textvariable=self.status,bg=PALETTE["sidebar"],
                 fg="#94A3B8",font=("Segoe UI",9)).pack(side="left",padx=12)
        # word counter label (right side, updated on keypress)
        self.word_count_var = tk.StringVar(value="")
        tk.Label(sb,textvariable=self.word_count_var,bg=PALETTE["sidebar"],
                 fg="#64748B",font=("Segoe UI",9)).pack(side="right",padx=8)
        tk.Label(sb,textvariable=self.page_status,bg=PALETTE["sidebar"],
                 fg="#94A3B8",font=("Segoe UI",9)).pack(side="right",padx=12)

    # ──────────────────────────────────────────────────── SIDEBAR ────────────
    def _build_sidebar(self, parent:tk.Frame):
        P = PALETTE
        # Logo / app name
        logo_row = tk.Frame(parent, bg=P["sidebar"])
        logo_row.pack(fill="x",padx=0,pady=0)
        if self._logo:
            sm = self._logo.subsample(28,28)
            self._logo_sm = sm
            tk.Label(logo_row,image=sm,bg=P["sidebar"]).pack(
                side="left",padx=(14,6),pady=14)
        tk.Label(logo_row,text="Studio",bg=P["sidebar"],fg="#FFFFFF",
                 font=("Segoe UI",13,"bold")).pack(side="left",pady=14)

        # thin divider
        tk.Frame(parent,bg="#2D4460",height=1).pack(fill="x",padx=12)

        # nav items
        self._nav_items = [
            ("documents",  "📄", "Documents"),
            ("design",     "🎨", "Design Canvas"),
            ("spreadsheet","📊", "Spreadsheet"),
            ("slides",     "🖼", "Slides"),
            ("video",      "🎬", "Video Studio"),
            ("animation",  "🎞", "Animation"),
            ("creations",  "🗂", "Creations"),
        ]
        self._nav_btns:Dict[str,tk.Label] = {}
        self._active_dept = "documents"

        nav_frame = tk.Frame(parent,bg=P["sidebar"])
        nav_frame.pack(fill="x",pady=(8,0))
        for key,icon,label in self._nav_items:
            self._make_nav_btn(nav_frame,key,icon,label)

        # bottom section
        tk.Frame(parent,bg="#2D4460",height=1).pack(fill="x",padx=12,pady=(0,4))
        bottom = tk.Frame(parent,bg=P["sidebar"])
        bottom.pack(fill="x",side="bottom",pady=8)
        for icon,label,cmd in [
            ("💾","Save",    self._save),
            ("📂","Open",    self._open),
            ("✨","New",     self._new),
            ("⚙️","Settings",self._settings),
        ]:
            btn = tk.Frame(bottom,bg=P["sidebar"],cursor="hand2")
            btn.pack(fill="x",padx=8,pady=1)
            lbl = tk.Label(btn,text=icon+" "+label,bg=P["sidebar"],fg="#CBD5E1",
                     font=("Segoe UI",10),anchor="w",padx=10,pady=5)
            lbl.pack(fill="x")
            # use default-arg capture to avoid closure bug
            btn.bind("<Enter>", lambda e,b=btn: b.configure(bg=P["sidebar_hl"]))
            btn.bind("<Leave>", lambda e,b=btn: b.configure(bg=P["sidebar"]))
            btn.bind("<Button-1>", lambda e,c=cmd: c())
            lbl.bind("<Enter>", lambda e,b=btn: b.configure(bg=P["sidebar_hl"]))
            lbl.bind("<Leave>", lambda e,b=btn: b.configure(bg=P["sidebar"]))
            lbl.bind("<Button-1>", lambda e,c=cmd: c())

    def _make_nav_btn(self, parent:tk.Frame, key:str, icon:str, label:str):
        P = PALETTE
        row = tk.Frame(parent,bg=P["sidebar"],cursor="hand2")
        row.pack(fill="x",padx=6,pady=1)
        icon_lbl = tk.Label(row,text=icon,bg=P["sidebar"],fg="#CBD5E1",
                             font=("Segoe UI",14),width=2)
        icon_lbl.pack(side="left",padx=(8,4),pady=8)
        name_lbl = tk.Label(row,text=label,bg=P["sidebar"],fg="#CBD5E1",
                             font=("Segoe UI",10),anchor="w")
        name_lbl.pack(side="left",fill="x",expand=True,pady=8)
        self._nav_btns[key] = row
        def _enter(e,r=row):
            if self._active_dept!=key: r.configure(bg=P["sidebar_hl"]); [c.configure(bg=P["sidebar_hl"]) for c in r.winfo_children()]
        def _leave(e,r=row):
            if self._active_dept!=key: r.configure(bg=P["sidebar"]); [c.configure(bg=P["sidebar"]) for c in r.winfo_children()]
        def _click(e,k=key): self._switch_dept(k)
        for widget in (row,icon_lbl,name_lbl):
            widget.bind("<Enter>",_enter); widget.bind("<Leave>",_leave)
            widget.bind("<Button-1>",_click)

    def _switch_dept(self, key:str):
        if not hasattr(self, '_toolbar_frame'): return
        P = PALETTE
        # deselect old
        if self._active_dept in self._nav_btns:
            old = self._nav_btns[self._active_dept]
            old.configure(bg=P["sidebar"])
            for c in old.winfo_children(): c.configure(bg=P["sidebar"],fg="#CBD5E1")
        self._active_dept = key
        # highlight new
        row = self._nav_btns[key]
        row.configure(bg=P["sidebar_sel"])
        for c in row.winfo_children(): c.configure(bg=P["sidebar_sel"],fg="#FFFFFF")
        # switch notebook tab
        order = ["documents","design","spreadsheet","slides","video","animation","creations"]
        self._dept_nb.select(order.index(key))
        # update toolbar
        self._rebuild_toolbar(key)

    def _on_dept_change(self, e=None):
        if not hasattr(self, '_toolbar_frame'): return
        order = ["documents","design","spreadsheet","slides","video","animation","creations"]
        try:
            idx = self._dept_nb.index("current")
            self._switch_dept(order[idx])
        except Exception: pass

    # ───────────────────────────────────────── CONTEXTUAL TOOLBAR ────────────
    def _rebuild_toolbar(self, dept:str):
        if not hasattr(self, '_toolbar_frame'):
            return
        for w in self._toolbar_frame.winfo_children(): w.destroy()
        bg = self._bg
        P  = PALETTE
        # thin top accent line
        accent_line = tk.Frame(self._toolbar_frame, bg=P["accent"], height=3)
        accent_line.pack(fill="x")
        bar = tk.Frame(self._toolbar_frame, bg=self._surface, pady=4)
        bar.pack(fill="x")

        def _btn(text, cmd, style="normal", tip=""):
            bg_c = P["accent"]  if style=="accent"  else \
                   P["danger"]  if style=="danger"   else \
                   self._surface
            fg_c = "#FFFFFF" if style in ("accent","danger") else self._fg
            f = tk.Frame(bar, bg=bg_c, cursor="hand2",
                         relief="flat", bd=0)
            lbl = tk.Label(f, text=text, bg=bg_c, fg=fg_c,
                           font=("Segoe UI",9), padx=10, pady=4)
            lbl.pack()
            f.pack(side="left", padx=2, pady=2)
            hover_bg = P["accent2"] if style=="accent" else \
                       "#B91C1C"    if style=="danger"  else \
                       (P["surface2"] if not self._dark else "#2D4A6E")
            def _e(ev,fr=f,lb=lbl,hb=hover_bg,ob=bg_c): fr.configure(bg=hb); lb.configure(bg=hb)
            def _l(ev,fr=f,lb=lbl,hb=hover_bg,ob=bg_c): fr.configure(bg=ob); lb.configure(bg=ob)
            f.bind("<Enter>",_e); lbl.bind("<Enter>",_e)
            f.bind("<Leave>",_l); lbl.bind("<Leave>",_l)
            f.bind("<Button-1>",lambda e,c=cmd:c()); lbl.bind("<Button-1>",lambda e,c=cmd:c())
            return f

        def _sep():
            tk.Frame(bar, bg=P["border"], width=1).pack(side="left",fill="y",padx=4,pady=4)

        def _combo(var, values, width=14):
            c = ttk.Combobox(bar,textvariable=var,values=values,
                              width=width,state="readonly",font=("Segoe UI",9))
            c.pack(side="left",padx=3,pady=3)
            return c

        def _spin(var, frm, to, width=4, inc=1):
            s = ttk.Spinbox(bar,from_=frm,to=to,increment=inc,
                             textvariable=var,width=width,font=("Segoe UI",9))
            s.pack(side="left",padx=2,pady=3)
            return s

        def _label(text):
            tk.Label(bar,text=text,bg=bar.cget("bg"),fg=self._fg,
                     font=("Segoe UI",9)).pack(side="left",padx=(6,2))

        if dept=="documents":
            _btn("✦ New",self._new)
            _btn("📂 Open",self._open)
            _btn("💾 Save",self._save,"accent")
            _sep()
            _btn("↩ Undo",self._undo)
            _btn("↪ Redo",self._redo)
            _sep()
            self.family=tk.StringVar(value="Segoe UI")
            self.fsize=tk.IntVar(value=12)
            _combo(self.family, sorted(set(font.families())),16)
            _spin(self.fsize,6,144)
            _sep()
            # ── Bold B (rendered bold) ────────────────────────────────
            bf = tk.Frame(bar, bg=self._surface,
                          cursor="hand2", relief="flat", bd=0)
            bl = tk.Label(bf, text="B", bg=self._surface,
                          fg=self._fg, font=("Segoe UI", 11, "bold"), padx=9, pady=4)
            bl.pack(); bf.pack(side="left", padx=2, pady=2)
            for w in (bf, bl):
                w.bind("<Enter>", lambda e, f=bf, l=bl: (f.configure(bg=P["surface2"]), l.configure(bg=P["surface2"])))
                w.bind("<Leave>", lambda e, f=bf, l=bl, ob=self._surface: (f.configure(bg=ob), l.configure(bg=ob)))
                w.bind("<Button-1>", lambda e: self._tag("bold"))
            # ── Italic I ─────────────────────────────────────────────
            itf = tk.Frame(bar, bg=self._surface,
                           cursor="hand2", relief="flat", bd=0)
            itl = tk.Label(itf, text="I", bg=self._surface,
                           fg=self._fg, font=("Segoe UI", 11, "italic"), padx=9, pady=4)
            itl.pack(); itf.pack(side="left", padx=2, pady=2)
            for w in (itf, itl):
                w.bind("<Enter>", lambda e, f=itf, l=itl: (f.configure(bg=P["surface2"]), l.configure(bg=P["surface2"])))
                w.bind("<Leave>", lambda e, f=itf, l=itl, ob=self._surface: (f.configure(bg=ob), l.configure(bg=ob)))
                w.bind("<Button-1>", lambda e: self._tag("italic"))
            # ── Underline U ──────────────────────────────────────────
            uf = tk.Frame(bar, bg=self._surface,
                          cursor="hand2", relief="flat", bd=0)
            ul = tk.Label(uf, text="U", bg=self._surface,
                          fg=self._fg, font=("Segoe UI", 11, "underline"), padx=9, pady=4)
            ul.pack(); uf.pack(side="left", padx=2, pady=2)
            for w in (uf, ul):
                w.bind("<Enter>", lambda e, f=uf, l=ul: (f.configure(bg=P["surface2"]), l.configure(bg=P["surface2"])))
                w.bind("<Leave>", lambda e, f=uf, l=ul, ob=self._surface: (f.configure(bg=ob), l.configure(bg=ob)))
                w.bind("<Button-1>", lambda e: self._tag("under"))
            # ── Strikethrough S ───────────────────────────────────────
            sf2 = tk.Frame(bar, bg=self._surface,
                           cursor="hand2", relief="flat", bd=0)
            sl2 = tk.Label(sf2, text="S", bg=self._surface,
                           fg=self._fg, font=("Segoe UI", 11, "overstrike"), padx=9, pady=4)
            sl2.pack(); sf2.pack(side="left", padx=2, pady=2)
            for w in (sf2, sl2):
                w.bind("<Enter>", lambda e, f=sf2, l=sl2: (f.configure(bg=P["surface2"]), l.configure(bg=P["surface2"])))
                w.bind("<Leave>", lambda e, f=sf2, l=sl2, ob=self._surface: (f.configure(bg=ob), l.configure(bg=ob)))
                w.bind("<Button-1>", lambda e: self._tag("strike"))
            _sep()
            # ── Rainbow "Color" button ────────────────────────────────
            cf2 = tk.Frame(bar, bg=self._surface,
                           cursor="hand2", relief="flat", bd=0, padx=2, pady=2)
            cf2.pack(side="left", padx=2, pady=2)
            rainbow = [("#E53935","C"),("#F4511E","o"),("#FB8C00","l"),
                       ("#43A047","o"),("#1E88E5","r")]
            for rc, rl in rainbow:
                tk.Label(cf2, text=rl, fg=rc,
                         bg=self._surface,
                         font=("Segoe UI", 10, "bold"), padx=0).pack(side="left")
            cf2.bind("<Button-1>", lambda e: self._text_color())
            for child in cf2.winfo_children():
                child.bind("<Button-1>", lambda e: self._text_color())
                child.bind("<Enter>", lambda e, f=cf2: f.configure(bg=P["surface2"]))
                child.bind("<Leave>", lambda e, f=cf2, ob=self._surface: f.configure(bg=ob))
            cf2.bind("<Enter>", lambda e: cf2.configure(bg=P["surface2"]))
            cf2.bind("<Leave>", lambda e, ob=self._surface: cf2.configure(bg=ob))
            # ── Highlight button with yellow background ───────────────
            hf = tk.Frame(bar, bg="#FEF08A", cursor="hand2", relief="flat", bd=0)
            hl = tk.Label(hf, text=" Highlight ", bg="#FEF08A",
                          fg="#78350F", font=("Segoe UI", 9, "bold"), padx=4, pady=4)
            hl.pack(); hf.pack(side="left", padx=2, pady=2)
            for w in (hf, hl):
                w.bind("<Enter>", lambda e, f=hf, l=hl: (f.configure(bg="#FDE047"), l.configure(bg="#FDE047")))
                w.bind("<Leave>", lambda e, f=hf, l=hl: (f.configure(bg="#FEF08A"), l.configure(bg="#FEF08A")))
                w.bind("<Button-1>", lambda e: self._highlight())
            _sep()
            # ── Align buttons with visual line icons ──────────────────
            for icon, tip, cmd in [
                ("⬛\n▬▬▬\n▬▬  ", "Align Left",   lambda:self._align("left")),
                ("▬▬▬\n▬▬▬\n▬▬ ", "Align Center", lambda:self._align("center")),
                ("▬▬▬\n▬▬\n▬▬  ", "Align Right",  lambda:self._align("right")),
            ]:
                # Use clean Unicode icons instead
                pass
            # Clean align icons using proper symbols
            for sym, tip, cmd in [
                ("≡←", "Align Left",   lambda:self._align("left")),
                ("≡↔", "Align Center", lambda:self._align("center")),
                ("≡→", "Align Right",  lambda:self._align("right")),
            ]:
                af = tk.Frame(bar, bg=self._surface,
                              cursor="hand2", relief="flat", bd=0)
                al = tk.Label(af, text=sym, bg=self._surface,
                              fg=self._fg, font=("Segoe UI", 10), padx=8, pady=4)
                al.pack(); af.pack(side="left", padx=2, pady=2)
                for w in (af, al):
                    w.bind("<Enter>", lambda e, f=af, l=al: (f.configure(bg=P["surface2"]), l.configure(bg=P["surface2"])))
                    w.bind("<Leave>", lambda e, f=af, l=al, ob=self._surface: (f.configure(bg=ob), l.configure(bg=ob)))
                    w.bind("<Button-1>", lambda e, c=cmd: c())
            _sep()
            for t,fn in [("📄 PDF",self._pdf),("📝 DOCX",self._docx),
                          ("🌐 HTML",self._html),("🖨 Print",self._print)]:
                _btn(t,fn)
            _sep()
            _btn("📋 Templates",self._template_gallery,"accent")
            _btn("🌍 Translate",self._translate)
            _btn("ء Diacritics",self._diacritics)
            _sep()
            _btn("✨ AI",self._ai_assistant,"accent")

        elif dept=="design":
            _btn("New",self._design_new)
            _btn("Save…",self._design_save)
            _btn("Export PNG",self._design_export_png,"accent")
            _btn("Export SVG",self._design_export_svg)
            _sep()
            _btn("↩ Undo",self._design_undo)
            _btn("↪ Redo",self._design_redo_action)
            _btn("⊞ Snap",self._design_snap_toggle)
            _btn("📋 Templates",self._design_templates_gallery)
            _sep()
            for t,fn in [("Text",self._design_add_text),
                          ("Rect",lambda:self._design_add_shape("rect")),
                          ("Ellipse",lambda:self._design_add_shape("ellipse")),
                          ("Triangle",lambda:self._design_add_shape("triangle")),
                          ("Star",lambda:self._design_add_shape("star")),
                          ("Pentagon",lambda:self._design_add_shape("pentagon")),
                          ("Hexagon",lambda:self._design_add_shape("hexagon")),
                          ("Line",lambda:self._design_add_shape("line")),
                          ("Arrow",lambda:self._design_add_shape("arrow")),
                          ("Image",self._design_add_image)]:
                _btn(t,fn)
            _sep()
            _btn("Duplicate", self._design_duplicate)
            _btn("Delete",    self._design_delete, "danger")
            _btn("Up layer",  lambda: self._design_reorder(-1))
            _btn("Down layer",lambda: self._design_reorder(1))
            _sep()
            for t,fn in [("Align L",lambda:self._design_align("left")),
                          ("Align C",lambda:self._design_align("center")),
                          ("Align R",lambda:self._design_align("right")),
                          ("Align T",lambda:self._design_align("top")),
                          ("Align M",lambda:self._design_align("middle")),
                          ("Align B",lambda:self._design_align("bottom"))]:
                _btn(t,fn)

        elif dept=="spreadsheet":
            _btn("📊 Chart",self._sheet_chart)
            _btn("⇃ Auto-fill",self._sheet_auto_fill)
            _btn("↕ Sort",self._sheet_sort_column)
            _btn("🔍 Find",self._sheet_find_replace)
            _sep()
            _btn("✦ New",self._sheet_new)
            _btn("📂 Open",self._sheet_open)
            _btn("💾 Save",self._sheet_save_csv,"accent")
            _sep()
            _btn("＋Row",self._sheet_add_row)
            _btn("＋Col",self._sheet_add_col)
            _btn("－Row",self._sheet_del_row,"danger")
            _btn("𝐁 Bold",self._sheet_bold)
            _sep()
            _label("Fill:")
            self._sheet_fill_btn=tk.Label(bar,bg="#FFFFFF",width=3,
                relief="solid",cursor="hand2",bd=1)
            self._sheet_fill_btn.pack(side="left",padx=3,pady=5)
            self._sheet_fill_btn.bind("<Button-1>",lambda e:self._sheet_fill_color())
            _btn("⊞ Border",self._sheet_toggle_border)
            _sep()
            _label("Format:")
            self._sheet_fmt_var=tk.StringVar(value="General")
            _combo(self._sheet_fmt_var,["General","Number","Currency","Percent","Date"],10)
            _btn("Apply",self._sheet_apply_format)
            _sep()
            _btn("❄ Freeze",self._sheet_freeze_toggle)
            _btn("fx Help",self._sheet_formula_help)

        elif dept=="slides":
            _btn("🎨 Themes",self._slide_theme_gallery)
            _btn("🖼 Image",self._slide_add_image)
            _btn("📺 Presenter",self._present_with_notes,"accent")
            _sep()
            _btn("＋ Slide",self._slide_add,"accent")
            _btn("⎘ Dup",self._slide_duplicate)
            _btn("✕ Del",self._slide_delete,"danger")
            _btn("↑",lambda:self._slide_move(-1))
            _btn("↓",lambda:self._slide_move(1))
            _sep()
            _btn("▶ Present",self._present,"accent")
            _btn("📤 PPTX",self._slide_export_pptx)
            _sep()
            _label("Transition:")
            self._slide_trans_var=tk.StringVar(value="Fade")
            _combo(self._slide_trans_var,["None","Fade","Slide","Zoom","Wipe","Dissolve"],10)
            _sep()
            _label("BG:")
            self._slide_theme=tk.StringVar(value="#1E2D40")
            ttk.Entry(bar,textvariable=self._slide_theme,
                       width=8,font=("Segoe UI",9)).pack(side="left",padx=2)
            bg_pick=tk.Label(bar,text="🎨",bg=bar.cget("bg"),fg=self._fg,
                              cursor="hand2",font=("Segoe UI",14),padx=3)
            bg_pick.pack(side="left")
            bg_pick.bind("<Button-1>",lambda e:self._slide_pick_bg())
            _btn("✔ Apply",self._slide_apply_theme)
            _sep()
            _label("Font sz:")
            self._slide_font_size=tk.IntVar(value=32)
            _spin(self._slide_font_size,12,96)

        elif dept=="video":
            _btn("＋ Clips",self._video_add_clips,"accent")
            _btn("🎵 Audio",self._video_add_audio)
            _btn("T Titles",self._video_add_title)
            _btn("📍 Marker",self._video_add_marker)
            _sep()
            _btn("✕ Remove",self._video_remove_clip,"danger")
            _btn("⎘ Dup track",self._video_duplicate_track)
            _btn("＋ Track",self._video_add_track)
            _btn("↑",lambda:self._video_move_clip(-1))
            _btn("↓",lambda:self._video_move_clip(1))
            _sep()
            _label("Label:")
            self._vid_label_var=tk.StringVar()
            ttk.Entry(bar,textvariable=self._vid_label_var,
                       width=12,font=("Segoe UI",9)).pack(side="left",padx=2)
            _btn("Set",self._video_set_clip_label)
            _sep()
            _btn("💾 Save",self._video_save,"accent")
            _btn("📂 Open",self._video_open)
            _btn("🎬 Render",self._video_render)
            _btn("📄 SRT",self._video_export_srt)

        elif dept=="animation":
            _btn("🎞 Tween",self._anim_tween)
            _btn("🔷 Symbol",self._anim_symbol_insert)
            _btn("🎵 Audio",self._anim_audio_waveform)
            _sep()
            _btn("＋ Frame",self._anim_add_frame,"accent")
            _btn("⎘ Dup",self._anim_duplicate_frame)
            _btn("✕ Del",self._anim_delete_frame,"danger")
            _btn("⌫ Clear",self._anim_clear_frame)
            _sep()
            _btn("▶ Play",self._anim_play_toggle)
            _sep()
            _btn("💾 Save",self._anim_save,"accent")
            _btn("📂 Open",self._anim_open)
            _btn("🎞 GIF",self._anim_export_gif)
            _btn("🖼 PNG seq",self._anim_export_png_seq)
            _sep()
            _label("FPS:")
            self._anim_fps_var=tk.IntVar(value=self._anim_project["fps"])
            _spin(self._anim_fps_var,1,60)
            self._anim_fps_var.trace_add("write",lambda *_:self._anim_fps_changed())
            _sep()
            _label("BG:")
            self._anim_bg_lbl=tk.Label(bar,bg=self._anim_project.get("background","#FFFFFF"),
                                        width=3,relief="solid",cursor="hand2")
            self._anim_bg_lbl.pack(side="left",padx=3,pady=5)
            self._anim_bg_lbl.bind("<Button-1>",lambda e:self._anim_pick_bg())
            _btn("📐 Canvas",self._anim_canvas_size)
            _sep()
            _label("Brush:")
            self._anim_brush=tk.IntVar(value=5)
            _spin(self._anim_brush,1,80)
            _label("Color:")
            self._anim_color_lbl=tk.Label(bar,bg=self._anim_color,
                                           width=3,relief="solid",cursor="hand2")
            self._anim_color_lbl.pack(side="left",padx=4,pady=5)
            self._anim_color_lbl.bind("<Button-1>",lambda e:self._anim_pick_color())

        elif dept=="creations":
            _btn("⟳ Refresh",self._creations_refresh)
            _btn("📂 Open folder",self._creations_open_folder)
            _sep()
            _btn("🗑 Delete",self._creations_delete,"danger")
            _btn("📋 Copy path",self._creations_copy_path)
            _sep()
            _btn("📤 Export",self._creations_export)

        # Always show dept title at far right of toolbar
        tk.Label(bar,text={"documents":"📄 Documents","design":"🎨 Design",
                            "spreadsheet":"📊 Spreadsheet","slides":"🖼 Slides",
                            "video":"🎬 Video","animation":"🎞 Animation",
                            "creations":"🗂 Creations"}.get(dept,""),
                 bg=bar.cget("bg"),fg=P["muted"],
                 font=("Segoe UI",10,"bold")).pack(side="right",padx=16)

    # ──────────────────────────────────────────────────────── menu ───────────
    def _menu(self):
        m=tk.Menu(self); self.config(menu=m)
        def _sub(label,items):
            s=tk.Menu(m,tearoff=False)
            for t,f in items: s.add_command(label=t,command=f)
            m.add_cascade(label=label,menu=s)
        _sub("File",[
            ("New document",self._new),("Open…",self._open),
            ("Save",self._save),("Save As…",self._save_as),
            ("Print…",self._print),("Settings…",self._settings),("Close",self._close),
        ])
        _sub("Edit",[
            ("Undo",self._undo),("Redo",self._redo),
            ("Cut",lambda:self.editor.event_generate("<<Cut>>")),
            ("Copy",lambda:self.editor.event_generate("<<Copy>>")),
            ("Paste",lambda:self.editor.event_generate("<<Paste>>")),
            ("Select all",lambda:self.editor.event_generate("<<SelectAll>>")),
            ("Find & Replace…",self._find_replace),("Word count",self._words),
        ])
        _sub("Insert",[
            ("Page break",self._add_page),("Image…",self._image),
            ("Table…",self._table),("Table of Contents",self._doc_toc),("Mail merge...",self._doc_mail_merge),("Footnote...",self._doc_footnote),("Checklist",self._checklist),
            ("Flashcard",self._flashcard),("Equation",self._equation),
            ("Answer lines…",self._answer_lines),
            ("Horizontal rule",lambda:self._insert("\n─────────────────────────────────\n")),
            ("Date",self._insert_date),("Hyperlink…",self._hyperlink),
            ("Symbol…",self._insert_symbol),
        ])
        _sub("Format",[
            ("Bold",lambda:self._tag("bold")),("Italic",lambda:self._tag("italic")),
            ("Underline",lambda:self._tag("under")),("Strikethrough",lambda:self._tag("strike")),
            ("Superscript",lambda:self._tag("super")),("Subscript",lambda:self._tag("sub")),
            ("Text color…",self._text_color),("Highlight…",self._highlight),
            ("Clear formatting",self._clear_format),
            ("Align left",lambda:self._align("left")),
            ("Align center",lambda:self._align("center")),
            ("Align right",lambda:self._align("right")),
        ])
        _sub("Styles",[
            (s,lambda x=s:self._style(x))
            for s in ("Normal","Title","Heading 1","Heading 2","Heading 3",
                       "Quote","Code","Question")
        ])
        _sub("Export",[
            ("PDF…",self._pdf),("HTML…",self._html),
            ("Plain text…",self._txt),("Word DOCX…",self._docx),
            ("SVG…",self._export_svg),("Print…",self._print),
            ("Export to ZIP…",self._export_zip),
        ])
        _sub("Review",[
            ("Translate selection…",self._translate),
            ("Translate whole page…",self._translate_page),
            ("Arabic diacritics…",self._diacritics),
            ("Auto-correct",self._auto_correct),
            ("Find & Replace…",self._find_replace),
            ("Word count",self._words),("Read aloud",self._read_aloud),
            ("✨ AI Writing Assistant…",self._ai_assistant),
        ])
        _sub("View",[
            ("Zoom in",lambda:self._zoom_to(self.zoom.get()+10)),
            ("Zoom out",lambda:self._zoom_to(self.zoom.get()-10)),
            ("100%",lambda:self._zoom_to(100)),("Fit page",lambda:self._zoom_to(65)),
            ("Toggle dark mode",self._toggle_dark),
            ("Present",self._present),
            ("Keyboard shortcuts  F1",self._show_shortcuts),
        ])
        _sub("Slides",[
            ("🎨 Theme gallery…",self._slide_theme_gallery),
            ("🖼 Add image to slide…",self._slide_add_image),
            ("▶ Presenter view…",self._present_with_notes),
        ])
        _sub("Design",[
            ("↩ Undo",self._design_undo),
            ("↪ Redo",self._design_redo_action),
            ("⊞ Snap to grid toggle",self._design_snap_toggle),
            ("📋 Templates gallery…",self._design_templates_gallery),
        ])
        _sub("Spreadsheet",[
            ("📊 Insert chart…",self._sheet_chart),
            ("🔄 Auto-fill series…",self._sheet_auto_fill),
            ("↕ Sort column…",self._sheet_sort_column),
            ("🔍 Find & Replace cells…",self._sheet_find_replace),
            ("＋ Add sheet",self._sheet_add_sheet),
        ])
        _sub("Animation",[
            ("🎞 Tween frames…",self._anim_tween),
            ("🔷 Save symbol…",self._anim_symbol_save),
            ("🔷 Insert symbol…",self._anim_symbol_insert),
            ("🎵 Audio waveform…",self._anim_audio_waveform),
        ])
        _sub("Tools",[
            ("🧩 Plugins…",self._plugins_menu),
            ("☁ Cloud sync…",self._cloud_sync_stub),
            ("📦 Export ZIP…",self._export_zip),
        ])

        _sub("Help", [("Check for updates...", self._check_for_updates)])

    def _check_for_updates(self):
        """Opt-in GitHub release check. Never installs; only reports."""
        import json as _json, urllib.request as _ur, urllib.error as _ue
        repo = "Cambric-software/C-EDITOR"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = _ur.Request(url, headers={"User-Agent": "C-EDITOR"})
            with _ur.urlopen(req, timeout=8) as r:
                data = _json.loads(r.read().decode("utf-8"))
            tag = data.get("tag_name", "")
            html_url = data.get("html_url", "")
            if tag:
                messagebox.showinfo("Updates",
                    f"Latest release: {tag}\nCurrent: v{VERSION}\n\n{html_url}")
            else:
                messagebox.showinfo("Updates", "No published release found.")
        except _ue.URLError:
            messagebox.showwarning("Updates", "Could not reach GitHub (offline?).")
        except Exception as e:
            messagebox.showerror("Updates", f"Update check failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  DOCUMENTS TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_documents(self, parent:tk.Frame):
        P=PALETTE
        pw=tk.PanedWindow(parent,orient="horizontal",bg=self._bg,
                           sashwidth=4,sashrelief="flat")
        pw.pack(fill="both",expand=True)

        # ── left panel ────────────────────────────────────────────────────────
        left=tk.Frame(pw,bg=self._bg,width=220)
        pw.add(left,minsize=160)
        left.pack_propagate(False)

        nb_left=ttk.Notebook(left)
        nb_left.pack(fill="both",expand=True,padx=4,pady=4)

        pages_f=tk.Frame(nb_left,bg=self._bg)
        elems_f=tk.Frame(nb_left,bg=self._bg)
        nb_left.add(pages_f,text="📄 Pages")
        nb_left.add(elems_f,text="¶ Elements")

        # pages
        self.pages_lb=tk.Listbox(pages_f,bg=self._surface,fg=self._fg,
                                  selectbackground=P["accent"],selectforeground="#FFF",
                                  font=("Segoe UI",10),relief="flat",bd=0,
                                  activestyle="none",exportselection=False)
        self.pages_lb.pack(fill="both",expand=True,padx=4,pady=(4,0))
        self.pages_lb.bind("<<ListboxSelect>>",self._page_select)
        pf=tk.Frame(pages_f,bg=self._bg); pf.pack(fill="x",padx=4,pady=4)
        for t,fn in [("+ Page",self._add_page),("Dup",self._duplicate_page),
                      ("Del",self._delete_page),("↑",lambda:self._move_page(-1)),
                      ("↓",lambda:self._move_page(1))]:
            ttk.Button(pf,text=t,command=fn).pack(side="left",padx=1)

        # elements
        self.elements_lb=tk.Listbox(elems_f,bg=self._surface,fg=self._fg,
                                     selectbackground=P["accent"],selectforeground="#FFF",
                                     font=("Segoe UI",9),relief="flat",bd=0,
                                     activestyle="none",exportselection=False)
        self.elements_lb.pack(fill="both",expand=True,padx=4,pady=(4,0))
        self.elements_lb.bind("<<ListboxSelect>>",self._element_focus)
        tk.Label(elems_f,text="Paragraph bookmarks",bg=self._bg,
                  fg=P["muted"],font=("Segoe UI",8)).pack(padx=8,pady=4,anchor="w")

        # ── center (canvas) ───────────────────────────────────────────────────
        center=tk.Frame(pw,bg="#C8C8C8")
        pw.add(center,minsize=400)

        canv_wrap=tk.Frame(center,bg="#C8C8C8")
        canv_wrap.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(canv_wrap,bg="#C8C8C8",highlightthickness=0)
        self.canvas.pack(side="left",fill="both",expand=True)
        sb=ttk.Scrollbar(canv_wrap,command=self.canvas.yview)
        sb.pack(side="right",fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.paper=tk.Frame(self.canvas,bg="white",
                             relief="flat",bd=0,
                             highlightbackground="#B0B8C4",
                             highlightthickness=1)
        self.paperid=self.canvas.create_window(20,20,window=self.paper,anchor="nw")

        # shadow effect
        self.canvas.bind("<Configure>",lambda e:self._resize())

        self.header_lbl=tk.Label(self.paper,bg="white",anchor="e",
                                  font=("Segoe UI",9),pady=4)
        self.header_lbl.pack(fill="x",padx=55,pady=(24,2))
        tk.Frame(self.paper,bg=P["border"],height=1).pack(fill="x",padx=55)

        self.editor=ScrolledText(self.paper,undo=True,autoseparators=True,
                                  wrap="word",font=("Segoe UI",12),
                                  foreground="#1E293B",bg="white",
                                  relief="flat",bd=0,spacing1=4,spacing3=9,
                                  insertbackground="#315C8A",
                                  selectbackground="#BFDBFE")
        self.editor.pack(fill="both",expand=True,padx=55,pady=16)
        self.editor.bind("<<Modified>>",self._changed)
        self.editor.bind("<KeyRelease>",lambda e: (self._refresh_elements(e), self._update_word_count(e)))
        self.editor.bind("<ButtonRelease>",self._info)
        self.editor.bind("<Control-z>",lambda e:self._undo())
        self.editor.bind("<Control-y>",lambda e:self._redo())
        self.editor.bind("<Control-b>",lambda e:self._tag("bold"))
        self.editor.bind("<Control-i>",lambda e:self._tag("italic"))
        self.editor.bind("<Control-u>",lambda e:self._tag("under"))
        self.editor.bind("<Control-h>",lambda e:self._find_replace())
        self.editor.bind("<Control-s>",lambda e:self._save())

        # drawing overlay
        self.drawing=tk.Canvas(self.paper,highlightthickness=0,bg="white")
        self.drawing.bind("<ButtonPress-1>",self._draw_start)
        self.drawing.bind("<B1-Motion>",self._draw_move)
        self.drawing.bind("<ButtonRelease-1>",self._draw_end)

        tk.Frame(self.paper,bg=P["border"],height=1).pack(fill="x",padx=55)
        self.footer_lbl=tk.Label(self.paper,bg="white",anchor="center",
                                  font=("Segoe UI",8),fg=P["muted"],pady=4)
        self.footer_lbl.pack(fill="x",padx=55,pady=(2,20))

        # ── right panel (properties) ──────────────────────────────────────────
        right=tk.Frame(pw,bg=self._bg,width=250)
        pw.add(right,minsize=200)
        right.pack_propagate(False)

        nb_right=ttk.Notebook(right)
        nb_right.pack(fill="both",expand=True,padx=4,pady=4)
        props_f =tk.Frame(nb_right,bg=self._bg)
        styles_f=tk.Frame(nb_right,bg=self._bg)
        layout_f=tk.Frame(nb_right,bg=self._bg)
        draw_f  =tk.Frame(nb_right,bg=self._bg)
        nb_right.add(props_f, text="⚙ Properties")
        nb_right.add(styles_f,text="🎨 Styles")
        nb_right.add(layout_f,text="📐 Layout")
        nb_right.add(draw_f,  text="✏️ Draw")

        # Properties
        self.titlevar=tk.StringVar(); self.headvar=tk.StringVar()
        self.footvar=tk.StringVar();  self.langvar=tk.StringVar(value="English")
        self.numbers_var=tk.BooleanVar(value=True)
        pf2=tk.Frame(props_f,bg=self._bg); pf2.pack(fill="x",padx=8,pady=4)
        for lbl,var in [("Document title",self.titlevar),("Header",self.headvar),("Footer",self.footvar)]:
            tk.Label(pf2,text=lbl,bg=self._bg,fg=P["muted"],
                      font=("Segoe UI",8)).pack(anchor="w",pady=(6,1))
            e=ttk.Entry(pf2,textvariable=var,font=("Segoe UI",10))
            e.pack(fill="x",pady=(0,2))
            e.bind("<FocusOut>",lambda _e:self._properties())
        tk.Label(pf2,text="Language",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",pady=(8,1))
        cb=ttk.Combobox(pf2,textvariable=self.langvar,values=LANGS,
                          state="readonly",font=("Segoe UI",10))
        cb.pack(fill="x"); cb.bind("<<ComboboxSelected>>",lambda _e:self._properties())
        ttk.Checkbutton(pf2,text="Page numbers",variable=self.numbers_var,
                        command=self._properties).pack(anchor="w",pady=8)
        ttk.Separator(props_f).pack(fill="x",padx=8,pady=4)
        self.sel_info=tk.StringVar(value="Click in the document.")
        tk.Label(props_f,textvariable=self.sel_info,bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",9),wraplength=220,justify="left").pack(
            anchor="w",padx=8,pady=4)

        # Styles
        tk.Label(styles_f,text="Quick styles",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=(8,4))
        for s in ("Normal","Title","Heading 1","Heading 2","Heading 3",
                   "Quote","Code","Question"):
            ttk.Button(styles_f,text=s,command=lambda x=s:self._style(x)).pack(
                fill="x",padx=8,pady=2)
        ttk.Separator(styles_f).pack(fill="x",padx=8,pady=8)
        tk.Label(styles_f,text="Insert",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=(0,4))
        for t,fn in [("• Bullet list",lambda:self._insert_list("•")),
                      ("1. Numbered",  lambda:self._insert_list("1.")),
                      ("Checklist",    self._checklist),
                      ("Table",        self._table),
                      ("Flashcard",    self._flashcard),
                      ("Equation",     self._equation),
                      ("Answer lines", self._answer_lines),
                      ("Horizontal rule",lambda:self._insert("\n─────────────────────────────────\n"))]:
            ttk.Button(styles_f,text=t,command=fn).pack(fill="x",padx=8,pady=1)

        # Layout
        self._pgs    = tk.StringVar(value="A4")
        self._orient = tk.StringVar(value="Portrait")
        self._margin = tk.IntVar(value=56)
        self._theme_var=tk.StringVar(value="#315C8A")
        lf=tk.Frame(layout_f,bg=self._bg); lf.pack(fill="x",padx=8,pady=4)
        for lbl,var,values in [("Page size",self._pgs,list(PAGE_SIZES.keys())),
                                 ("Orientation",self._orient,["Portrait","Landscape"])]:
            tk.Label(lf,text=lbl,bg=self._bg,fg=P["muted"],
                      font=("Segoe UI",8)).pack(anchor="w",pady=(6,1))
            ttk.Combobox(lf,textvariable=var,values=values,
                          state="readonly").pack(fill="x")
        tk.Label(lf,text="Margin",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",pady=(6,1))
        ttk.Spinbox(lf,from_=10,to=150,textvariable=self._margin,width=6).pack(anchor="w")
        tk.Label(lf,text="Theme color",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",pady=(6,1))
        tr=tk.Frame(lf,bg=self._bg); tr.pack(fill="x")
        ttk.Entry(tr,textvariable=self._theme_var,width=9).pack(side="left")
        ttk.Button(tr,text="Pick",command=self._pick_theme).pack(side="left",padx=4)
        ttk.Button(lf,text="Apply layout",
                    command=self._layout_apply).pack(fill="x",pady=8)
        tk.Label(lf,text="Zoom",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",pady=(4,1))
        zoom_row=tk.Frame(lf,bg=self._bg); zoom_row.pack(fill="x")
        for t,z in [("-10",lambda:self._zoom_to(self.zoom.get()-10)),
                     ("Fit",lambda:self._zoom_to(65)),
                     ("100%",lambda:self._zoom_to(100)),
                     ("+10",lambda:self._zoom_to(self.zoom.get()+10))]:
            ttk.Button(zoom_row,text=t,command=z).pack(side="left",padx=1)

        # Draw tools
        tk.Label(draw_f,text="Drawing tool",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=(8,4))
        for name in ("Select","Pencil","Highlighter","Line",
                      "Arrow","Rectangle","Ellipse","Eraser"):
            ttk.Radiobutton(draw_f,text=name,value=name,
                            variable=self.draw_tool).pack(anchor="w",padx=12,pady=2)
        ttk.Separator(draw_f).pack(fill="x",padx=8,pady=6)
        tk.Label(draw_f,text="Draw color",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",padx=8)
        dc_row=tk.Frame(draw_f,bg=self._bg); dc_row.pack(fill="x",padx=8,pady=4)
        ttk.Entry(dc_row,textvariable=self._draw_color_var,width=9).pack(side="left")
        ttk.Button(dc_row,text="Pick",
                    command=self._pick_draw_color).pack(side="left",padx=4)
        ttk.Button(draw_f,text="Clear drawings",
                    command=self._clear_drawings).pack(fill="x",padx=8,pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    #  DESIGN CANVAS TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_design(self, parent:tk.Frame):
        P=PALETTE
        pw=tk.PanedWindow(parent,orient="horizontal",bg=self._bg,sashwidth=4)
        pw.pack(fill="both",expand=True)

        # canvas
        canvas_col=tk.Frame(pw,bg="#6B7280")
        pw.add(canvas_col,minsize=400)
        self.dcanvas=tk.Canvas(canvas_col,bg="#6B7280",highlightthickness=0)
        self.dcanvas.pack(fill="both",expand=True)
        self.dcanvas.bind("<ButtonPress-1>",self._dc_down)
        self.dcanvas.bind("<B1-Motion>",self._dc_drag)
        self.dcanvas.bind("<ButtonRelease-1>",self._dc_up)
        self.dcanvas.bind("<Configure>",lambda e:self._dc_redraw())
        self.dcanvas.bind("<Double-Button-1>",self._design_edit_text_inplace)

        # props
        props=tk.Frame(pw,bg=self._bg,width=260)
        pw.add(props,minsize=220)
        props.pack_propagate(False)

        tk.Label(props,text="Object properties",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",11,"bold")).pack(anchor="w",padx=10,pady=(10,4))

        self._dp_kind  =tk.StringVar(value="—")
        self._dp_x     =tk.DoubleVar(value=0)
        self._dp_y     =tk.DoubleVar(value=0)
        self._dp_w     =tk.DoubleVar(value=200)
        self._dp_h     =tk.DoubleVar(value=100)
        self._dp_fill  =tk.StringVar(value="#315C8A")
        self._dp_stroke=tk.StringVar(value="")
        self._dp_opac  =tk.DoubleVar(value=1.0)
        self._dp_text  =tk.StringVar(value="")
        self._dp_fsize =tk.IntVar(value=22)
        self._dp_bold  =tk.BooleanVar(value=False)
        self._dp_italic=tk.BooleanVar(value=False)
        self._dp_tcol  =tk.StringVar(value="#FFFFFF")

        pf=tk.Frame(props,bg=self._bg); pf.pack(fill="x",padx=10)
        pf.columnconfigure(1,weight=1)
        for row,(lbl,var) in enumerate([
            ("Kind",self._dp_kind),("X",self._dp_x),("Y",self._dp_y),
            ("Width",self._dp_w),("Height",self._dp_h),("Opacity",self._dp_opac),
        ]):
            tk.Label(pf,text=lbl,bg=self._bg,fg=P["muted"],
                      font=("Segoe UI",8)).grid(row=row,column=0,sticky="w",pady=2)
            if lbl=="Kind":
                tk.Label(pf,textvariable=var,bg=self._bg,fg=self._fg,
                          font=("Segoe UI",9)).grid(row=row,column=1,sticky="w")
            else:
                ttk.Entry(pf,textvariable=var,width=12).grid(
                    row=row,column=1,sticky="ew",pady=1)

        tk.Label(pf,text="Fill",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).grid(row=6,column=0,sticky="w",pady=2)
        fr=tk.Frame(pf,bg=self._bg); fr.grid(row=6,column=1,sticky="ew")
        ttk.Entry(fr,textvariable=self._dp_fill,width=8).pack(side="left")
        ttk.Button(fr,text="…",width=2,command=self._dp_pick_fill).pack(side="left",padx=2)

        tk.Label(pf,text="Stroke",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).grid(row=7,column=0,sticky="w",pady=2)
        ttk.Entry(pf,textvariable=self._dp_stroke,width=12).grid(
            row=7,column=1,sticky="ew",pady=1)

        ttk.Separator(props).pack(fill="x",padx=10,pady=6)
        tk.Label(props,text="Text",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=10)
        tf=tk.Frame(props,bg=self._bg); tf.pack(fill="x",padx=10,pady=4)
        tf.columnconfigure(1,weight=1)
        for row,(lbl,var) in enumerate([("Content",self._dp_text),
                                          ("Font size",self._dp_fsize)]):
            tk.Label(tf,text=lbl,bg=self._bg,fg=P["muted"],
                      font=("Segoe UI",8)).grid(row=row,column=0,sticky="w",pady=2)
            ttk.Entry(tf,textvariable=var,width=14).grid(
                row=row,column=1,sticky="ew",pady=1)

        ttk.Checkbutton(props,text="Bold",variable=self._dp_bold).pack(anchor="w",padx=10)
        ttk.Checkbutton(props,text="Italic",variable=self._dp_italic).pack(anchor="w",padx=10)
        tk.Label(props,text="Text color",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",padx=10,pady=(4,1))
        tcr=tk.Frame(props,bg=self._bg); tcr.pack(fill="x",padx=10)
        ttk.Entry(tcr,textvariable=self._dp_tcol,width=8).pack(side="left")
        ttk.Button(tcr,text="…",width=2,command=self._dp_pick_tcol).pack(side="left",padx=2)

        ttk.Button(props,text="Apply changes",
                    command=self._dp_apply).pack(fill="x",padx=10,pady=(10,4))

        ttk.Separator(props).pack(fill="x",padx=10,pady=6)
        tk.Label(props,text="Canvas presets",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=10)
        for lbl,w,h in [("Social 1080×1080",1080,1080),("Story 1080×1920",1080,1920),
                          ("HD 1920×1080",1920,1080),("A4 794×1123",794,1123),
                          ("Poster 2480×3508",2480,3508),("Banner 1200×628",1200,628)]:
            ttk.Button(props,text=lbl,
                        command=lambda a=w,b=h:self._design_resize(a,b)).pack(
                fill="x",padx=10,pady=1)


    # ══════════════════════════════════════════════════════════════════════════
    #  SPREADSHEET TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_spreadsheet(self, parent:tk.Frame):
        P=PALETTE
        # formula bar
        fb=tk.Frame(parent,bg=self._surface,
                    relief="flat",pady=3)
        fb.pack(fill="x",padx=0)
        tk.Label(fb,text="Cell:",bg=fb.cget("bg"),fg=self._fg,
                  font=("Segoe UI",9)).pack(side="left",padx=(8,2))
        self._sheet_cell_ref=tk.StringVar(value="A1")
        tk.Label(fb,textvariable=self._sheet_cell_ref,width=5,
                  bg=fb.cget("bg"),fg=P["accent"],
                  font=("Segoe UI",10,"bold")).pack(side="left",padx=(0,8))
        tk.Label(fb,text="fx",bg=fb.cget("bg"),fg=P["muted"],
                  font=("Segoe UI",10,"italic")).pack(side="left")
        self._formula_var=tk.StringVar()
        self._formula_entry=ttk.Entry(fb,textvariable=self._formula_var,
                                       font=("Segoe UI",10))
        self._formula_entry.pack(side="left",fill="x",expand=True,padx=6)
        self._formula_entry.bind("<Return>",self._sheet_formula_enter)
        tk.Frame(parent,bg=P["border"],height=1).pack(fill="x")

        # grid
        outer=tk.Frame(parent,bg=self._bg)
        outer.pack(fill="both",expand=True)
        self.sheet_canvas=tk.Canvas(outer,bg="white",highlightthickness=0)
        sh_h=ttk.Scrollbar(outer,orient="horizontal",command=self.sheet_canvas.xview)
        sh_v=ttk.Scrollbar(outer,orient="vertical",  command=self.sheet_canvas.yview)
        self.sheet_canvas.configure(xscrollcommand=sh_h.set,yscrollcommand=sh_v.set)
        sh_h.pack(side="bottom",fill="x")
        sh_v.pack(side="right", fill="y")
        self.sheet_canvas.pack(side="left",fill="both",expand=True)
        self.sheet_canvas.bind("<Configure>",lambda e:self._sheet_draw())
        self.sheet_canvas.bind("<Button-1>",self._sheet_click)
        self.sheet_canvas.bind("<Double-Button-1>",self._sheet_edit)
        parent.bind("<Control-f>",lambda e:self._sheet_find_replace())
        parent.bind("<Control-f>",lambda e:self._sheet_find_replace())
        parent.bind("<Control-F>",lambda e:self._sheet_find_replace())

        # ── sheet tab strip (Excel-style tabs at bottom) ──────────────────
        self._sheet_tab_frame = tk.Frame(parent, bg="#1A2233")
        self._sheet_tab_frame.pack(fill="x", side="bottom")
        self._sheet_tabs = [{"name":"Sheet 1","data":{}}]
        self._sheet_tab_idx = 0
        self._sheet_refresh_tabs()

    # ══════════════════════════════════════════════════════════════════════════
    #  SLIDES TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_slides(self, parent:tk.Frame):
        P=PALETTE
        pw=tk.PanedWindow(parent,orient="horizontal",bg=self._bg,sashwidth=5,
                          sashrelief="flat")
        pw.pack(fill="both",expand=True)

        # ── left: slide sorter ────────────────────────────────────────────────
        sorter=tk.Frame(pw,bg="#1A2233",width=190)
        pw.add(sorter,minsize=150)
        sorter.pack_propagate(False)

        # header
        hdr=tk.Frame(sorter,bg="#0F172A"); hdr.pack(fill="x")
        tk.Label(hdr,text="🖼  Slides",bg="#0F172A",fg="#E2E8F0",
                  font=("Segoe UI",11,"bold")).pack(side="left",padx=12,pady=10)

        # slide list
        lb_frame=tk.Frame(sorter,bg="#1A2233"); lb_frame.pack(fill="both",expand=True,padx=4,pady=4)
        self.slide_lb=tk.Listbox(lb_frame,bg="#1E293B",fg="#E2E8F0",
                                  selectbackground="#3B82F6",selectforeground="#FFFFFF",
                                  font=("Segoe UI",10),relief="flat",bd=0,
                                  activestyle="none",exportselection=False,
                                  highlightthickness=0)
        self.slide_lb.pack(fill="both",expand=True)
        self.slide_lb.bind("<<ListboxSelect>>",self._slide_select)

        # sorter buttons
        sf=tk.Frame(sorter,bg="#0F172A",pady=6); sf.pack(fill="x",padx=6,pady=(0,6))
        for t,fn,tip in [("＋","_slide_add","New"),("⎘","_slide_duplicate","Duplicate"),
                          ("✕","_slide_delete","Delete"),("↑","_slide_move_up","Up"),
                          ("↓","_slide_move_down","Down")]:
            b=tk.Label(sf,text=t,bg="#1E293B",fg="#E2E8F0",
                       font=("Segoe UI",12),padx=8,pady=4,cursor="hand2",relief="flat")
            b.pack(side="left",padx=2)
            b.bind("<Enter>",lambda e,w=b:w.configure(bg="#3B82F6"))
            b.bind("<Leave>",lambda e,w=b:w.configure(bg="#1E293B"))
            b.bind("<Button-1>",lambda e,m=fn: getattr(self,m)())
        # helper wrappers so the lambda above works cleanly
        self._slide_move_up   = lambda: self._slide_move(-1)
        self._slide_move_down = lambda: self._slide_move(1)

        # ── center: canvas + editor ───────────────────────────────────────────
        center=tk.Frame(pw,bg="#0D1117")
        pw.add(center,minsize=420)

        # slide preview canvas
        self.slide_canvas=tk.Canvas(center,bg="#0D1117",highlightthickness=0)
        self.slide_canvas.pack(fill="both",expand=True,padx=12,pady=(12,6))
        self.slide_canvas.bind("<Configure>",lambda e:self._slide_redraw())

        # content editor with visible header
        ed_header=tk.Frame(center,bg="#1E293B")
        ed_header.pack(fill="x",padx=12,pady=(0,2))
        tk.Label(ed_header,text="✏️  Slide content",bg="#1E293B",fg="#94A3B8",
                  font=("Segoe UI",8,"bold")).pack(side="left",padx=8,pady=4)
        self.slide_editor=ScrolledText(center,height=6,wrap="word",
                                        font=("Segoe UI",11),bg="#1E2D40",
                                        fg="#E2E8F0",relief="flat",bd=0,
                                        insertbackground="#3B82F6")
        self.slide_editor.pack(fill="x",padx=12,pady=(0,4))
        self.slide_editor.bind("<<Modified>>",self._slide_text_changed)

        # layout selector row
        lc=tk.Frame(center,bg="#0D1117"); lc.pack(fill="x",padx=12,pady=(0,8))
        tk.Label(lc,text="Layout:",bg="#0D1117",fg="#64748B",
                  font=("Segoe UI",8)).pack(side="left")
        self._slide_layout=tk.StringVar(value="Title + Content")
        ttk.Combobox(lc,textvariable=self._slide_layout,width=18,
                     values=["Title + Content","Title only","Blank",
                              "Two columns","Image + Text","Quote","Section header",
                              "Comparison","Title + Two content","Agenda"],
                     state="readonly").pack(side="left",padx=8)
        # theme color
        tk.Label(lc,text="Background:",bg="#0D1117",fg="#64748B",
                  font=("Segoe UI",8)).pack(side="left",padx=(12,0))
        self._slide_theme=tk.StringVar(value="#1E2D40")
        ttk.Entry(lc,textvariable=self._slide_theme,width=9,
                  font=("Segoe UI",9)).pack(side="left",padx=4)
        tk.Label(lc,text=" → ",bg="#0D1117",fg="#64748B").pack(side="left")
        b=tk.Label(lc,text="Apply",bg="#3B82F6",fg="#FFF",
                   font=("Segoe UI",9),padx=8,pady=3,cursor="hand2")
        b.pack(side="left")
        b.bind("<Button-1>",lambda e:self._slide_apply_theme())

        # ── right: speaker notes ─────────────────────────────────────────────
        notes_area=tk.Frame(pw,bg="#0F172A",width=230)
        pw.add(notes_area,minsize=180)
        notes_area.pack_propagate(False)

        nf_hdr=tk.Frame(notes_area,bg="#0F172A"); nf_hdr.pack(fill="x")
        tk.Label(nf_hdr,text="🗒  Speaker notes",bg="#0F172A",fg="#E2E8F0",
                  font=("Segoe UI",10,"bold")).pack(padx=12,pady=10,anchor="w")
        self.notes_editor=ScrolledText(notes_area,wrap="word",font=("Segoe UI",10),
                                        bg="#1E293B",fg="#CBD5E1",
                                        relief="flat",bd=0,
                                        insertbackground="#3B82F6")
        self.notes_editor.pack(fill="both",expand=True,padx=8,pady=(0,8))
        self.notes_editor.bind("<<Modified>>",self._notes_changed)

        # ── slide stats bar ───────────────────────────────────────────────────
        stats=tk.Frame(notes_area,bg="#0F172A")
        stats.pack(fill="x",padx=8,pady=(0,4))
        self._slide_stat=tk.StringVar(value="1 slide")
        tk.Label(stats,textvariable=self._slide_stat,bg="#0F172A",fg="#475569",
                  font=("Segoe UI",8)).pack(side="left")

        self._slide_refresh_list()

    # ══════════════════════════════════════════════════════════════════════════
    #  VIDEO TAB  (fully embedded, no separate window)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_video(self, parent:tk.Frame):
        P=PALETTE
        # dark cinema background
        VBGD = "#0D1117"
        VBGS = "#161B22"
        VBGB = "#1C2333"
        VFGA = "#E6EDF3"
        VFGM = "#8B949E"
        VACC = "#3B82F6"

        pw=tk.PanedWindow(parent,orient="horizontal",bg=VBGD,sashwidth=5,
                          sashrelief="flat")
        pw.pack(fill="both",expand=True)

        # ── left: tracks + clips ─────────────────────────────────────────────
        left=tk.Frame(pw,bg=VBGD,width=240)
        pw.add(left,minsize=190)
        left.pack_propagate(False)

        tk.Label(left,text="🎬  Tracks",bg=VBGD,fg=VFGA,
                  font=("Segoe UI",11,"bold")).pack(anchor="w",padx=10,pady=(10,4))
        self._vid_track_lb=tk.Listbox(left,bg=VBGS,fg=VFGA,
                                       selectbackground=VACC,selectforeground="#FFF",
                                       font=("Segoe UI",9),relief="flat",bd=0,
                                       activestyle="none",exportselection=False,
                                       height=7,highlightthickness=0)
        self._vid_track_lb.pack(fill="x",padx=6,pady=(0,4))
        self._vid_track_lb.bind("<<ListboxSelect>>",self._video_on_track_select)

        tr_btns=tk.Frame(left,bg=VBGD); tr_btns.pack(fill="x",padx=6,pady=(0,6))
        for txt,cmd,col in [("🔇 Mute",self._video_mute_track,VBGS),
                              ("🔒 Lock",self._video_lock_track,VBGS),
                              ("✕ Remove",self._video_remove_track,"#7F1D1D")]:
            b=tk.Label(tr_btns,text=txt,bg=col,fg=VFGA,
                       font=("Segoe UI",8),padx=6,pady=3,cursor="hand2")
            b.pack(side="left",padx=1)
            b.bind("<Button-1>",lambda e,c=cmd:c())

        tk.Frame(left,bg="#2D3748",height=1).pack(fill="x",padx=6,pady=4)
        tk.Label(left,text="📎  Clips in track",bg=VBGD,fg=VFGA,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=10)
        self._vid_clip_lb=tk.Listbox(left,bg=VBGS,fg=VFGA,
                                      selectbackground=VACC,selectforeground="#FFF",
                                      font=("Segoe UI",9),relief="flat",bd=0,
                                      activestyle="none",exportselection=False,
                                      highlightthickness=0)
        self._vid_clip_lb.pack(fill="both",expand=True,padx=6,pady=(4,4))
        self._vid_clip_lb.bind("<<ListboxSelect>>",self._video_on_clip_select)

        # ── center: preview + timeline ────────────────────────────────────────
        mid=tk.Frame(pw,bg=VBGD)
        pw.add(mid,minsize=420)

        # preview area with header
        prev_hdr=tk.Frame(mid,bg="#111827"); prev_hdr.pack(fill="x")
        tk.Label(prev_hdr,text="▶  Preview",bg="#111827",fg=VFGM,
                  font=("Segoe UI",8,"bold")).pack(side="left",padx=10,pady=4)
        self._vid_status=tk.StringVar(value="Add clips to begin")
        tk.Label(prev_hdr,textvariable=self._vid_status,bg="#111827",fg=VFGM,
                  font=("Segoe UI",8)).pack(side="right",padx=10)

        self._vid_preview=tk.Canvas(mid,bg="#0A0F1A",highlightthickness=0,height=260)
        self._vid_preview.pack(fill="x",padx=0,pady=0)
        self._vid_preview_img=None

        # transport controls
        tr2=tk.Frame(mid,bg="#111827"); tr2.pack(fill="x",padx=0,pady=0)
        self._vid_play_btn=tk.Label(tr2,text="▶  Play",bg=VACC,fg="#FFF",
                                     font=("Segoe UI",10,"bold"),
                                     padx=20,pady=6,cursor="hand2")
        self._vid_play_btn.pack(side="left",padx=4,pady=4)
        self._vid_play_btn.bind("<Button-1>",lambda e:self._video_toggle_play())
        for sym,tip in [("⏮","First"),("⏭","Last")]:
            b=tk.Label(tr2,text=sym,bg=VBGS,fg=VFGA,font=("Segoe UI",14),
                       padx=8,pady=4,cursor="hand2")
            b.pack(side="left",padx=2,pady=4)

        # timeline with colored track rows
        tl_frame=tk.Frame(mid,bg=VBGD)
        tl_frame.pack(fill="both",expand=True)

        # timeline header label
        tl_hdr=tk.Frame(tl_frame,bg="#111827"); tl_hdr.pack(fill="x")
        tk.Label(tl_hdr,text="🕐  Timeline",bg="#111827",fg=VFGM,
                  font=("Segoe UI",8,"bold")).pack(side="left",padx=10,pady=3)

        self._tl_canvas=tk.Canvas(tl_frame,bg="#0F1923",highlightthickness=0)
        tl_h=ttk.Scrollbar(tl_frame,orient="horizontal",command=self._tl_canvas.xview)
        tl_v=ttk.Scrollbar(tl_frame,orient="vertical",  command=self._tl_canvas.yview)
        self._tl_canvas.configure(xscrollcommand=tl_h.set,yscrollcommand=tl_v.set)
        tl_h.pack(side="bottom",fill="x")
        tl_v.pack(side="right",fill="y")
        self._tl_canvas.pack(side="left",fill="both",expand=True)
        self._tl_canvas.bind("<Configure>",lambda e:self._video_draw_timeline())
        self._tl_canvas.bind("<Button-1>",self._tl_click)

        # ── right: clip inspector ─────────────────────────────────────────────
        right=tk.Frame(pw,bg=VBGD,width=260)
        pw.add(right,minsize=210)
        right.pack_propagate(False)

        nb=ttk.Notebook(right)
        nb.pack(fill="both",expand=True,padx=4,pady=4)
        clip_tab=tk.Frame(nb,bg=self._bg)
        grade_tab=tk.Frame(nb,bg=self._bg)
        cap_tab=tk.Frame(nb,bg=self._bg)
        nb.add(clip_tab,  text="✂️ Clip")
        nb.add(grade_tab, text="🎨 Color")
        nb.add(cap_tab,   text="💬 Captions")

        # Clip tab
        self._vid_clip_name=tk.StringVar(value="Select a clip")
        tk.Label(clip_tab,textvariable=self._vid_clip_name,bg=self._bg,fg=self._fg,
                  font=("Segoe UI",9,"bold"),wraplength=220).pack(anchor="w",padx=8,pady=(8,4))
        self._vid_start=tk.StringVar(value="0"); self._vid_end=tk.StringVar(value="")
        self._vid_speed=tk.DoubleVar(value=1.0); self._vid_vol=tk.DoubleVar(value=1.0)
        self._vid_opac=tk.DoubleVar(value=1.0); self._vid_muted=tk.BooleanVar(value=False)
        self._vid_trans=tk.StringVar(value="Cut"); self._vid_filter=tk.StringVar(value="None")
        cf=tk.Frame(clip_tab,bg=self._bg); cf.pack(fill="x",padx=8)
        cf.columnconfigure(1,weight=1)
        for row,(lbl,var,kind) in enumerate([
            ("Trim start",self._vid_start,"entry"),("Trim end",self._vid_end,"entry"),
            ("Speed ×",self._vid_speed,"spin"),("Volume",self._vid_vol,"spin"),
            ("Opacity",self._vid_opac,"spin"),
        ]):
            tk.Label(cf,text=lbl,bg=self._bg,fg=P["muted"],font=("Segoe UI",8)).grid(
                row=row,column=0,sticky="w",pady=2)
            if kind=="entry":
                ttk.Entry(cf,textvariable=var,width=10).grid(row=row,column=1,sticky="ew",pady=1)
            else:
                ttk.Spinbox(cf,from_=0.0,to=4.0,increment=0.05,
                             textvariable=var,width=8).grid(row=row,column=1,sticky="w",pady=1)
        ttk.Checkbutton(clip_tab,text="Mute clip",variable=self._vid_muted).pack(anchor="w",padx=8,pady=2)
        tk.Label(clip_tab,text="Transition",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",padx=8)
        ttk.Combobox(clip_tab,textvariable=self._vid_trans,
                     values=["Cut","Fade","Dissolve","Slide left","Zoom in","Zoom out","Blur"],
                     state="readonly").pack(fill="x",padx=8,pady=(0,4))
        tk.Label(clip_tab,text="Filter",bg=self._bg,fg=P["muted"],
                  font=("Segoe UI",8)).pack(anchor="w",padx=8)
        ttk.Combobox(clip_tab,textvariable=self._vid_filter,
                     values=["None","Grayscale","Sepia","Vignette","Vintage",
                              "Sharpen","Blur","Brightness+","Contrast+","Cool","Warm"],
                     state="readonly").pack(fill="x",padx=8,pady=(0,6))
        ttk.Button(clip_tab,text="✔ Apply clip",command=self._video_apply_clip).pack(
            fill="x",padx=8,pady=2)
        ttk.Button(clip_tab,text="👁 Preview",command=self._video_preview_selected).pack(
            fill="x",padx=8)

        # Color grading tab
        tk.Label(grade_tab,text="🎨 Color grading",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=(8,4))
        self._grade_vars={}
        for name in ("brightness","contrast","saturation","hue","temperature"):
            tk.Label(grade_tab,text=name.capitalize(),bg=self._bg,fg=P["muted"],
                      font=("Segoe UI",8)).pack(anchor="w",padx=8)
            v=tk.DoubleVar(value=0.0); self._grade_vars[name]=v
            tk.Scale(grade_tab,variable=v,from_=-100,to=100,orient="horizontal",
                      resolution=1,bg=self._bg,fg=self._fg,
                      highlightthickness=0,troughcolor=P["border"],
                      activebackground=P["accent"]).pack(fill="x",padx=8,pady=(0,2))
        ttk.Button(grade_tab,text="✔ Apply grade",command=self._video_apply_grade).pack(
            fill="x",padx=8,pady=6)
        ttk.Button(grade_tab,text="↺ Reset",command=self._video_reset_grade).pack(
            fill="x",padx=8)

        # Captions tab
        tk.Label(cap_tab,text="💬 Add caption",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=(8,4))
        self._cap_text=tk.Text(cap_tab,height=4,wrap="word",bg=self._surface,
                                fg=self._fg,relief="flat",bd=1,font=("Segoe UI",10))
        self._cap_text.pack(fill="x",padx=8,pady=4)
        self._cap_start=tk.DoubleVar(value=0.0); self._cap_end=tk.DoubleVar(value=3.0)
        for lbl,var in [("Start (s)",self._cap_start),("End (s)",self._cap_end)]:
            tk.Label(cap_tab,text=lbl,bg=self._bg,fg=P["muted"],
                      font=("Segoe UI",8)).pack(anchor="w",padx=8)
            ttk.Spinbox(cap_tab,from_=0,to=9999,increment=0.1,
                         textvariable=var,width=10).pack(anchor="w",padx=8,pady=(0,4))
        ttk.Button(cap_tab,text="＋ Add caption",command=self._video_add_caption_entry).pack(
            fill="x",padx=8,pady=4)
        self._cap_list_lb=tk.Listbox(cap_tab,bg=self._surface,fg=self._fg,
                                      selectbackground=P["accent"],selectforeground="#FFF",
                                      font=("Segoe UI",9),relief="flat",bd=0,
                                      exportselection=False,height=6)
        self._cap_list_lb.pack(fill="both",expand=True,padx=8)
        ttk.Button(cap_tab,text="✕ Delete caption",command=self._video_del_caption).pack(
            fill="x",padx=8,pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    #  ANIMATION TAB  (fully embedded, no separate window)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_animation(self, parent:tk.Frame):
        P=PALETTE
        # animation studio colors
        ABG  = "#111318"   # main bg
        ABGS = "#1A1F2B"   # surface
        ABGB = "#232836"   # button bg
        AFGA = "#E2E8F0"   # primary text
        AFGM = "#6B7280"   # muted
        AACC = "#3B82F6"   # accent blue

        pw=tk.PanedWindow(parent,orient="horizontal",bg=ABG,sashwidth=5,
                          sashrelief="flat")
        pw.pack(fill="both",expand=True)

        # ── tools column ─────────────────────────────────────────────────────
        tools=tk.Frame(pw,bg=ABG,width=195)
        pw.add(tools,minsize=165)
        tools.pack_propagate(False)

        nb_tools=ttk.Notebook(tools)
        nb_tools.pack(fill="both",expand=True)
        tool_tab  =tk.Frame(nb_tools,bg=ABG)
        layer_tab =tk.Frame(nb_tools,bg=ABG)
        nb_tools.add(tool_tab,  text="🖌 Tools")
        nb_tools.add(layer_tab, text="⧉ Layers")

        # ── Tools sub-tab ────────────────────────────────────────────────────
        # tool buttons grid (icon + name)
        tk.Label(tool_tab,text="Drawing tool",bg=ABG,fg=AFGA,
                  font=("Segoe UI",9,"bold")).pack(anchor="w",padx=8,pady=(8,4))
        self._anim_tool=tk.StringVar(value="Brush")
        TOOL_ICONS = {
        "Select":"↖","Brush":"🖌","Pencil":"✏️","Line":"╱",
            "Rectangle":"▭","Ellipse":"◯","Fill":"🪣","Text":"T","Eraser":"⌫"
        }
        tools_grid=tk.Frame(tool_tab,bg=ABG); tools_grid.pack(fill="x",padx=6,pady=(0,4))
        for i,t in enumerate(("Select","Brush","Pencil","Line","Rectangle","Ellipse","Fill","Text","Eraser")):
            icon=TOOL_ICONS.get(t,"•")
            cell=tk.Frame(tools_grid,bg=ABGB,relief="flat",bd=0,cursor="hand2")
            cell.grid(row=i//3,column=i%3,padx=2,pady=2,sticky="ew")
            tools_grid.columnconfigure(i%3,weight=1)
            ik=tk.Label(cell,text=icon,bg=ABGB,fg=AFGA,font=("Segoe UI",14),pady=2)
            ik.pack()
            nl=tk.Label(cell,text=t,bg=ABGB,fg=AFGM,font=("Segoe UI",7))
            nl.pack(pady=(0,3))
            def _sel(ev,tool=t,frm=cell):
                self._anim_tool.set(tool)
                # reset all cells
                for child in tools_grid.winfo_children():
                    child.configure(bg=ABGB)
                    for sub in child.winfo_children(): sub.configure(bg=ABGB)
                frm.configure(bg=AACC)
                for sub in frm.winfo_children(): sub.configure(bg=AACC)
            for w in (cell,ik,nl):
                w.bind("<Button-1>",_sel)

        tk.Frame(tool_tab,bg=ABGB,height=1).pack(fill="x",padx=8,pady=6)

        # brush controls
        bc=tk.Frame(tool_tab,bg=ABG); bc.pack(fill="x",padx=8)
        bc.columnconfigure(1,weight=1)
        tk.Label(bc,text="Size",bg=ABG,fg=AFGM,font=("Segoe UI",8)).grid(row=0,column=0,sticky="w",pady=2)
        self._anim_brush=tk.IntVar(value=5)
        ttk.Spinbox(bc,from_=1,to=120,textvariable=self._anim_brush,width=5).grid(row=0,column=1,sticky="ew",pady=1)
        tk.Label(bc,text="Opacity",bg=ABG,fg=AFGM,font=("Segoe UI",8)).grid(row=1,column=0,sticky="w",pady=2)
        self._anim_opacity=tk.DoubleVar(value=1.0)
        ttk.Spinbox(bc,from_=0.05,to=1.0,increment=0.05,textvariable=self._anim_opacity,width=5).grid(row=1,column=1,sticky="ew",pady=1)
        self._anim_smooth=tk.BooleanVar(value=True)
        ttk.Checkbutton(bc,text="Smooth",variable=self._anim_smooth).grid(row=2,column=0,columnspan=2,sticky="w",pady=2)

        tk.Frame(tool_tab,bg=ABGB,height=1).pack(fill="x",padx=8,pady=4)

        # color swatch + palette
        tk.Label(tool_tab,text="Color",bg=ABG,fg=AFGM,font=("Segoe UI",8)).pack(anchor="w",padx=8)
        self._anim_color_swatch=tk.Label(tool_tab,bg="#315C8A",
                                          width=12,height=2,relief="flat",cursor="hand2")
        self._anim_color_swatch.pack(anchor="w",padx=8,pady=(2,4))
        self._anim_color_swatch.bind("<Button-1>",lambda e:self._anim_pick_color())

        pal_frame=tk.Frame(tool_tab,bg=ABG); pal_frame.pack(anchor="w",padx=8,pady=(0,4))
        for i,c in enumerate(["#000000","#FFFFFF","#FF0000","#00CC00","#0000FF",
                               "#FFFF00","#FF8800","#315C8A","#7C3AED","#F59E0B",
                               "#E74C3C","#3B82F6","#10B981","#8B5CF6","#F97316",
                               "#6B7280","#1E293B","#F8FAFC","#DC2626","#16A34A"]):
            b=tk.Label(pal_frame,bg=c,width=2,height=1,relief="flat",cursor="hand2",
                       highlightbackground="#444",highlightthickness=1)
            b.grid(row=i//5,column=i%5,padx=1,pady=1)
            b.bind("<Button-1>",lambda e,col=c:self._anim_set_color(col))

        tk.Frame(tool_tab,bg=ABGB,height=1).pack(fill="x",padx=8,pady=4)

        # onion skin
        tk.Label(tool_tab,text="🧅 Onion skin",bg=ABG,fg=AFGM,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=8)
        onion_row=tk.Frame(tool_tab,bg=ABG); onion_row.pack(fill="x",padx=8,pady=2)
        onion_row.columnconfigure(1,weight=1)
        self._onion_prev=tk.IntVar(value=1)
        self._onion_next=tk.IntVar(value=0)
        tk.Label(onion_row,text="Prev",bg=ABG,fg=AFGM,font=("Segoe UI",8)).grid(row=0,column=0,sticky="w")
        ttk.Spinbox(onion_row,from_=0,to=5,textvariable=self._onion_prev,width=4,command=self._anim_redraw).grid(row=0,column=1,sticky="w",padx=4)
        tk.Label(onion_row,text="Next",bg=ABG,fg=AFGM,font=("Segoe UI",8)).grid(row=1,column=0,sticky="w")
        ttk.Spinbox(onion_row,from_=0,to=5,textvariable=self._onion_next,width=4,command=self._anim_redraw).grid(row=1,column=1,sticky="w",padx=4)

        tk.Frame(tool_tab,bg=ABGB,height=1).pack(fill="x",padx=8,pady=4)
        self._anim_grid=tk.BooleanVar(value=False)
        ttk.Checkbutton(tool_tab,text="📐 Show grid",variable=self._anim_grid,
                        command=self._anim_redraw).pack(anchor="w",padx=8)
        self._anim_zoom=1.0
        zr=tk.Frame(tool_tab,bg=ABG); zr.pack(anchor="w",padx=8,pady=4)
        tk.Label(zr,text="Zoom:",bg=ABG,fg=AFGM,font=("Segoe UI",8)).pack(side="left")
        ttk.Button(zr,text="−",width=2,command=lambda:self._anim_zoom_by(-0.25)).pack(side="left",padx=1)
        self._anim_zoom_lbl=tk.Label(zr,text="100%",bg=ABG,fg=AFGA,
                                      font=("Segoe UI",9),width=5)
        self._anim_zoom_lbl.pack(side="left")
        ttk.Button(zr,text="+",width=2,command=lambda:self._anim_zoom_by(0.25)).pack(side="left",padx=1)

        # ── Layers sub-tab ───────────────────────────────────────────────────
        tk.Label(layer_tab,text="⧉  Layers",bg=ABG,fg=AFGA,
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=(8,4))
        self._anim_layer_lb=tk.Listbox(layer_tab,bg=ABGS,fg=AFGA,
                                        selectbackground=AACC,selectforeground="#FFF",
                                        font=("Segoe UI",9),relief="flat",bd=0,
                                        activestyle="none",exportselection=False,
                                        highlightthickness=0)
        self._anim_layer_lb.pack(fill="both",expand=True,padx=4)
        self._anim_layer_lb.bind("<<ListboxSelect>>",self._anim_on_layer_select)
        lb_btns=tk.Frame(layer_tab,bg=ABG); lb_btns.pack(fill="x",padx=4,pady=4)
        for t,fn,tip in [("＋",self._anim_add_layer,"New layer"),
                          ("⎘",self._anim_dup_layer,"Duplicate"),
                          ("✕",self._anim_del_layer,"Delete"),
                          ("↑",lambda:self._anim_move_layer(-1),"Move up"),
                          ("↓",lambda:self._anim_move_layer(1),"Move down")]:
            b=tk.Label(lb_btns,text=t,bg=ABGB,fg=AFGA,font=("Segoe UI",12),
                       padx=7,pady=3,cursor="hand2")
            b.pack(side="left",padx=1)
            b.bind("<Button-1>",lambda e,c=fn:c())
        tk.Label(layer_tab,text="Opacity",bg=ABG,fg=AFGM,font=("Segoe UI",8)).pack(anchor="w",padx=8,pady=(4,0))
        self._anim_layer_opac=tk.DoubleVar(value=1.0)
        ttk.Spinbox(layer_tab,from_=0,to=1.0,increment=0.05,
                    textvariable=self._anim_layer_opac,width=6).pack(anchor="w",padx=8,pady=(0,4))
        ttk.Button(layer_tab,text="Apply opacity",
                    command=self._anim_apply_layer_opacity).pack(fill="x",padx=4,pady=2)
        lv_row=tk.Frame(layer_tab,bg=ABG); lv_row.pack(fill="x",padx=4,pady=2)
        ttk.Button(lv_row,text="👁 Visible",command=self._anim_toggle_visible).pack(side="left",padx=1)
        ttk.Button(lv_row,text="🔒 Lock",command=self._anim_toggle_lock).pack(side="left",padx=1)

        # ── canvas area ───────────────────────────────────────────────────────
        stage=tk.Frame(pw,bg=ABG)
        pw.add(stage,minsize=400)

        canv_outer=tk.Frame(stage,bg="#1A1A2E")
        canv_outer.pack(fill="both",expand=True)
        self._anim_canvas=tk.Canvas(canv_outer,bg="#1A1A2E",highlightthickness=0)
        ac_h=ttk.Scrollbar(canv_outer,orient="horizontal",command=self._anim_canvas.xview)
        ac_v=ttk.Scrollbar(canv_outer,orient="vertical",  command=self._anim_canvas.yview)
        self._anim_canvas.configure(xscrollcommand=ac_h.set,yscrollcommand=ac_v.set)
        ac_h.pack(side="bottom",fill="x")
        ac_v.pack(side="right",fill="y")
        self._anim_canvas.pack(side="left",fill="both",expand=True)
        self._anim_canvas.bind("<ButtonPress-1>",   self._anim_down)
        self._anim_canvas.bind("<B1-Motion>",       self._anim_drag)
        self._anim_canvas.bind("<ButtonRelease-1>", self._anim_up)
        self._anim_canvas.bind("<Configure>",       lambda e:self._anim_redraw())
        self._anim_start_pt=None; self._anim_cur_pts:list=[]
        self._anim_undo_stack:list=[]; self._anim_redo_stack:list=[]

        # transport row with proper styled buttons
        tr=tk.Frame(stage,bg="#111827"); tr.pack(fill="x",padx=0,pady=0)
        transport_btns=[
            ("⏮","first"),("◀","prev"),("▶ Play","play"),("▶","next"),("⏭","last")
        ]
        self._anim_play_btn=None
        for sym,action in transport_btns:
            is_play=(action=="play")
            b=tk.Label(tr,text=sym,
                       bg=AACC if is_play else ABGB,
                       fg="#FFF",
                       font=("Segoe UI",10,"bold" if is_play else "normal"),
                       padx=14 if is_play else 8,pady=5,cursor="hand2")
            b.pack(side="left",padx=2,pady=4)
            if is_play:
                self._anim_play_btn=b
                b.bind("<Button-1>",lambda e:self._anim_play_toggle())
            elif action=="first":
                b.bind("<Button-1>",lambda e:self._anim_go_frame(-self._anim_frame))
            elif action=="prev":
                b.bind("<Button-1>",lambda e:self._anim_go_frame(-1))
            elif action=="next":
                b.bind("<Button-1>",lambda e:self._anim_go_frame(1))
            elif action=="last":
                b.bind("<Button-1>",lambda e:self._anim_go_frame(
                    self._anim_project["total_frames"]-self._anim_frame-1))

        # scrubber + frame counter
        scr=tk.Frame(stage,bg=ABG); scr.pack(fill="x",padx=8,pady=(2,4))
        tk.Label(scr,text="Frame:",bg=ABG,fg=AFGM,font=("Segoe UI",8)).pack(side="left")
        self._anim_scrubber=tk.Scale(scr,from_=0,to=23,orient="horizontal",
                                      resolution=1,command=self._anim_scrub,
                                      bg=ABG,fg=AFGA,troughcolor="#2D3748",
                                      highlightthickness=0,
                                      activebackground=AACC,length=300,
                                      showvalue=False)
        self._anim_scrubber.pack(side="left",fill="x",expand=True)
        self._anim_frame_lbl=tk.Label(scr,text="1 / 24",bg=ABG,fg=AFGA,
                                       font=("Segoe UI",9,"bold"),width=8)
        self._anim_frame_lbl.pack(side="left",padx=6)

        # ── frame list column ─────────────────────────────────────────────────
        frame_list_col=tk.Frame(pw,bg=ABG,width=185)
        pw.add(frame_list_col,minsize=145)
        frame_list_col.pack_propagate(False)

        fl_hdr=tk.Frame(frame_list_col,bg="#0F172A"); fl_hdr.pack(fill="x")
        tk.Label(fl_hdr,text="🎞  Frames",bg="#0F172A",fg=AFGA,
                  font=("Segoe UI",10,"bold")).pack(padx=10,pady=8,anchor="w")

        self._anim_frame_lb=tk.Listbox(frame_list_col,bg=ABGS,fg=AFGA,
                                        selectbackground=AACC,selectforeground="#FFF",
                                        font=("Courier New",9),relief="flat",bd=0,
                                        activestyle="none",exportselection=False,
                                        highlightthickness=0)
        self._anim_frame_lb.pack(fill="both",expand=True,padx=4,pady=(0,4))
        self._anim_frame_lb.bind("<<ListboxSelect>>",self._anim_on_frame_select)

        fb2=tk.Frame(frame_list_col,bg="#0F172A",pady=4); fb2.pack(fill="x",padx=4)
        for t,fn,tip in [("＋",self._anim_add_frame,"Add"),
                          ("⎘",self._anim_duplicate_frame,"Dup"),
                          ("✕",self._anim_delete_frame,"Del"),
                          ("↑",lambda:self._anim_move_frame(-1),"Up"),
                          ("↓",lambda:self._anim_move_frame(1),"Down"),
                          ("⌫",self._anim_clear_frame,"Clear")]:
            b=tk.Label(fb2,text=t,bg=ABGB,fg=AFGA,font=("Segoe UI",11),
                       padx=5,pady=3,cursor="hand2")
            b.pack(side="left",padx=1)
            b.bind("<Enter>",lambda e,w=b:w.configure(bg=AACC))
            b.bind("<Leave>",lambda e,w=b:w.configure(bg=ABGB))
            b.bind("<Button-1>",lambda e,c=fn:c())

        # keyboard shortcuts for animation
        parent.bind("<Control-z>",lambda e:self._anim_undo())
        parent.bind("<Control-y>",lambda e:self._anim_redo())
        parent.bind("<Left>",lambda e:self._anim_go_frame(-1))
        parent.bind("<Right>",lambda e:self._anim_go_frame(1))


    # ══════════════════════════════════════════════════════════════════════════
    #  DOCUMENT EDITING  —  core
    # ══════════════════════════════════════════════════════════════════════════
    def _store(self):
        if hasattr(self,"editor"):
            self.doc.pages[self.current].text=self.editor.get("1.0","end-1c")

    def _load_page(self):
        if not hasattr(self,"editor"): return
        self.loading=True
        p=self.doc.pages[self.current]
        self.editor.delete("1.0","end")
        self.editor.insert("1.0",p.text)
        self.editor._studio_images=[]
        for el in p.elements:
            if el.get("type")=="image" and Path(el.get("path","")).exists():
                try:
                    from PIL import Image,ImageTk
                    im=Image.open(el["path"]); im.thumbnail((520,360))
                    photo=ImageTk.PhotoImage(im)
                    self.editor.image_create(el.get("position","1.0"),image=photo)
                    self.editor._studio_images.append(photo)
                except Exception: pass
        self.editor.edit_modified(False)
        self.loading=False
        self.titlevar.set(self.doc.title)
        self.headvar.set(self.doc.header)
        self.footvar.set(self.doc.footer)
        self.langvar.set(self.doc.content_language)
        self.numbers_var.set(self.doc.page_numbers)
        self._theme_var.set(self.doc.theme)
        self._pgs.set(self.doc.page_size)
        self._orient.set(self.doc.orientation)
        self._margin.set(self.doc.margin)
        self._chrome(); self._refresh_pages(); self._refresh_elements()
        self._redraw_doc(); self._resize()
        self.after_idle(self._update_word_count)

    def _snapshot(self):
        if self.loading: return
        self._store()
        s=json.dumps(self.doc.payload(),ensure_ascii=False,sort_keys=True)
        if not self.history or s!=self.history[-1]:
            self.history.append(s); self.history=self.history[-80:]; self.future.clear()

    def _restore(self,s:str):
        self.loading=True
        self.doc=Document.load(json.loads(s))
        self.current=min(self.current,len(self.doc.pages)-1)
        self._load_page(); self.loading=False; self._dirt()

    def _changed(self,e=None):
        if not self.loading and self.editor.edit_modified():
            self._store(); self.editor.edit_modified(False)
            self._dirt(); self.after_idle(self._snapshot)

    def _dirt(self):
        self.dirty=True
        self.title("● "+self.doc.title+" — "+APP)

    def _update_word_count(self,e=None):
        """Update live word/char counter in status bar."""
        if not hasattr(self,"editor") or not hasattr(self,"word_count_var"):
            return
        try:
            text=self.editor.get("1.0","end-1c")
            words=len(re.findall(r"\b\w+\b",text,flags=re.UNICODE))
            chars=len(text)
            self.word_count_var.set(f"  {words:,} words  •  {chars:,} chars  ")
        except Exception:
            pass

    def _undo(self):
        self._store()
        if len(self.history)>1:
            self.future.append(self.history.pop()); self._restore(self.history[-1])
            self.status.set("Undone")

    def _redo(self):
        if self.future:
            s=self.future.pop(); self.history.append(s); self._restore(s)
            self.status.set("Redone")

    def _refresh_pages(self):
        if not hasattr(self, 'pages_lb'): return
        self.pages_lb.delete(0,"end")
        for i,p in enumerate(self.doc.pages):
            mark=" •" if p.text.strip() else ""
            self.pages_lb.insert("end",f"  Page {i+1}{mark}")
        self.pages_lb.selection_set(self.current)
        self.page_status.set(f"Page {self.current+1}/{len(self.doc.pages)}  {self.zoom.get()}%")

    def _refresh_elements(self,e=None):
        if not hasattr(self,"elements_lb"): return
        self.elements_lb.delete(0,"end")
        for i,line in enumerate(self.editor.get("1.0","end-1c").splitlines(),1):
            if line.strip():
                self.elements_lb.insert("end",f"¶{i}: {line.strip()[:36]}")

    def _element_focus(self,e=None):
        s=self.elements_lb.curselection()
        if s: self.editor.mark_set("insert",f"{s[0]+1}.0"); self.editor.focus_set()

    def _chrome(self):
        self.header_lbl.configure(text=self.doc.header,fg=self.doc.theme)
        foot=self.doc.footer
        if self.doc.page_numbers:
            foot=(foot+"    •    " if foot else "")+"Page "+str(self.current+1)
        self.footer_lbl.configure(text=foot)

    def _resize(self):
        if not hasattr(self,"canvas"): return
        ratio=self.zoom.get()/100
        w,h=page_size(self.doc.page_size,self.doc.orientation=="Landscape")
        w=int(w*ratio); h=int(h*ratio)
        self.editor.configure(font=(getattr(self,"family",tk.StringVar(value="Segoe UI")).get()
                                     if hasattr(self,"family") else "Segoe UI",
                                     max(8,round(12*ratio))))
        self.paper.configure(width=w,height=h)
        self.canvas.itemconfigure(self.paperid,width=w,height=h)
        self.canvas.coords(self.paperid,max(20,(self.canvas.winfo_width()-w)//2),20)
        self.canvas.configure(scrollregion=(0,0,max(w+45,self.canvas.winfo_width()),h+45))
        self._refresh_pages()

    def _page_select(self,e=None):
        s=self.pages_lb.curselection()
        if s and s[0]!=self.current:
            self._store(); self.current=s[0]; self._load_page()

    def _page_change(self,n:int):
        self._store()
        self.current=max(0,min(len(self.doc.pages)-1,self.current+n))
        self._load_page()

    def _add_page(self):
        self._store(); self.doc.pages.insert(self.current+1,Page())
        self.current+=1; self._load_page(); self._dirt(); self._snapshot()

    def _duplicate_page(self):
        self._store(); p=copy.deepcopy(self.doc.pages[self.current]); p.id=new_id()
        self.doc.pages.insert(self.current+1,p); self.current+=1
        self._load_page(); self._dirt(); self._snapshot()

    def _delete_page(self):
        if len(self.doc.pages)==1:
            messagebox.showinfo(APP,"A document must have at least one page."); return
        if messagebox.askyesno(APP,"Delete this page?"):
            self.doc.pages.pop(self.current)
            self.current=min(self.current,len(self.doc.pages)-1)
            self._load_page(); self._dirt(); self._snapshot()

    def _move_page(self,n:int):
        j=self.current+n
        if 0<=j<len(self.doc.pages):
            self.doc.pages[self.current],self.doc.pages[j]=\
                self.doc.pages[j],self.doc.pages[self.current]
            self.current=j; self._load_page(); self._dirt(); self._snapshot()

    # ── text helpers ──────────────────────────────────────────────────────────
    def _selected(self):
        try: return self.editor.index("sel.first"),self.editor.index("sel.last")
        except tk.TclError: return "insert wordstart","insert wordend"

    def _tag(self,name:str):
        a,b=self._selected()
        active=name in self.editor.tag_names("insert")
        if active: self.editor.tag_remove(name,a,b)
        else:       self.editor.tag_add(name,a,b)
        fam=self.family.get() if hasattr(self,"family") else "Segoe UI"
        sz =self.fsize.get()  if hasattr(self,"fsize")  else 12
        self.editor.tag_configure("bold",   font=(fam,sz,"bold"))
        self.editor.tag_configure("italic", font=(fam,sz,"italic"))
        self.editor.tag_configure("under",  underline=True)
        self.editor.tag_configure("strike", overstrike=True)
        self.editor.tag_configure("super",  offset=6,font=(fam,max(6,sz-3)))
        self.editor.tag_configure("sub",    offset=-4,font=(fam,max(6,sz-3)))
        self._dirt(); self._snapshot()

    def _font_apply(self):
        a,b=self._selected()
        fam=self.family.get(); sz=self.fsize.get()
        tag=f"f_{fam}_{sz}"
        self.editor.tag_configure(tag,font=(fam,sz)); self.editor.tag_add(tag,a,b)
        self._dirt(); self._snapshot()

    def _text_color(self):
        c=colorchooser.askcolor(parent=self)[1]
        if c:
            a,b=self._selected()
            self.editor.tag_configure(f"fg{c}",foreground=c)
            self.editor.tag_add(f"fg{c}",a,b); self._dirt(); self._snapshot()

    def _highlight(self):
        c=colorchooser.askcolor("#FFF3A3",parent=self)[1]
        if c:
            a,b=self._selected()
            self.editor.tag_configure(f"bg{c}",background=c)
            self.editor.tag_add(f"bg{c}",a,b); self._dirt(); self._snapshot()

    def _align(self,where:str):
        a,b=self._selected(); tag=f"align_{where}"
        self.editor.tag_configure(tag,justify=where)
        self.editor.tag_add(tag,a+" linestart",b+" lineend")
        self._dirt(); self._snapshot()

    def _style(self,name:str):
        s=self.doc.styles.get(name,{})
        if not s: return
        a,b=self._selected(); tag=f"style_{name.replace(' ','_')}"
        wt="bold" if s.get("bold") else "normal"
        sl="italic" if s.get("italic") else "roman"
        opts=dict(font=(s["font"],s["size"],wt,sl),foreground=s["color"])
        if name=="Code": opts["background"]="#F3F4F6"
        self.editor.tag_configure(tag,**opts)
        self.editor.tag_add(tag,a+" linestart",b+" lineend")
        self._dirt(); self._snapshot()

    def _clear_format(self):
        a,b=self._selected()
        for t in self.editor.tag_names(): self.editor.tag_remove(t,a,b)
        self._dirt(); self._snapshot()

    def _insert(self,text:str):
        self.editor.insert("insert",text); self.editor.focus_set()
        self._store(); self._dirt(); self._snapshot()

    def _heading(self):
        self._insert("\nHeading\n")
        self.editor.tag_add("hd","insert-2l linestart","insert-1l lineend")
        self.editor.tag_configure("hd",font=("Segoe UI",18,"bold"),foreground=self.doc.theme)

    def _checklist(self): self._insert("\n☐ Task one\n☐ Task two\n☐ Task three\n")
    def _flashcard(self): self._insert("\nFLASHCARD\nFront: Question\nBack: Answer\n")

    def _equation(self):
        t=simpledialog.askstring(APP,"Equation:",initialvalue="x\u00b2 + y\u00b2 = z\u00b2",parent=self)
        if t: self._insert("\n  " + t + "\n")

    def _answer_lines(self):
        n=simpledialog.askinteger(APP,"Number of answer lines",initialvalue=5,minvalue=1,maxvalue=30,parent=self)
        if n: self._insert("\n"+"".join("________________________________________________________________\n" for _ in range(n)))

    def _doc_toc(self):
        # Generate a table of contents from Heading 1/2/3 styles.
        text = self.editor.get("1.0", "end-1c")
        lines = text.splitlines()
        entries = []
        idx = "1.0"
        for ln in lines:
            if not ln.strip():
                continue
            pos = self.editor.search(ln.strip(), idx, stopindex="end")
            if pos:
                tags = self.editor.tag_names(pos)
                level = None
                for t in tags:
                    if t == "style_Heading_1": level = 1
                    elif t == "style_Heading_2": level = 2
                    elif t == "style_Heading_3": level = 3
                if level and ln.strip():
                    entries.append((level, ln.strip()))
                idx = pos + "+1c"
        if not entries:
            messagebox.showinfo(APP, "No headings found. Apply Heading 1/2/3 styles first.")
            return
        toc = "Table of Contents\n" + ("=" * 24) + "\n"
        for level, title in entries:
            indent = "  " * (level - 1)
            toc = toc + indent + "- " + title + "\n"
        toc = toc + "\n"
        self._insert(toc)

    def _doc_mail_merge(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[("CSV", "*.csv")])
        if not p: return
        try:
            import csv as _csv
            with open(p, newline="", encoding="utf-8") as f:
                rows = list(_csv.DictReader(f))
        except Exception as e:
            messagebox.showerror(APP, "Could not read CSV: " + str(e))
            return
        if not rows:
            messagebox.showinfo(APP, "CSV is empty.")
            return
        template = self.editor.get("1.0", "end-1c")
        out = ""
        for i, row in enumerate(rows):
            merged = template
            for k, v in row.items():
                val = str(v) if v is not None else ""
                merged = merged.replace("{{" + k + "}}", val)
                merged = merged.replace("<<" + k + ">>", val)
            out = out + merged
            if i < len(rows) - 1:
                out = out + "\n\n" + ("=" * 60) + "\n\n"
        self._insert(out)
        messagebox.showinfo(APP, "Merged " + str(len(rows)) + " record(s).")

    def _doc_footnote(self):
        txt = simpledialog.askstring(APP, "Footnote text:", parent=self)
        if not txt: return
        marker = str(getattr(self, "_footnote_counter", 0) + 1)
        self._footnote_counter = getattr(self, "_footnote_counter", 0) + 1
        a, b = self._selected()
        pos = a if a else self.editor.index("insert")
        self.editor.insert(pos, marker)
        try:
            self.editor.tag_add("sup", pos, pos + ("+" + str(len(marker)) + "c"))
            self.editor.tag_configure("sup", font=("Segoe UI", 8), offset=6)
        except Exception:
            pass
        end = self.editor.index("end-1c")
        self.editor.insert(end, "\n" + marker + "  " + txt + "\n")
        try:
            self.editor.tag_add("footnote", end, end + ("+" + str(len(marker) + 2 + len(txt)) + "c"))
            self.editor.tag_configure("footnote", font=("Segoe UI", 9), foreground="#64748B")
        except Exception:
            pass
        self._dirt(); self._snapshot()
        self.status.set("Footnote " + marker + " added.")

    def _table(self):
        r=simpledialog.askinteger(APP,"Rows",initialvalue=3,minvalue=1,maxvalue=30,parent=self)
        c=simpledialog.askinteger(APP,"Columns",initialvalue=3,minvalue=1,maxvalue=12,parent=self)
        if r and c:
            header=" | ".join(f"Col {i+1}" for i in range(c))
            sep="-+-".join("--------" for _ in range(c))
            rows="\n".join(" | ".join("        " for _ in range(c)) for _ in range(r-1))
            self._insert("\n" + header + "\n" + sep + "\n" + rows + "\n")

    def _insert_list(self,bullet:str):
        lines=[]
        if bullet=="1.":
            for i in range(1,4): lines.append(f"{i}. Item {i}")
        else:
            for i in range(1,4): lines.append(f"{bullet} Item {i}")
        self._insert(""+"".join(lines)+"\n")

    def _insert_date(self):
        import datetime; self._insert(datetime.date.today().strftime("%B %d, %Y"))

    def _hyperlink(self):
        url=simpledialog.askstring(APP,"URL:",initialvalue="https://",parent=self)
        lbl=simpledialog.askstring(APP,"Link text:",initialvalue=url or "",parent=self)
        if url and lbl: self._insert(f"[{lbl}]({url})")

    def _insert_symbol(self):
        syms="© ® ™ § ¶ • ★ ☆ ✓ ✗ ← → ↑ ↓ ↔ ⇒ ∞ ≠ ≤ ≥ ± × ÷ √ π α β γ Σ Ω"
        win=tk.Toplevel(self); win.title("Insert symbol"); win.transient(self)
        f=ttk.Frame(win); f.pack(padx=10,pady=10)
        for i,s in enumerate(syms.split()):
            ttk.Button(f,text=s,width=3,
                        command=lambda c=s:(self._insert(c),win.destroy())
                       ).grid(row=i//12,column=i%12,padx=1,pady=1)

    def _image(self):
        p=filedialog.askopenfilename(title="Insert image",
            filetypes=[("Images","*.png *.jpg *.jpeg *.gif *.webp *.bmp")])
        if p: self._insert_image_at_cursor(p)

    def _insert_image_at_cursor(self,p:str):
        try:
            from PIL import Image,ImageTk
            im=Image.open(p); im.thumbnail((520,360))
            photo=ImageTk.PhotoImage(im)
            self.editor.image_create("insert",image=photo)
            self.editor._studio_images=getattr(self.editor,"_studio_images",[])+[photo]
            self.editor.insert("insert","\n")
        except Exception: self._insert("\n[Image: " + Path(p).name + "]\n")
        self.doc.pages[self.current].elements.append(
            {"type":"image","path":str(p),"position":self.editor.index("insert")})
        self._store(); self._dirt(); self._snapshot()

    def _info(self,e=None):
        self.sel_info.set("Cursor: "+self.editor.index("insert")+"  — Select text to format.")

    def _properties(self):
        self.doc.title=self.titlevar.get().strip() or "Untitled document"
        self.doc.header=self.headvar.get(); self.doc.footer=self.footvar.get()
        self.doc.content_language=self.langvar.get()
        self.doc.page_numbers=self.numbers_var.get()
        self._chrome(); self._dirt(); self._snapshot()

    def _theme_apply(self):
        v=self._theme_var.get()
        if re.fullmatch(r"#[0-9a-fA-F]{6}",v):
            self.doc.theme=v; self._chrome(); self._dirt(); self._snapshot()
        else: messagebox.showwarning(APP,"Use a hex color like #315C8A.")

    def _pick_theme(self):
        c=colorchooser.askcolor(self.doc.theme,parent=self)[1]
        if c: self._theme_var.set(c); self._theme_apply()

    def _layout_apply(self):
        self.doc.page_size=self._pgs.get(); self.doc.orientation=self._orient.get()
        self.doc.margin=self._margin.get(); self._resize(); self._dirt(); self._snapshot()

    def _zoom_to(self,n:int): self.zoom.set(max(40,min(200,n))); self._resize()
    def _toggle_dark(self):
        self.preferences["ui_theme"]="Light" if self._dark else "Dark"
        self._apply_theme(); self._save_prefs()
        self._full_ui_refresh()

    def _full_ui_refresh(self):
        """Rebuild the sidebar and current toolbar to apply theme colors live."""
        P = PALETTE
        # ── Re-color sidebar ────────────────────────────────────────────────
        if hasattr(self, "_sidebar"):
            # walk every widget in sidebar and update bg/fg
            def _recolor(widget):
                try:
                    cls = widget.winfo_class()
                    if cls in ("Frame","Label"):
                        cur_bg = widget.cget("bg")
                        # sidebar widgets keep their dark sidebar colors —
                        # only update the ones that previously used theme colors
                        if cur_bg not in (P["sidebar"],P["sidebar_hl"],
                                          P["sidebar_sel"],"#2D4460","#0F172A"):
                            widget.configure(bg=self._bg)
                    for child in widget.winfo_children():
                        _recolor(child)
                except Exception:
                    pass
            _recolor(self._sidebar)

        # ── Rebuild current toolbar ─────────────────────────────────────────
        if hasattr(self, "_toolbar_frame"):
            self._rebuild_toolbar(self._active_dept)

        # ── Update main window bg ───────────────────────────────────────────
        self.configure(bg=self._bg)

        # ── Update status bar ───────────────────────────────────────────────
        # status bar is at the bottom — re-color its labels
        for widget in self.winfo_children():
            try:
                if isinstance(widget, tk.Frame) and widget.cget("bg") in (
                        P["sidebar"], "#0F172A", "#1E293B"):
                    pass  # keep sidebar/status colors
            except Exception:
                pass

    # ── drawing ───────────────────────────────────────────────────────────────
    def _draw_visibility(self):
        if not hasattr(self,"drawing"): return
        if self.draw_tool.get()=="Select": self.drawing.place_forget()
        else: self.drawing.place(relx=0,rely=0,relwidth=1,relheight=1)

    def _pick_draw_color(self):
        c=colorchooser.askcolor(self._draw_color_var.get(),parent=self)[1]
        if c: self._draw_color_var.set(c)

    def _draw_start(self,e):
        if self.draw_tool.get()=="Select": return
        self._dstart=(e.x,e.y); self._dpts=[(e.x,e.y)]; self._dpreview=None

    def _draw_move(self,e):
        if not hasattr(self,"_dstart") or self.draw_tool.get() in ("Select","Eraser"): return
        x,y=self._dstart; self._dpts.append((e.x,e.y))
        t=self.draw_tool.get(); c="#F8D34B" if t=="Highlighter" else self._draw_color_var.get()
        w=9 if t=="Highlighter" else 2
        if self._dpreview: self.drawing.delete(self._dpreview)
        flat=sum(([a,b] for a,b in self._dpts),[])
        if t in ("Pencil","Highlighter"): self._dpreview=self.drawing.create_line(*flat,fill=c,width=w,smooth=True)
        elif t in ("Line","Arrow"):       self._dpreview=self.drawing.create_line(x,y,e.x,e.y,fill=c,width=w,arrow="last" if t=="Arrow" else "none")
        elif t=="Rectangle":              self._dpreview=self.drawing.create_rectangle(x,y,e.x,e.y,outline=c,width=w)
        elif t=="Ellipse":                self._dpreview=self.drawing.create_oval(x,y,e.x,e.y,outline=c,width=w)

    def _draw_end(self,e):
        if not hasattr(self,"_dstart"): return
        t=self.draw_tool.get()
        if t=="Eraser":
            near=self.drawing.find_closest(e.x,e.y)
            if near: self.drawing.delete(near[0]); self.doc.pages[self.current].drawings=[]
        elif t!="Select":
            self.doc.pages[self.current].drawings.append(
                {"tool":t,"pts":self._dpts,
                 "color":"#F8D34B" if t=="Highlighter" else self._draw_color_var.get()})
            self._dirt(); self._snapshot()
        del self._dstart

    def _redraw_doc(self):
        if not hasattr(self,"drawing"): return
        self.drawing.delete("all")
        for d in self.doc.pages[self.current].drawings:
            p=d["pts"]; t=d["tool"]; c=d["color"]
            if len(p)<2: continue
            x,y=p[0]; xx,yy=p[-1]; flat=sum(([a,b] for a,b in p),[])
            if t in ("Pencil","Highlighter"): self.drawing.create_line(*flat,fill=c,width=9 if t=="Highlighter" else 2,smooth=True)
            elif t in ("Line","Arrow"):        self.drawing.create_line(x,y,xx,yy,fill=c,width=2,arrow="last" if t=="Arrow" else "none")
            elif t=="Rectangle":               self.drawing.create_rectangle(x,y,xx,yy,outline=c,width=2)
            elif t=="Ellipse":                 self.drawing.create_oval(x,y,xx,yy,outline=c,width=2)

    def _clear_drawings(self):
        if messagebox.askyesno(APP,"Clear all drawings on this page?"):
            self.doc.pages[self.current].drawings=[]; self._redraw_doc(); self._dirt(); self._snapshot()

    # ══════════════════════════════════════════════════════════════════════════
    #  DESIGN CANVAS  methods
    # ══════════════════════════════════════════════════════════════════════════
    def _dp(self)->Optional[DesignPage]:
        pages=self.design_proj.pages
        return pages[self.design_page] if pages else None

    def _dc_redraw(self):
        if not hasattr(self, 'dcanvas'): return
        c=self.dcanvas; c.delete("all"); c._img_refs=[]
        pg=self._dp()
        if pg is None: return
        cw=max(200,c.winfo_width()); ch=max(100,c.winfo_height())
        pw=self.design_proj.width; ph=self.design_proj.height
        scale=min((cw-40)/max(1,pw),(ch-40)/max(1,ph))
        ox=int((cw-pw*scale)/2); oy=int((ch-ph*scale)/2)
        self._dc_scale=scale; self._dc_ox=ox; self._dc_oy=oy
        # snap grid overlay
        if getattr(self,"_design_snap",False):
            gs=int(20*scale)
            if gs>8:
                for gx in range(0,int(pw*scale),gs):
                    c.create_line(ox+gx,oy,ox+gx,oy+int(ph*scale),
                                   fill="#334155",dash=(2,4))
                for gy in range(0,int(ph*scale),gs):
                    c.create_line(ox,oy+gy,ox+int(pw*scale),oy+gy,
                                   fill="#334155",dash=(2,4))
        # shadow
        c.create_rectangle(ox+4,oy+4,ox+int(pw*scale)+4,oy+int(ph*scale)+4,
                            fill="#888888",outline="",stipple="gray25")
        c.create_rectangle(ox,oy,ox+int(pw*scale),oy+int(ph*scale),
                            fill=pg.background,outline=PALETTE["border"])
        for obj in pg.objects:
            if not obj.opacity: continue
            x0=ox+int(obj.x*scale); y0=oy+int(obj.y*scale)
            x1=x0+int(obj.w*scale); y1=y0+int(obj.h*scale)
            fill=obj.fill or ""; stroke=obj.stroke or ""
            sw=max(1,int(obj.stroke_w*scale)); k=obj.kind
            if k=="rect":
                c.create_rectangle(x0,y0,x1,y1,fill=fill,outline=stroke,width=sw)
            elif k=="ellipse":
                c.create_oval(x0,y0,x1,y1,fill=fill,outline=stroke,width=sw)
            elif k=="triangle":
                cx,cy=(x0+x1)//2,(y0+y1)//2
                c.create_polygon(cx,y0,x1,y1,x0,y1,fill=fill,outline=stroke,width=sw)
            elif k=="star":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(10):
                    ang=_m.radians(i*36-90); r=rx if i%2==0 else rx*0.4
                    rr=ry if i%2==0 else ry*0.4
                    pts.append((cx+_m.cos(ang)*r, cy+_m.sin(ang)*rr))
                flat=[v for pt in pts for v in pt]
                c.create_polygon(*flat,fill=fill,outline=stroke,width=sw)
            elif k=="triangle":
                cx,cy=(x0+x1)//2,(y0+y1)//2
                c.create_polygon(cx,y0,x1,y1,x0,y1,fill=fill,outline=stroke,width=sw)
            elif k=="star":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(10):
                    ang=_m.radians(i*36-90); r=rx if i%2==0 else rx*0.4
                    rr=ry if i%2==0 else ry*0.4
                    pts.append((cx+_m.cos(ang)*r, cy+_m.sin(ang)*rr))
                flat=[v for pt in pts for v in pt]
                c.create_polygon(*flat,fill=fill,outline=stroke,width=sw)
            elif k=="pentagon":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(5):
                    ang=_m.radians(i*72-90)
                    pts.append((cx+_m.cos(ang)*rx, cy+_m.sin(ang)*ry))
                flat=[v for pt in pts for v in pt]
                c.create_polygon(*flat,fill=fill,outline=stroke,width=sw)
            elif k=="hexagon":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(6):
                    ang=_m.radians(i*60-90)
                    pts.append((cx+_m.cos(ang)*rx, cy+_m.sin(ang)*ry))
                flat=[v for pt in pts for v in pt]
                c.create_polygon(*flat,fill=fill,outline=stroke,width=sw)
            elif k in ("line","arrow"):
                c.create_line(x0,y0,x1,y1,fill=fill or "#000",width=sw,
                               arrow="last" if k=="arrow" else "none")
            elif k=="text":
                sz=max(6,int(obj.font_sz*scale))
                wt="bold" if obj.font_bold else "normal"
                sl="italic" if obj.font_it else "roman"
                c.create_text(x0,y0,text=obj.text,fill=obj.text_color or "#000",
                               font=(obj.font_fam,sz,wt,sl),anchor="nw")
            elif k=="image":
                try:
                    from PIL import Image,ImageTk
                    im=Image.open(obj.image_path)
                    im=im.resize((max(1,int(obj.w*scale)),max(1,int(obj.h*scale))),Image.LANCZOS)
                    photo=ImageTk.PhotoImage(im); c._img_refs.append(photo)
                    c.create_image(x0,y0,image=photo,anchor="nw")
                except Exception:
                    c.create_rectangle(x0,y0,x1,y1,fill="#DDD",outline="#AAA")
                    c.create_text((x0+x1)//2,(y0+y1)//2,text=Path(obj.image_path).name[:20],fill="#666")
            if obj is self._sel_obj:
                c.create_rectangle(x0-3,y0-3,x1+3,y1+3,outline="#F59E0B",width=2,dash=(5,3))
                c.create_rectangle(x1-5,y1-5,x1+5,y1+5,fill="#F59E0B",outline="")

    def _dc_hit(self,mx,my)->Optional[DesignObject]:
        pg=self._dp()
        if pg is None: return None
        scale=getattr(self,"_dc_scale",1.0); ox=getattr(self,"_dc_ox",0); oy=getattr(self,"_dc_oy",0)
        px=(mx-ox)/scale; py=(my-oy)/scale
        for obj in reversed(pg.objects):
            if obj.x<=px<=obj.x+obj.w and obj.y<=py<=obj.y+obj.h: return obj
        return None

    def _dc_down(self,e):
        self._sel_obj=self._dc_hit(e.x,e.y); self._drag_start=(e.x,e.y)
        self._drag_orig=(self._sel_obj.x,self._sel_obj.y) if self._sel_obj else (0,0)
        if self._sel_obj: self._dp_load_obj(self._sel_obj)
        self._dc_redraw()

    def _dc_drag(self,e):
        if self._sel_obj is None or self._drag_start is None: return
        dx=e.x-self._drag_start[0]; dy=e.y-self._drag_start[1]
        scale=getattr(self,"_dc_scale",1.0)
        nx=self._drag_orig[0]+dx/scale
        ny=self._drag_orig[1]+dy/scale
        if getattr(self,"_design_snap",False):
            gs=20; nx=round(nx/gs)*gs; ny=round(ny/gs)*gs
        self._sel_obj.x=nx
        self._sel_obj.y=ny
        self._dc_redraw()

    def _dc_up(self,e): self._drag_start=None

    def _dp_load_obj(self,obj:DesignObject):
        self._dp_kind.set(obj.kind); self._dp_x.set(round(obj.x,1)); self._dp_y.set(round(obj.y,1))
        self._dp_w.set(round(obj.w,1)); self._dp_h.set(round(obj.h,1)); self._dp_opac.set(obj.opacity)
        self._dp_fill.set(obj.fill or ""); self._dp_stroke.set(obj.stroke or "")
        self._dp_text.set(obj.text or ""); self._dp_fsize.set(obj.font_sz)
        self._dp_bold.set(obj.font_bold); self._dp_italic.set(obj.font_it)
        self._dp_tcol.set(obj.text_color or "#000000")

    def _dp_apply(self):
        obj=self._sel_obj
        if obj is None: return
        obj.x=self._dp_x.get(); obj.y=self._dp_y.get()
        obj.w=max(1,self._dp_w.get()); obj.h=max(1,self._dp_h.get())
        obj.fill=self._dp_fill.get(); obj.stroke=self._dp_stroke.get()
        obj.opacity=max(0,min(1,self._dp_opac.get()))
        obj.text=self._dp_text.get(); obj.font_sz=self._dp_fsize.get()
        obj.font_bold=self._dp_bold.get(); obj.font_it=self._dp_italic.get()
        obj.text_color=self._dp_tcol.get(); self._dc_redraw()

    def _dp_pick_fill(self):
        c=colorchooser.askcolor(self._dp_fill.get() or "#315C8A",parent=self)[1]
        if c: self._dp_fill.set(c); (self._sel_obj and setattr(self._sel_obj,"fill",c)); self._dc_redraw()

    def _dp_pick_tcol(self):
        c=colorchooser.askcolor(self._dp_tcol.get() or "#000000",parent=self)[1]
        if c: self._dp_tcol.set(c)

    def _design_add_text(self):
        t=simpledialog.askstring("Add text","Text:",parent=self)
        if not t: return
        pg=self._dp()
        if pg is None: return
        obj=DesignObject(kind="text",x=100,y=100,w=300,h=70,fill="",text=t,
                          text_color="#1E293B",font_sz=32,font_bold=True)
        pg.objects.append(obj); self._sel_obj=obj; self._dc_redraw()

    def _design_add_shape(self,kind:str):
        pg=self._dp()
        if pg is None: return
        obj=DesignObject(kind=kind,x=80,y=80,w=240,h=140,fill=self.doc.theme,stroke="",stroke_w=2)
        pg.objects.append(obj); self._sel_obj=obj; self._dc_redraw()

    def _design_add_image(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        if not p: return
        pg=self._dp()
        if pg is None: return
        obj=DesignObject(kind="image",x=50,y=50,w=300,h=200,image_path=p)
        pg.objects.append(obj); self._sel_obj=obj; self._dc_redraw()

    def _design_duplicate(self):
        if self._sel_obj:
            pg=self._dp(); new=copy.deepcopy(self._sel_obj)
            new.id=new_id(); new.x+=20; new.y+=20
            pg.objects.append(new); self._sel_obj=new; self._dc_redraw()

    def _design_delete(self):
        if self._sel_obj:
            pg=self._dp()
            pg.objects=[o for o in pg.objects if o is not self._sel_obj]
            self._sel_obj=None; self._dc_redraw()

    def _design_reorder(self,d:int):
        if self._sel_obj is None: return
        pg=self._dp(); objs=pg.objects
        i=next((i for i,o in enumerate(objs) if o is self._sel_obj),None)
        if i is None: return
        j=i+d
        if 0<=j<len(objs): objs[i],objs[j]=objs[j],objs[i]; self._dc_redraw()

    def _design_align(self,where:str):
        if self._sel_obj is None: return
        pw=self.design_proj.width; ph=self.design_proj.height; obj=self._sel_obj
        if where=="left":   obj.x=0
        elif where=="center": obj.x=(pw-obj.w)/2
        elif where=="right":  obj.x=pw-obj.w
        elif where=="top":    obj.y=0
        elif where=="middle": obj.y=(ph-obj.h)/2
        elif where=="bottom": obj.y=ph-obj.h
        self._dc_redraw()

    def _design_resize(self,w:int,h:int):
        self.design_proj.width=w; self.design_proj.height=h; self._dc_redraw()

    def _design_new(self):
        self.design_proj=DesignProject(); self.design_page=0; self._sel_obj=None; self._dc_redraw()

    def _design_save(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".json",
                                        filetypes=[("Design project","*.json")])
        if p:
            Path(p).write_text(json.dumps(self.design_proj.payload(),indent=2,ensure_ascii=False),encoding="utf-8")
            self.status.set(f"Design saved: {Path(p).name}")

    def _design_export_png(self):
        try: from PIL import Image,ImageDraw as PD,ImageFont
        except ImportError: messagebox.showinfo(APP,"PNG export needs Pillow.\npip install pillow"); return
        pg=self._dp()
        if pg is None: return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".png",filetypes=[("PNG","*.png")])
        if not p: return
        pw=self.design_proj.width; ph=self.design_proj.height
        im=Image.new("RGB",(pw,ph),pg.background); d=PD.Draw(im)
        for obj in pg.objects:
            x0,y0=int(obj.x),int(obj.y); x1,y1=x0+int(obj.w),y0+int(obj.h)
            fill=obj.fill or None; stroke=obj.stroke or None; sw=obj.stroke_w; k=obj.kind
            if k=="rect":   d.rectangle([x0,y0,x1,y1],fill=fill,outline=stroke,width=sw)
            elif k=="ellipse": d.ellipse([x0,y0,x1,y1],fill=fill,outline=stroke,width=sw)
            elif k=="triangle":
                d.polygon([(x0+x1)//2,y0,x1,y1,x0,y1],fill=fill,outline=stroke,width=sw)
            elif k=="star":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(10):
                    ang=_m.radians(i*36-90); r=rx if i%2==0 else rx*0.4
                    rr=ry if i%2==0 else ry*0.4
                    pts.append((cx+_m.cos(ang)*r, cy+_m.sin(ang)*rr))
                d.polygon(pts,fill=fill,outline=stroke,width=sw)
            elif k=="pentagon":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(5):
                    ang=_m.radians(i*72-90)
                    pts.append((cx+_m.cos(ang)*rx, cy+_m.sin(ang)*ry))
                d.polygon(pts,fill=fill,outline=stroke,width=sw)
            elif k=="hexagon":
                import math as _m
                cx,cy=(x0+x1)/2,(y0+y1)/2; rx,ry=(x1-x0)/2,(y1-y0)/2
                pts=[]
                for i in range(6):
                    ang=_m.radians(i*60-90)
                    pts.append((cx+_m.cos(ang)*rx, cy+_m.sin(ang)*ry))
                d.polygon(pts,fill=fill,outline=stroke,width=sw)
            elif k in ("line","arrow"): d.line([x0,y0,x1,y1],fill=fill or "#000",width=sw)
            elif k=="text":
                try:
                    fnt=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf" if obj.font_bold else "C:/Windows/Fonts/segoeui.ttf",max(8,obj.font_sz))
                except Exception:
                    fnt=ImageFont.load_default()
                d.text((x0,y0),obj.text or "",fill=obj.text_color or "#000",font=fnt)
            elif k=="image":
                try:
                    src=Image.open(obj.image_path).resize((max(1,int(obj.w)),max(1,int(obj.h))),Image.LANCZOS)
                    im.paste(src,(x0,y0))
                except Exception: pass
        im.save(p); self.status.set(f"Design exported: {Path(p).name}")

    def _design_export_svg(self):
        pg=self._dp()
        if pg is None: return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".svg",filetypes=[("SVG","*.svg")])
        if not p: return
        pw=self.design_proj.width; ph=self.design_proj.height
        lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}" height="{ph}">',
               f'<rect width="100%" height="100%" fill="{pg.background}"/>']
        for obj in pg.objects:
            x0,y0,w,h=int(obj.x),int(obj.y),int(obj.w),int(obj.h)
            fill=obj.fill or "none"; stroke=obj.stroke or "none"; k=obj.kind
            if k=="rect":
                lines.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{obj.stroke_w}"/>')
            elif k=="ellipse":
                cx,cy,rx,ry=x0+w//2,y0+h//2,w//2,h//2
                lines.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{obj.stroke_w}"/>')
            elif k=="triangle":
                cx=x0+w//2
                pts=f"{cx},{y0} {x1},{y1} {x0},{y1}"
                lines.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{obj.stroke_w}"/>')
            elif k=="star":
                import math as _m
                cx,cy=x0+w/2,y0+h/2; rx,ry=w/2,h/2
                pts=[]
                for i in range(10):
                    ang=_m.radians(i*36-90); r=rx if i%2==0 else rx*0.4
                    rr=ry if i%2==0 else ry*0.4
                    pts.append(f"{cx+_m.cos(ang)*r},{cy+_m.sin(ang)*rr}")
                lines.append(f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{obj.stroke_w}"/>')
            elif k=="pentagon":
                import math as _m
                cx,cy=x0+w/2,y0+h/2; rx,ry=w/2,h/2
                pts=[]
                for i in range(5):
                    ang=_m.radians(i*72-90)
                    pts.append(f"{cx+_m.cos(ang)*rx},{cy+_m.sin(ang)*ry}")
                lines.append(f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{obj.stroke_w}"/>')
            elif k=="hexagon":
                import math as _m
                cx,cy=x0+w/2,y0+h/2; rx,ry=w/2,h/2
                pts=[]
                for i in range(6):
                    ang=_m.radians(i*60-90)
                    pts.append(f"{cx+_m.cos(ang)*rx},{cy+_m.sin(ang)*ry}")
                lines.append(f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{obj.stroke_w}"/>')
            elif k=="text":
                wt="bold" if obj.font_bold else "normal"; sl="italic" if obj.font_it else "normal"
                lines.append(f'<text x="{x0}" y="{y0+obj.font_sz}" font-family="{obj.font_fam}" font-size="{obj.font_sz}" font-weight="{wt}" font-style="{sl}" fill="{obj.text_color or "#000"}">{html.escape(obj.text or "")}</text>')
        lines.append("</svg>")
        Path(p).write_text("\n".join(lines),encoding="utf-8"); self.status.set(f"SVG exported: {Path(p).name}")

    # ══════════════════════════════════════════════════════════════════════════
    #  SPREADSHEET  methods
    # ══════════════════════════════════════════════════════════════════════════
    def _sheet_key(self,row:int,col:int)->str:
        letters=""; c=col
        while True:
            letters=chr(65+c%26)+letters; c=c//26-1
            if c<0: break
        return f"{letters}{row+1}"

    def _col_index(self, s: str) -> int:
        s = s.upper(); r = 0
        for ch in s:
            r = r * 26 + ord(ch) - 64
        return r - 1

    def _sheet_draw(self):
        if not hasattr(self, 'sheet_canvas'): return
        c=self.sheet_canvas; c.delete("all")
        HDR=self._HDR; CW=self._COL_W; RH=self._ROW_H
        rows=self._ROWS; cols=self._COLS; P=PALETTE
        W=HDR+cols*CW; H=HDR+rows*RH
        c.configure(scrollregion=(0,0,W+20,H+20))
        c.create_rectangle(0,0,HDR,HDR,fill="#E2E8F0",outline="#CBD5E1")
        for col in range(cols):
            x=HDR+col*CW; letter=self._sheet_key(0,col)[:-1]
            c.create_rectangle(x,0,x+CW,HDR,fill="#E2E8F0",outline="#CBD5E1")
            c.create_text(x+CW//2,HDR//2,text=letter,font=("Segoe UI",9,"bold"),fill="#475467")
        sr,sc=self._sheet_sel
        for row in range(rows):
            y=HDR+row*RH
            c.create_rectangle(0,y,HDR,y+RH,fill="#E2E8F0",outline="#CBD5E1")
            c.create_text(HDR//2,y+RH//2,text=str(row+1),font=("Segoe UI",8,"bold"),fill="#475467")
            for col in range(cols):
                x=HDR+col*CW; key=self._sheet_key(row,col)
                cell=self._sheet_data.get(key,{}); bg=cell.get("bg","#FFFFFF")
                is_sel=(row==sr and col==sc)
                if is_sel: bg="#DBEAFE"
                c.create_rectangle(x,y,x+CW,y+RH,fill=bg,
                                    outline="#3B82F6" if is_sel else "#E2E8F0",
                                    width=2 if is_sel else 1)
                val=str(cell.get("value",""))
                if val:
                    fw="bold" if cell.get("bold") else "normal"
                    c.create_text(x+4,y+RH//2,text=val[:18],anchor="w",
                                   font=("Segoe UI",9,fw),fill=cell.get("fg","#1E293B"))

    def _sheet_click(self,e):
        HDR=self._HDR; CW=self._COL_W; RH=self._ROW_H
        if e.x<HDR or e.y<HDR: return
        col=(e.x-HDR)//CW; row=(e.y-HDR)//RH
        if 0<=row<self._ROWS and 0<=col<self._COLS:
            self._sheet_sel=(row,col); key=self._sheet_key(row,col)
            self._sheet_cell_ref.set(key)
            cell=self._sheet_data.get(key,{})
            self._formula_var.set(cell.get("formula") or cell.get("value",""))
            self._sheet_draw()

    def _sheet_edit(self,e):
        self._sheet_click(e); self._formula_entry.focus_set(); self._formula_entry.select_range(0,"end")

    def _sheet_formula_enter(self,e=None):
        row,col=self._sheet_sel; key=self._sheet_key(row,col)
        raw=self._formula_var.get(); cell=self._sheet_data.setdefault(key,{})
        if raw.startswith("="):
            cell["formula"]=raw; cell["value"]=self._eval_formula(raw[1:])
        else:
            cell["formula"]=""; cell["value"]=raw
        self._sheet_sel=(row,min(self._COLS-1,col+1)); self._sheet_draw()

    def _eval_formula(self,expr:str)->str:
        try:
            expr=expr.upper()
            m=re.match(r"SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                return str(sum(vals))
            m=re.match(r"AVERAGE\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                return str(round(sum(vals)/len(vals),4)) if vals else "0"
            m=re.match(r"COUNT\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                return str(len(vals))
            m=re.match(r"MAX\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                return str(max(vals)) if vals else "0"
            m=re.match(r"MIN\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                return str(min(vals)) if vals else "0"
            m=re.match(r"CONCATENATE\((.+)\)",expr)
            if m:
                args=[a.strip() for a in m.group(1).split(",")]
                out=""
                for a in args:
                    mm=re.match(r"([A-Z]+)(\d+)",a)
                    if mm:
                        v=self._sheet_data.get(self._sheet_key(int(mm.group(2))-1,self._col_index(mm.group(1))),{}).get("value","")
                        out+=str(v)
                    else:
                        out+=a.strip('"').strip("'")
                return out
            m=re.match(r"LEN\((.+)\)",expr)
            if m:
                a=m.group(1).strip()
                mm=re.match(r"([A-Z]+)(\d+)",a)
                if mm:
                    v=self._sheet_data.get(self._sheet_key(int(mm.group(2))-1,self._col_index(mm.group(1))),{}).get("value","")
                    return str(len(str(v)))
                return str(len(a.strip('"').strip("'")))
            m=re.match(r"UPPER\((.+)\)",expr)
            if m:
                a=m.group(1).strip()
                mm=re.match(r"([A-Z]+)(\d+)",a)
                if mm:
                    v=self._sheet_data.get(self._sheet_key(int(mm.group(2))-1,self._col_index(mm.group(1))),{}).get("value","")
                    return str(v).upper()
                return a.strip('"').strip("'").upper()
            m=re.match(r"LOWER\((.+)\)",expr)
            if m:
                a=m.group(1).strip()
                mm=re.match(r"([A-Z]+)(\d+)",a)
                if mm:
                    v=self._sheet_data.get(self._sheet_key(int(mm.group(2))-1,self._col_index(mm.group(1))),{}).get("value","")
                    return str(v).lower()
                return a.strip('"').strip("'").lower()
            m=re.match(r"VLOOKUP\((.+),([A-Z]+)(\d+):([A-Z]+)(\d+),(\d+)\)",expr)
            if m:
                key=m.group(1).strip().strip('"').strip("'")
                try: keyv=float(key)
                except Exception: keyv=None
                c1=self._col_index(m.group(2)); r1=int(m.group(3))-1
                c2=self._col_index(m.group(4)); r2=int(m.group(5))-1
                ci=int(m.group(6))-1
                for r in range(min(r1,r2),max(r1,r2)+1):
                    v=self._sheet_data.get(self._sheet_key(r,min(c1,c2)),{}).get("value","")
                    try: vv=float(v)
                    except Exception: vv=None
                    if (keyv is not None and vv==keyv) or (keyv is None and v==key):
                        col=min(c1,c2)+ci
                        res=self._sheet_data.get(self._sheet_key(r,col),{}).get("value","")
                        return res if res!="" else "0"
                return "#N/A"
            m=re.match(r"COUNTIF\(([A-Z]+)(\d+):([A-Z]+)(\d+),(.+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                crit=m.group(5).strip().strip('"').strip("'")
                try: c=float(crit)
                except Exception: c=None
                n=sum(1 for v in vals if (c is not None and v==c) or (c is None and str(v)==crit))
                return str(n)
            m=re.match(r"SUMIF\(([A-Z]+)(\d+):([A-Z]+)(\d+),(.+)\)",expr)
            if m:
                vals=self._range_vals(m.group(1),int(m.group(2))-1,m.group(3),int(m.group(4))-1)
                crit=m.group(5).strip().strip('"').strip("'")
                try: c=float(crit)
                except Exception: c=None
                return str(sum(v for v in vals if (c is not None and v==c) or (c is None and str(v)==crit)))
            m=re.match(r"IF\((.+),(.+),(.+)\)",expr)
            if m:
                cond=m.group(1).strip(); tv=m.group(2).strip(); fv=m.group(3).strip()
                try:
                    # support simple comparisons like A1>5, B2<=3, 4>2
                    mm=re.match(r"([A-Z]+)(\d+)\s*(>=|<=|==|!=|>|<)\s*(.+)",cond)
                    if mm:
                        _ci=0
                        for _ch in mm.group(1).upper(): _ci=_ci*26+ord(_ch)-64
                        _ci=_ci-1
                        v=self._sheet_data.get(self._sheet_key(int(mm.group(2))-1,_ci),{}).get("value","")
                        try: left=float(v)
                        except Exception: left=0.0
                        try: right=float(mm.group(4))
                        except Exception: right=0.0
                        op=mm.group(3)
                        ok={" >":left>right,">=":left>=right,"<":left<right,"<=":left<=right,"==":left==right,"!=":left!=right}.get(op,False)
                    else:
                        try: ok=float(cond)!=0
                        except Exception: ok=bool(cond)
                    def conv(x):
                        x=x.strip()
                        if x.startswith('"') and x.endswith('"'): return x.strip('"')
                        try: return float(x)
                        except Exception: return x
                    return str(conv(tv) if ok else conv(fv))
                except Exception: return "#ERR"
            safe=re.sub(r"[^0-9+\-*/()., ]","",expr)
            return str(eval(safe))  # noqa: S307
        except Exception: return "#ERR"

    def _range_vals(self,col1,row1,col2,row2)->list:
        def cidx(s):
            s=s.upper(); r=0
            for ch in s: r=r*26+ord(ch)-64
            return r-1
        c1=cidx(col1); c2=cidx(col2); vals=[]
        for r in range(min(row1,row2),max(row1,row2)+1):
            for co in range(min(c1,c2),max(c1,c2)+1):
                v=self._sheet_data.get(self._sheet_key(r,co),{}).get("value","")
                try: vals.append(float(v))
                except Exception: pass
        return vals

    def _sheet_new(self):
        if messagebox.askyesno(APP,"Clear spreadsheet?"):
            self._sheet_data.clear(); self._sheet_sel=(0,0); self._sheet_draw()

    def _sheet_open(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("CSV","*.csv"),("Excel","*.xlsx")])
        if not p: return
        try:
            if p.lower().endswith(".csv"):
                import csv
                with open(p,encoding="utf-8-sig",newline="") as f: rows=list(csv.reader(f))
            else:
                from openpyxl import load_workbook
                wb=load_workbook(p,data_only=True); ws=wb.active
                rows=[[str(x) if x is not None else "" for x in row] for row in ws.iter_rows(values_only=True)]
            self._sheet_data.clear()
            for ri,row in enumerate(rows):
                for ci,val in enumerate(row):
                    if val: self._sheet_data[self._sheet_key(ri,ci)]={"value":val}
            self._ROWS=max(self._ROWS,len(rows)); self._sheet_draw()
            self.status.set(f"Opened: {Path(p).name}")
        except Exception as exc: messagebox.showerror(APP,str(exc))

    def _sheet_save_csv(self):
        import csv
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p: return
        with open(p,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            for row in range(self._ROWS):
                w.writerow([self._sheet_data.get(self._sheet_key(row,col),{}).get("value","") for col in range(self._COLS)])
        self.status.set(f"CSV saved: {Path(p).name}")

    def _sheet_add_row(self):  self._ROWS+=1; self._sheet_draw()
    def _sheet_add_col(self):  self._COLS=min(26,self._COLS+1); self._sheet_draw()
    def _sheet_del_row(self):
        row,_=self._sheet_sel
        for col in range(self._COLS): self._sheet_data.pop(self._sheet_key(row,col),None)
        self._sheet_draw()
    def _sheet_bold(self):
        row,col=self._sheet_sel; key=self._sheet_key(row,col)
        cell=self._sheet_data.setdefault(key,{}); cell["bold"]=not cell.get("bold",False)
        self._sheet_draw()
    def _sheet_formula_help(self):
        messagebox.showinfo(APP,"Formulas start with =\n""=SUM(A1:B5)\n=AVERAGE(A1:A10)\n=COUNT(A1:A10)\n"
        "=MAX(A1:A10)\n=MIN(A1:A10)\n=COUNTIF(A1:A10,5)\n=SUMIF(A1:A10,5)\n"
         "=VLOOKUP(A1,A2:B10,2)\n=IF(A1>5,\"yes\",\"no\")\n=CONCATENATE(A1,B1)\n=LEN(A1)\n=UPPER(A1)\n=2+3*4\n\nPress Enter to confirm.")

    # ══════════════════════════════════════════════════════════════════════════
    #  SLIDES  methods
    # ══════════════════════════════════════════════════════════════════════════
    def _slide_refresh_list(self):
        self.slide_lb.delete(0,"end")
        for i,s in enumerate(self._slides):
            title=(s["text"].splitlines()[0] or "Slide")[:28]
            mark=" ◀" if i==self._cur_slide else ""
            self.slide_lb.insert("end",f"  {i+1:02d}  {title}{mark}")
        if self._cur_slide<self.slide_lb.size():
            self.slide_lb.selection_set(self._cur_slide)
        if hasattr(self,"_slide_stat"):
            n=len(self._slides)
            self._slide_stat.set(f"{n} slide{'s' if n!=1 else ''}  •  Slide {self._cur_slide+1}")

    def _slide_redraw(self):
        if not hasattr(self, 'slide_canvas'): return
        c=self.slide_canvas; c.delete("all")
        if not self._slides: return
        slide=self._slides[self._cur_slide]
        cw=max(200,c.winfo_width()); ch=max(100,c.winfo_height())
        bg=slide.get("background","#1E2D40")

        # background fill
        c.create_rectangle(0,0,cw,ch,fill=bg,outline="")

        # subtle gradient effect (horizontal lines getting slightly lighter)
        try:
            r=int(bg[1:3],16); g=int(bg[3:5],16); b=int(bg[5:7],16)
            for i in range(0,ch,4):
                factor=1.0+0.15*(i/ch)
                nr=min(255,int(r*factor)); ng=min(255,int(g*factor)); nb2=min(255,int(b*factor))
                shade=f"#{nr:02x}{ng:02x}{nb2:02x}"
                c.create_line(0,i,cw,i,fill=shade)
        except Exception:
            pass

        # accent bar at top (uses theme accent color)
        accent=slide.get("accent","#3B82F6")
        c.create_rectangle(0,0,cw,6,fill=accent,outline="")

        # slide layout
        layout=slide.get("layout","Title + Content")
        lines=slide["text"].splitlines()
        title=lines[0] if lines else "New Slide"
        body_lines=lines[1:] if len(lines)>1 else []
        body="\n".join(body_lines)

        # font sizes
        fsize_title=getattr(self,"_slide_font_size",None)
        title_sz=max(16,min(60,cw//18))
        if fsize_title:
            try: title_sz=max(12,min(80,int(fsize_title.get())*cw//800+12))
            except Exception: pass
        body_sz=max(10,min(28,cw//38))

        if layout=="Title only":
            c.create_text(cw//2,ch//2,text=title,fill="#FFFFFF",
                           font=("Segoe UI",title_sz,"bold"),
                           width=int(cw*0.82),justify="center")
        elif layout=="Blank":
            pass  # blank slide
        elif layout=="Quote":
            # large open-quote
            c.create_text(int(cw*0.1),int(ch*0.1),text="\u201C",fill="#FFFFFF",
                           font=("Segoe UI",int(ch*0.4),"bold"),anchor="nw")
            c.create_text(cw//2,int(ch*0.55),text=title,fill="#FFFFFF",
                           font=("Segoe UI",int(title_sz*1.1),"italic"),
                           width=int(cw*0.75),justify="center")
            if body.strip():
                c.create_text(cw//2,int(ch*0.82),text=body,fill="#CBD5E1",
                               font=("Segoe UI",body_sz),width=int(cw*0.6))
        elif layout=="Section header":
            c.create_rectangle(0,int(ch*0.35),cw,int(ch*0.65),
                                fill=accent,outline="")
            c.create_text(cw//2,ch//2,text=title,fill="#FFFFFF",
                           font=("Segoe UI",title_sz,"bold"),
                           width=int(cw*0.82),justify="center")
        elif layout=="Two columns" and body.strip():
            c.create_text(cw//2,int(ch*0.12),text=title,fill="#FFFFFF",
                           font=("Segoe UI",max(14,title_sz-6),"bold"),
                           width=int(cw*0.88),justify="center")
            half_body=body_lines[:len(body_lines)//2+1]
            second_body=body_lines[len(body_lines)//2+1:]
            c.create_text(int(cw*0.26),int(ch*0.55),
                           text="\n".join(half_body),fill="#CBD5E1",
                           font=("Segoe UI",body_sz),width=int(cw*0.42),justify="left")
            c.create_line(cw//2,int(ch*0.25),cw//2,int(ch*0.85),
                           fill="#475569",width=1,dash=(4,4))
            c.create_text(int(cw*0.74),int(ch*0.55),
                           text="\n".join(second_body),fill="#CBD5E1",
                           font=("Segoe UI",body_sz),width=int(cw*0.42),justify="left")
        elif layout=="Comparison":
            c.create_text(cw//2,int(ch*0.12),text=title,fill="#FFFFFF",
                           font=("Segoe UI",max(14,title_sz-6),"bold"),
                           width=int(cw*0.88),justify="center")
            c.create_rectangle(int(cw*0.06),int(ch*0.28),int(cw*0.47),int(ch*0.88),
                               fill="#1E293B",outline=accent,width=1)
            c.create_text(int(cw*0.265),int(ch*0.33),text="Option A",fill=accent,
                           font=("Segoe UI",12,"bold"),anchor="n")
            c.create_rectangle(int(cw*0.53),int(ch*0.28),int(cw*0.94),int(ch*0.88),
                               fill="#1E293B",outline=accent,width=1)
            c.create_text(int(cw*0.735),int(ch*0.33),text="Option B",fill=accent,
                           font=("Segoe UI",12,"bold"),anchor="n")
            if body.strip():
                c.create_text(int(cw*0.265),int(ch*0.42),text=body,fill="#CBD5E1",
                               font=("Segoe UI",body_sz),width=int(cw*0.38),justify="left",anchor="n")
        elif layout=="Title + Two content":
            c.create_text(cw//2,int(ch*0.12),text=title,fill="#FFFFFF",
                           font=("Segoe UI",max(14,title_sz-6),"bold"),
                           width=int(cw*0.88),justify="center")
            c.create_line(int(cw*0.08),int(ch*0.26),int(cw*0.92),int(ch*0.26),
                           fill=accent,width=2)
            if body.strip():
                lines2 = body_lines
                half = len(lines2)//2
                c.create_text(int(cw*0.28),int(ch*0.6),
                               text="\n".join(lines2[:half+1]),fill="#CBD5E1",
                               font=("Segoe UI",body_sz),width=int(cw*0.4),justify="left")
                c.create_text(int(cw*0.72),int(ch*0.6),
                               text="\n".join(lines2[half+1:]),fill="#CBD5E1",
                               font=("Segoe UI",body_sz),width=int(cw*0.4),justify="left")
        elif layout=="Agenda":
            c.create_text(int(cw*0.1),int(ch*0.12),text=title,fill="#FFFFFF",
                           font=("Segoe UI",title_sz,"bold"),anchor="nw")
            c.create_line(int(cw*0.1),int(ch*0.28),int(cw*0.9),int(ch*0.28),
                           fill=accent,width=2)
            if body.strip():
                y = int(ch*0.34)
                for i, bl in enumerate(body_lines):
                    if not bl.strip(): continue
                    c.create_text(int(cw*0.12), y, text=f"{i+1}.  {bl}",
                                  fill="#CBD5E1", font=("Segoe UI",body_sz), anchor="nw")
                    y += int(body_sz*1.6)
        else:  # "Title + Content" and others
            # title in upper third
            title_y = int(ch*0.22)
            c.create_text(cw//2,title_y,text=title,fill="#FFFFFF",
                           font=("Segoe UI",title_sz,"bold"),
                           width=int(cw*0.84),justify="center")
            # thin separator line
            c.create_line(int(cw*0.1),int(ch*0.38),int(cw*0.9),int(ch*0.38),
                           fill=accent,width=2)
            # body content
            if body.strip():
                # bullet points if lines start without a bullet
                display_body=body
                if body_lines and not body_lines[0].startswith(("•","●","◆","-","*")):
                    display_body="\n".join("• "+l if l.strip() else l for l in body_lines)
                c.create_text(int(cw*0.12),int(ch*0.56),
                               text=display_body,fill="#CBD5E1",
                               font=("Segoe UI",body_sz),
                               width=int(cw*0.78),justify="left",anchor="n")

        # transition indicator badge
        trans=getattr(self,"_slide_trans_var",None)
        if trans:
            try:
                tv=trans.get()
                if tv and tv!="None":
                    c.create_rectangle(8,ch-26,8+len(tv)*7+16,ch-6,
                                        fill="#1E293B",outline=accent)
                    c.create_text(16,ch-16,text=f"⇢ {tv}",anchor="w",
                                   fill=accent,font=("Segoe UI",8))
            except Exception: pass

        # slide counter bottom-right
        c.create_text(cw-12,ch-10,
                       text=f"  {self._cur_slide+1} / {len(self._slides)}  ",
                       fill="#64748B",anchor="se",font=("Segoe UI",9))

        self._slide_refresh_list()
        self.slide_editor.edit_modified(False)
        self.slide_editor.delete("1.0","end"); self.slide_editor.insert("1.0",slide["text"])
        self.slide_editor.edit_modified(False)
        self.notes_editor.edit_modified(False)
        self.notes_editor.delete("1.0","end"); self.notes_editor.insert("1.0",slide.get("notes",""))
        self.notes_editor.edit_modified(False)

    def _slide_select(self,e=None):
        s=self.slide_lb.curselection()
        if s: self._cur_slide=s[0]; self._slide_redraw()

    def _slide_add(self):
        self._slides.insert(self._cur_slide+1,self._empty_slide())
        self._cur_slide+=1; self._slide_redraw()

    def _slide_duplicate(self):
        s=copy.deepcopy(self._slides[self._cur_slide])
        self._slides.insert(self._cur_slide+1,s); self._cur_slide+=1; self._slide_redraw()

    def _slide_delete(self):
        if len(self._slides)<=1: messagebox.showinfo(APP,"Need at least one slide."); return
        self._slides.pop(self._cur_slide)
        self._cur_slide=max(0,self._cur_slide-1); self._slide_redraw()

    def _slide_move(self,d:int):
        n=self._cur_slide+d
        if 0<=n<len(self._slides):
            self._slides[self._cur_slide],self._slides[n]=self._slides[n],self._slides[self._cur_slide]
            self._cur_slide=n; self._slide_redraw()

    def _slide_text_changed(self,e=None):
        if self.slide_editor.edit_modified():
            self._slides[self._cur_slide]["text"]=self.slide_editor.get("1.0","end-1c")
            # save layout selection too
            if hasattr(self,"_slide_layout"):
                self._slides[self._cur_slide]["layout"]=self._slide_layout.get()
            self.slide_editor.edit_modified(False); self._slide_redraw()

    def _notes_changed(self,e=None):
        if self.notes_editor.edit_modified():
            self._slides[self._cur_slide]["notes"]=self.notes_editor.get("1.0","end-1c")
            self.notes_editor.edit_modified(False)

    def _slide_apply_theme(self):
        color=self._slide_theme.get()
        self._slides[self._cur_slide]["background"]=color
        # also save transition if set
        if hasattr(self,"_slide_trans_var"):
            self._slides[self._cur_slide]["transition"]=self._slide_trans_var.get()
        self._slide_redraw()

    def _slide_export_pptx(self):
        try: from pptx import Presentation; from pptx.util import Inches,Pt
        except ImportError: messagebox.showinfo(APP,"PPTX needs python-pptx.\npip install python-pptx"); return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".pptx",filetypes=[("PowerPoint","*.pptx")])
        if not p: return
        prs=Presentation(); blank=prs.slide_layouts[6]
        for sd in self._slides:
            slide=prs.slides.add_slide(blank); lines=sd["text"].splitlines()
            title=lines[0] if lines else ""; body="".join(lines[1:]) if len(lines)>1 else ""
            tf=slide.shapes.add_textbox(Inches(0.5),Inches(1.5),Inches(9),Inches(1.5))
            tf.text_frame.text=title
            if tf.text_frame.paragraphs and tf.text_frame.paragraphs[0].runs:
                tf.text_frame.paragraphs[0].runs[0].font.size=Pt(36)
                tf.text_frame.paragraphs[0].runs[0].font.bold=True
            if body:
                tb=slide.shapes.add_textbox(Inches(0.5),Inches(3.0),Inches(9),Inches(3.5))
                tb.text_frame.text=body
        prs.save(p); self.status.set(f"PPTX exported: {Path(p).name}")

    # ══════════════════════════════════════════════════════════════════════════
    #  VIDEO  methods (inline)
    # ══════════════════════════════════════════════════════════════════════════
    def _vid_track(self)->Optional[dict]:
        t=self._video_project["tracks"]
        return t[self._video_sel_track] if 0<=self._video_sel_track<len(t) else None

    def _video_refresh(self):
        self._vid_track_lb.delete(0,"end")
        for t in self._video_project["tracks"]:
            icon="🔇" if t.get("muted") else ("🔒" if t.get("locked") else "▶")
            self._vid_track_lb.insert("end",f"{icon} {t['name']} [{t['kind']}] ({len(t['clips'])})")
        if self._video_sel_track<self._vid_track_lb.size():
            self._vid_track_lb.selection_set(self._video_sel_track)
        self._vid_clip_lb.delete(0,"end")
        tr=self._vid_track()
        if tr:
            for i,c in enumerate(tr["clips"]):
                lbl=f"  [{c['label']}]" if c.get("label") else ""
                self._vid_clip_lb.insert("end",f"{i+1:02d}  {Path(c['path']).name}{lbl}")
            if self._video_sel_clip is not None and self._video_sel_clip<self._vid_clip_lb.size():
                self._vid_clip_lb.selection_set(self._video_sel_clip)
        self._video_draw_timeline()
        self._video_refresh_captions()

    def _video_on_track_select(self,e=None):
        s=self._vid_track_lb.curselection()
        if s: self._video_sel_track=s[0]; self._video_sel_clip=None; self._video_refresh()

    def _video_on_clip_select(self,e=None):
        s=self._vid_clip_lb.curselection()
        if not s: return
        self._video_sel_clip=s[0]
        tr=self._vid_track()
        if tr is None or self._video_sel_clip>=len(tr["clips"]): return
        clip=tr["clips"][self._video_sel_clip]
        self._vid_clip_name.set(Path(clip["path"]).name)
        self._vid_start.set(clip.get("start","0")); self._vid_end.set(clip.get("end",""))
        self._vid_speed.set(clip.get("speed",1.0)); self._vid_vol.set(clip.get("volume",1.0))
        self._vid_opac.set(clip.get("opacity",1.0)); self._vid_muted.set(clip.get("muted",False))
        self._vid_trans.set(clip.get("transition","Cut")); self._vid_filter.set(clip.get("filter","None"))
        cg=clip.get("color_grading",{})
        for k,v in self._grade_vars.items(): v.set(cg.get(k,0))
        self._video_draw_timeline(); self._video_preview_selected()

    def _video_draw_timeline(self):
        """Route to enhanced timeline with thumbnails, waveforms, and trim handles."""
        self._video_draw_timeline_enhanced()

    def _video_draw_timeline_basic(self):
        if not hasattr(self, '_tl_canvas'): return
        c=self._tl_canvas; c.delete("all")
        W=max(800,c.winfo_width()); tracks=self._video_project["tracks"]
        ROW_H=44; LABEL_W=88; RULER_H=22
        c.create_rectangle(0,0,W,RULER_H,fill="#111827",outline="")
        for sec in range(0,600,5):
            rx=LABEL_W+sec*22
            c.create_line(rx,0,rx,RULER_H,fill="#374151")
            c.create_text(rx+3,4,text=f"{sec}s",anchor="nw",fill="#9CA3AF",font=("Segoe UI",7))
        total_h=RULER_H+ROW_H*len(tracks)+10
        for ri,track in enumerate(tracks):
            y0=RULER_H+ri*ROW_H; y1=y0+ROW_H-2
            c.create_rectangle(0,y0,W,y1,fill="#1E2A3A" if ri%2==0 else "#182031",outline="")
            c.create_rectangle(0,y0,LABEL_W,y1,fill="#111827",outline="")
            c.create_text(6,y0+ROW_H//2,text=track["name"],anchor="w",fill="#CBD5E1",font=("Segoe UI",8,"bold"))
            tc=track.get("color","#315C8A")
            for ci,clip in enumerate(track["clips"]):
                try:
                    cstart=float(clip.get("offset",ci*5) or 0)
                    cdur=max(1,float(clip.get("end","5") or 5)-float(clip.get("start","0") or 0))
                except (ValueError,TypeError): cstart,cdur=float(ci*5),5.0
                cx0=LABEL_W+int(cstart*22); cx1=cx0+max(20,int(cdur*22))
                is_sel=(ri==self._video_sel_track and ci==self._video_sel_clip)
                c.create_rectangle(cx0+1,y0+4,cx1-1,y1-4,
                                    fill="#F59E0B" if is_sel else tc,
                                    outline="white" if is_sel else "")
                c.create_text(cx0+4,y0+ROW_H//2,text=Path(clip["path"]).stem[:16],
                               anchor="w",fill="white",font=("Segoe UI",7))
        for m in self._video_project.get("markers",[]):
            mx=LABEL_W+m["time"]*22
            c.create_line(mx,0,mx,total_h,fill="#F59E0B",dash=(4,2),width=1)
            c.create_text(mx+2,RULER_H+2,text=m.get("label",""),anchor="nw",fill="#FCD34D",font=("Segoe UI",7))
        c.configure(scrollregion=(0,0,max(W,LABEL_W+600*22),total_h+10))

    def _tl_click(self,e):
        LABEL_W=88; RULER_H=22; ROW_H=44
        if e.y>RULER_H:
            row=(e.y-RULER_H)//ROW_H
            if 0<=row<len(self._video_project["tracks"]):
                self._video_sel_track=row; self._video_sel_clip=None; self._video_refresh()

    def _video_preview_selected(self):
        self._vid_preview.delete("all"); self._vid_preview_img=None
        tr=self._vid_track()
        if tr is None or self._video_sel_clip is None: return
        if self._video_sel_clip>=len(tr["clips"]): return
        clip=tr["clips"][self._video_sel_clip]
        path=clip["path"]; suffix=Path(path).suffix.lower()
        cw=max(200,self._vid_preview.winfo_width()); ch=max(100,self._vid_preview.winfo_height())
        if suffix in (".png",".jpg",".jpeg",".webp",".gif",".bmp"):
            try:
                from PIL import Image,ImageTk
                im=Image.open(path); im.thumbnail((cw,ch))
                self._vid_preview_img=ImageTk.PhotoImage(im)
                self._vid_preview.create_image(cw//2,ch//2,image=self._vid_preview_img)
                return
            except Exception: pass
        self._vid_preview.create_rectangle(0,0,cw,ch,fill="#0D1117",outline="")
        try: sz_str=f"\n{Path(path).stat().st_size//1024} KB"
        except: sz_str=""
        self._vid_preview.create_text(cw//2,ch//2,
            text=f"{Path(path).name}\n{suffix[1:].upper()}{sz_str}\nTransition: {clip.get('transition','Cut')}",
            fill="#C9D1D9",font=("Segoe UI",12),justify="center")

    def _video_toggle_play(self):
        self._vid_play_btn.configure(text="⏸ Pause" if not getattr(self,"_vid_playing",False) else "▶ Play")
        self._vid_playing=not getattr(self,"_vid_playing",False)

    def _video_add_clips(self):
        paths=filedialog.askopenfilenames(parent=self,title="Add clips",
            filetypes=[("Video and images","*.mp4 *.mov *.mkv *.avi *.webm *.png *.jpg *.jpeg *.webp *.gif")])
        tr=self._vid_track()
        if not tr: return
        for p in paths:
            clip=self._empty_clip(p); clip["offset"]=len(tr["clips"])*5.0; tr["clips"].append(clip)
        self._video_refresh(); self._vid_status.set(f"Added {len(paths)} clip(s).")

    def _video_add_audio(self):
        p=filedialog.askopenfilename(parent=self,title="Add audio",
            filetypes=[("Audio","*.mp3 *.wav *.m4a *.aac *.ogg *.flac")])
        if not p: return
        at=next((t for t in self._video_project["tracks"] if t["kind"]=="audio"),None)
        if at: at["clips"].append(self._empty_clip(p))
        self._video_refresh()

    def _video_add_title(self):
        text=simpledialog.askstring("Add title","Title text:",parent=self)
        if not text: return
        tt=next((t for t in self._video_project["tracks"] if t["kind"]=="title"),None)
        if tt:
            clip={"path":"","text":text,"start":"0","end":"5","offset":0.0,
                   "transition":"Fade","label":text[:30],"volume":0.0,"opacity":1.0,
                   "speed":1.0,"muted":True,"filter":"None","color_grading":{}}
            tt["clips"].append(clip)
        self._video_refresh()

    def _video_add_marker(self):
        t=simpledialog.askfloat("Add marker","Time (seconds):",initialvalue=0.0,parent=self)
        if t is None: return
        lbl=simpledialog.askstring("Marker label","Label (optional):",parent=self) or ""
        self._video_project["markers"].append({"time":t,"label":lbl,"color":"#F59E0B"})
        self._video_draw_timeline()

    def _video_remove_clip(self):
        tr=self._vid_track()
        if tr and self._video_sel_clip is not None and self._video_sel_clip<len(tr["clips"]):
            tr["clips"].pop(self._video_sel_clip); self._video_sel_clip=None; self._video_refresh()

    def _video_move_clip(self,d:int):
        tr=self._vid_track()
        if tr is None or self._video_sel_clip is None: return
        n=self._video_sel_clip+d
        if 0<=n<len(tr["clips"]):
            tr["clips"][self._video_sel_clip],tr["clips"][n]=tr["clips"][n],tr["clips"][self._video_sel_clip]
            self._video_sel_clip=n; self._video_refresh()

    def _video_apply_clip(self):
        tr=self._vid_track()
        if tr is None or self._video_sel_clip is None: return
        clip=tr["clips"][self._video_sel_clip]
        clip.update({"start":self._vid_start.get(),"end":self._vid_end.get(),
                      "speed":self._vid_speed.get(),"volume":self._vid_vol.get(),
                      "opacity":self._vid_opac.get(),"muted":self._vid_muted.get(),
                      "transition":self._vid_trans.get(),"filter":self._vid_filter.get()})
        self._video_refresh(); self._vid_status.set("Clip updated.")

    def _video_apply_grade(self):
        tr=self._vid_track()
        if tr is None or self._video_sel_clip is None: return
        tr["clips"][self._video_sel_clip]["color_grading"]={k:v.get() for k,v in self._grade_vars.items()}
        self._vid_status.set("Color grade applied.")

    def _video_reset_grade(self):
        for v in self._grade_vars.values(): v.set(0.0)
        self._video_apply_grade()

    def _video_mute_track(self):
        tr=self._vid_track()
        if tr: tr["muted"]=not tr.get("muted",False); self._video_refresh()

    def _video_lock_track(self):
        tr=self._vid_track()
        if tr: tr["locked"]=not tr.get("locked",False); self._video_refresh()

    def _video_remove_track(self):
        tr=self._vid_track()
        if tr and messagebox.askyesno(APP,f"Remove {tr['name']}?"):
            self._video_project["tracks"].pop(self._video_sel_track)
            self._video_sel_track=max(0,self._video_sel_track-1); self._video_refresh()

    def _video_add_caption_entry(self):
        text=self._cap_text.get("1.0","end-1c").strip()
        if not text: return
        cap={"text":text,"start":self._cap_start.get(),"end":self._cap_end.get(),"clip":self._video_sel_clip or 0}
        self._video_project["captions"].append(cap)
        self._cap_text.delete("1.0","end"); self._video_refresh_captions(); self._video_draw_timeline()

    def _video_del_caption(self):
        s=self._cap_list_lb.curselection()
        if s: self._video_project["captions"].pop(s[0]); self._video_refresh_captions()

    def _video_refresh_captions(self):
        self._cap_list_lb.delete(0,"end")
        for cap in self._video_project.get("captions",[]):
            self._cap_list_lb.insert("end",f"{cap.get('start',0):.1f}–{cap.get('end',3):.1f}s  {cap.get('text','')[:35]}")

    def _video_export_srt(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".srt",filetypes=[("SubRip","*.srt")])
        if not p: return
        lines=[]
        for i,cap in enumerate(self._video_project.get("captions",[]),1):
            def _t(s):
                h=int(s)//3600; m=(int(s)%3600)//60; sec=s%60
                return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".",",")
            lines+=[str(i),f"{_t(cap.get('start',0))} --> {_t(cap.get('end',3))}",cap.get("text",""),""]
        Path(p).write_text("\n".join(lines),encoding="utf-8")
        self.status.set(f"SRT exported: {Path(p).name}")

    def _video_render(self):
        import shutil as _sh
        ff=_sh.which("ffmpeg")
        if not ff:
            messagebox.showinfo("ffmpeg not found",
                "Install ffmpeg:\nwinget install ffmpeg\n\nThen retry Render MP4.",parent=self); return
        clips=[c for t in self._video_project["tracks"] if t["kind"]=="video" and not t.get("muted")
                 for c in t["clips"] if Path(c.get("path","")).exists()]
        if not clips: messagebox.showinfo(APP,"Add video clips first.",parent=self); return
        out=filedialog.asksaveasfilename(parent=self,defaultextension=".mp4",filetypes=[("MP4","*.mp4")])
        if not out: return
        manifest=Path(tempfile.gettempdir())/"studio_concat.txt"
        manifest.write_text("\n".join(f"file '{c['path']}'" for c in clips),encoding="utf-8")
        try:
            import subprocess as _sp
            _sp.run([ff,"-y","-f","concat","-safe","0","-i",str(manifest),"-c","copy",out],
                    check=True,capture_output=True)
            self.status.set(f"Rendered: {Path(out).name}")
            messagebox.showinfo("Done",f"MP4 saved:\n{out}",parent=self)
        except Exception as exc:
            messagebox.showerror("Render failed",str(exc),parent=self)

    def _video_save(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".hvs",filetypes=[("Video project","*.hvs")])
        if p:
            Path(p).write_text(json.dumps({"format":"HomeworkVideoStudio","version":3,**self._video_project},indent=2,ensure_ascii=False),encoding="utf-8")
            self.status.set(f"Video project saved: {Path(p).name}")

    def _video_open(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("Video project","*.hvs *.json")])
        if p:
            try:
                data=json.loads(Path(p).read_text(encoding="utf-8"))
                self._video_project=data; self._video_sel_track=0; self._video_sel_clip=None
                self._video_refresh()
            except Exception as exc: messagebox.showerror(APP,str(exc),parent=self)

    # ══════════════════════════════════════════════════════════════════════════
    #  ANIMATION  methods (inline)
    # ══════════════════════════════════════════════════════════════════════════
    def _anim_layer_obj(self)->Optional[dict]:
        layers=self._anim_project["layers"]
        return layers[self._anim_layer] if 0<=self._anim_layer<len(layers) else None

    def _anim_get_ops(self)->list:
        layer=self._anim_layer_obj()
        if layer is None: return []
        key=str(self._anim_frame)
        if key not in layer["frames"]: layer["frames"][key]=[]
        return layer["frames"][key]

    def _anim_redraw(self):
        if not hasattr(self, '_anim_canvas'): return
        c=self._anim_canvas; c.delete("all")
        cw=max(200,c.winfo_width()); ch=max(100,c.winfo_height())
        pw=int(self._anim_project["width"]*self._anim_zoom)
        ph=int(self._anim_project["height"]*self._anim_zoom)
        ox=max(0,(cw-pw)//2); oy=max(0,(ch-ph)//2)
        c.create_rectangle(ox,oy,ox+pw,oy+ph,fill=self._anim_project.get("background","#FFFFFF"),outline="#AAA")
        if self._anim_grid.get():
            gs=max(8,int(20*self._anim_zoom))
            for x in range(0,pw,gs): c.create_line(ox+x,oy,ox+x,oy+ph,fill="#DDD",dash=(2,4))
            for y in range(0,ph,gs): c.create_line(ox,oy+y,ox+pw,oy+y,fill="#DDD",dash=(2,4))
        # onion skin prev
        for back in range(self._onion_prev.get(),0,-1):
            fi=self._anim_frame-back
            if fi>=0:
                opac=max(0.1,self._onion_prev.get()/(back+self._onion_prev.get()+1))
                self._anim_paint_all(c,fi,ox,oy,"#3366CC",opac)
        # onion skin next
        for fwd in range(1,self._onion_next.get()+1):
            fi=self._anim_frame+fwd
            if fi<self._anim_project["total_frames"]:
                opac=max(0.1,self._onion_next.get()/(fwd+self._onion_next.get()+1))
                self._anim_paint_all(c,fi,ox,oy,"#CC3333",opac)
        # actual layers
        for layer in self._anim_project["layers"]:
            if layer.get("visible",True):
                self._anim_paint_layer(c,self._anim_frame,ox,oy,layer,None)
        c.configure(scrollregion=(0,0,max(cw,ox+pw+40),max(ch,oy+ph+40)))
        self._anim_refresh_lists()

    def _anim_paint_all(self,c,fi,ox,oy,ghost_color,opac):
        for layer in self._anim_project["layers"]:
            if layer.get("visible",True):
                self._anim_paint_layer(c,fi,ox,oy,layer,ghost_color)

    def _anim_paint_layer(self,c,fi,ox,oy,layer,ghost_color):
        z=self._anim_zoom
        for op in layer["frames"].get(str(fi),[]):
            pts=[(ox+int(x*z),oy+int(y*z)) for x,y in op.get("pts",[])]
            if not pts: continue
            t=op.get("tool","Brush"); color=ghost_color or op.get("color","#000")
            w=max(1,int(op.get("width",3)*z)); flat=[coord for p in pts for coord in p]
            if t in ("Brush","Pencil"):
                if len(pts)>=2: c.create_line(*flat,fill=color,width=w,smooth=op.get("smooth",True),capstyle="round")
                else:
                    r=max(1,w//2); x,y=pts[0]; c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline="")
            elif t=="Line" and len(pts)>=2: c.create_line(*pts[0],*pts[-1],fill=color,width=w)
            elif t=="Rectangle" and len(pts)>=2: c.create_rectangle(*pts[0],*pts[-1],outline=color,width=w)
            elif t=="Ellipse" and len(pts)>=2: c.create_oval(*pts[0],*pts[-1],outline=color,width=w)
            elif t=="Fill" and pts:
                r=int(80*z); x,y=pts[0]; c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline="")
            elif t=="Text" and pts:
                sz=max(10,int(op.get("width",3)*4*z))
                c.create_text(*pts[0],text=op.get("text",""),fill=color,font=("Segoe UI",sz),anchor="nw")

    def _anim_refresh_lists(self):
        total=self._anim_project["total_frames"]
        self._anim_frame_lb.delete(0,"end")
        for i in range(total):
            n=sum(len(l["frames"].get(str(i),[])) for l in self._anim_project["layers"])
            mark=" ◀" if i==self._anim_frame else ""
            self._anim_frame_lb.insert("end",f"Frame {i+1:03d}  · {n}{mark}")
        if self._anim_frame<self._anim_frame_lb.size():
            self._anim_frame_lb.selection_set(self._anim_frame)
        self._anim_scrubber.configure(to=max(0,total-1))
        self._anim_scrubber.set(self._anim_frame)
        self._anim_frame_lbl.configure(text=f"{self._anim_frame+1}/{total}")
        # layers
        self._anim_layer_lb.delete(0,"end")
        for i,layer in enumerate(self._anim_project["layers"]):
            eye="👁" if layer.get("visible",True) else "◻"
            lock="🔒" if layer.get("locked") else "  "
            mark=" ←" if i==self._anim_layer else ""
            self._anim_layer_lb.insert("end",f"{eye}{lock} {layer['name']}{mark}")
        if self._anim_layer<self._anim_layer_lb.size():
            self._anim_layer_lb.selection_set(self._anim_layer)

    def _anim_proj_to_canvas(self,ex,ey):
        cw=max(200,self._anim_canvas.winfo_width()); ch=max(100,self._anim_canvas.winfo_height())
        pw=int(self._anim_project["width"]*self._anim_zoom)
        ph=int(self._anim_project["height"]*self._anim_zoom)
        ox=max(0,(cw-pw)//2); oy=max(0,(ch-ph)//2)
        return (ex-ox)/self._anim_zoom,(ey-oy)/self._anim_zoom

    def _anim_push_undo(self):
        snap=json.dumps([{"id":l["id"],"frame":l["frames"].get(str(self._anim_frame),[])} for l in self._anim_project["layers"]])
        self._anim_undo_stack.append(snap); self._anim_undo_stack=self._anim_undo_stack[-60:]; self._anim_redo_stack.clear()

    def _anim_undo(self):
        if not self._anim_undo_stack: return
        cur=json.dumps([{"id":l["id"],"frame":l["frames"].get(str(self._anim_frame),[])} for l in self._anim_project["layers"]])
        self._anim_redo_stack.append(cur)
        state=json.loads(self._anim_undo_stack.pop())
        for item in state:
            layer=next((l for l in self._anim_project["layers"] if l["id"]==item["id"]),None)
            if layer: layer["frames"][str(self._anim_frame)]=item["frame"]
        self._anim_redraw()

    def _anim_redo(self):
        if not self._anim_redo_stack: return
        cur=json.dumps([{"id":l["id"],"frame":l["frames"].get(str(self._anim_frame),[])} for l in self._anim_project["layers"]])
        self._anim_undo_stack.append(cur)
        state=json.loads(self._anim_redo_stack.pop())
        for item in state:
            layer=next((l for l in self._anim_project["layers"] if l["id"]==item["id"]),None)
            if layer: layer["frames"][str(self._anim_frame)]=item["frame"]
        self._anim_redraw()

    def _anim_down(self,e):
        layer=self._anim_layer_obj()
        if layer is None or layer.get("locked"): return
        if self._anim_tool.get()=="Select": return
        if self._anim_tool.get()=="Text":
            text=simpledialog.askstring("Text","Enter text:",parent=self)
            if text:
                pt=self._anim_proj_to_canvas(e.x,e.y)
                self._anim_push_undo()
                self._anim_get_ops().append({"tool":"Text","pts":[pt],"color":self._anim_color,"width":self._anim_brush.get(),"text":text,"smooth":False})
                self._anim_redraw()
            return
        if self._anim_tool.get()=="Fill":
            pt=self._anim_proj_to_canvas(e.x,e.y)
            self._anim_push_undo()
            self._anim_get_ops().append({"tool":"Fill","pts":[pt],"color":self._anim_color,"width":self._anim_brush.get(),"smooth":False})
            self._anim_redraw(); return
        self._anim_push_undo()
        self._anim_start_pt=self._anim_proj_to_canvas(e.x,e.y)
        self._anim_cur_pts=[self._anim_start_pt]

    def _anim_drag(self,e):
        if self._anim_start_pt is None: return
        pt=self._anim_proj_to_canvas(e.x,e.y); self._anim_cur_pts.append(pt)
        t=self._anim_tool.get()
        if t in ("Brush","Pencil","Eraser"):
            self._anim_redraw()
            z=self._anim_zoom
            cw=max(200,self._anim_canvas.winfo_width()); ch=max(100,self._anim_canvas.winfo_height())
            pw=int(self._anim_project["width"]*z); ph=int(self._anim_project["height"]*z)
            ox=max(0,(cw-pw)//2); oy=max(0,(ch-ph)//2)
            screen_pts=[(ox+int(x*z),oy+int(y*z)) for x,y in self._anim_cur_pts]
            flat=[c for p in screen_pts for c in p]
            if len(screen_pts)>=2:
                color=self._anim_project.get("background","#FFF") if t=="Eraser" else self._anim_color
                self._anim_canvas.create_line(*flat,fill=color,
                                               width=max(1,int(self._anim_brush.get()*z)),
                                               smooth=self._anim_smooth.get(),capstyle="round",tags="_preview")
        else: self._anim_redraw()

    def _anim_up(self,e):
        if self._anim_start_pt is None: return
        pt=self._anim_proj_to_canvas(e.x,e.y); t=self._anim_tool.get()
        if t=="Eraser":
            ops=self._anim_get_ops()
            if ops: ops.pop()
        elif t not in ("Select","Text","Fill"):
            pts=self._anim_cur_pts if t in ("Brush","Pencil") else [self._anim_start_pt,pt]
            self._anim_get_ops().append({"tool":t,"pts":pts,"color":self._anim_color,
                                          "width":self._anim_brush.get(),"smooth":self._anim_smooth.get(),"opacity":self._anim_opacity.get()})
        self._anim_start_pt=None; self._anim_cur_pts=[]; self._anim_redraw()

    def _anim_pick_color(self):
        c=colorchooser.askcolor(self._anim_color,parent=self)[1]
        if c: self._anim_set_color(c)

    def _anim_set_color(self,c:str):
        self._anim_color=c
        if hasattr(self,"_anim_color_swatch"): self._anim_color_swatch.configure(bg=c)
        if hasattr(self,"_anim_color_lbl"):    self._anim_color_lbl.configure(bg=c)

    def _anim_go_frame(self,d:int):
        total=self._anim_project["total_frames"]
        self._anim_frame=max(0,min(total-1,self._anim_frame+d)); self._anim_redraw()

    def _anim_scrub(self,val):
        self._anim_frame=int(float(val)); self._anim_redraw()

    def _anim_on_frame_select(self,e=None):
        s=self._anim_frame_lb.curselection()
        if s: self._anim_frame=s[0]; self._anim_redraw()

    def _anim_on_layer_select(self,e=None):
        s=self._anim_layer_lb.curselection()
        if s: self._anim_layer=s[0]; self._anim_layer_opac.set(self._anim_project["layers"][self._anim_layer].get("opacity",1.0)); self._anim_refresh_lists()

    def _anim_add_frame(self):
        self._anim_project["total_frames"]+=1
        self._anim_frame=self._anim_project["total_frames"]-1
        self._anim_scrubber.configure(to=self._anim_project["total_frames"]-1)
        self._anim_redraw()

    def _anim_duplicate_frame(self):
        fi=self._anim_frame
        for layer in self._anim_project["layers"]:
            src=copy.deepcopy(layer["frames"].get(str(fi),[]))
            nf={}
            for k,v in layer["frames"].items():
                idx=int(k); nf[str(idx+1) if idx>fi else k]=v
            nf[str(fi+1)]=src; layer["frames"]=nf
        self._anim_project["total_frames"]+=1; self._anim_frame=fi+1
        self._anim_scrubber.configure(to=self._anim_project["total_frames"]-1); self._anim_redraw()

    def _anim_delete_frame(self):
        if self._anim_project["total_frames"]<=1: messagebox.showinfo(APP,"Need at least one frame."); return
        fi=self._anim_frame
        for layer in self._anim_project["layers"]:
            nf={}
            for k,v in layer["frames"].items():
                idx=int(k)
                if idx<fi: nf[k]=v
                elif idx>fi: nf[str(idx-1)]=v
            layer["frames"]=nf
        self._anim_project["total_frames"]-=1; self._anim_frame=max(0,fi-1)
        self._anim_scrubber.configure(to=max(0,self._anim_project["total_frames"]-1)); self._anim_redraw()

    def _anim_move_frame(self,d:int):
        fi=self._anim_frame; fj=fi+d; total=self._anim_project["total_frames"]
        if not(0<=fj<total): return
        for layer in self._anim_project["layers"]:
            a=copy.deepcopy(layer["frames"].get(str(fi),[])); b=copy.deepcopy(layer["frames"].get(str(fj),[]))
            layer["frames"][str(fi)]=b; layer["frames"][str(fj)]=a
        self._anim_frame=fj; self._anim_redraw()

    def _anim_clear_frame(self):
        for layer in self._anim_project["layers"]: layer["frames"].pop(str(self._anim_frame),None)
        self._anim_redraw()

    def _anim_play_toggle(self):
        self._anim_playing=not self._anim_playing
        if hasattr(self,"_anim_play_btn"):
            self._anim_play_btn.configure(text="⏸ Pause" if self._anim_playing else "▶ Play")
        if self._anim_playing: self._anim_tick()

    def _anim_tick(self):
        if not self._anim_playing: return
        total=self._anim_project["total_frames"]
        self._anim_frame=(self._anim_frame+1)%total; self._anim_redraw()
        delay=max(16,int(1000/self._anim_project["fps"]))
        self.after(delay,self._anim_tick)

    def _anim_add_layer(self):
        name=simpledialog.askstring("New layer","Layer name:",parent=self) or f"Layer {len(self._anim_project['layers'])+1}"
        self._anim_project["layers"].insert(self._anim_layer+1,
            {"id":new_id(),"name":name,"visible":True,"locked":False,"opacity":1.0,"frames":{}})
        self._anim_layer+=1; self._anim_refresh_lists()

    def _anim_dup_layer(self):
        layer=self._anim_layer_obj()
        if layer is None: return
        new=copy.deepcopy(layer); new["id"]=new_id(); new["name"]=layer["name"]+" copy"
        self._anim_project["layers"].insert(self._anim_layer+1,new); self._anim_layer+=1; self._anim_refresh_lists()

    def _anim_del_layer(self):
        if len(self._anim_project["layers"])<=1: messagebox.showinfo(APP,"Need at least one layer."); return
        self._anim_project["layers"].pop(self._anim_layer)
        self._anim_layer=max(0,self._anim_layer-1); self._anim_refresh_lists(); self._anim_redraw()

    def _anim_move_layer(self,d:int):
        n=self._anim_layer+d; layers=self._anim_project["layers"]
        if 0<=n<len(layers):
            layers[self._anim_layer],layers[n]=layers[n],layers[self._anim_layer]
            self._anim_layer=n; self._anim_refresh_lists(); self._anim_redraw()

    def _anim_toggle_visible(self):
        layer=self._anim_layer_obj()
        if layer: layer["visible"]=not layer.get("visible",True); self._anim_refresh_lists(); self._anim_redraw()

    def _anim_toggle_lock(self):
        layer=self._anim_layer_obj()
        if layer: layer["locked"]=not layer.get("locked",False); self._anim_refresh_lists()

    def _anim_apply_layer_opacity(self):
        layer=self._anim_layer_obj()
        if layer: layer["opacity"]=max(0,min(1,self._anim_layer_opac.get())); self._anim_redraw()

    def _anim_zoom_by(self,delta:float):
        self._anim_zoom=max(0.25,min(4.0,self._anim_zoom+delta))
        if hasattr(self,"_anim_zoom_lbl"): self._anim_zoom_lbl.configure(text=f"{int(self._anim_zoom*100)}%")
        self._anim_redraw()

    def _anim_render_frame(self,fi:int):
        from PIL import Image,ImageDraw as PD,ImageFont
        pw=self._anim_project["width"]; ph=self._anim_project["height"]
        bg=self._anim_project.get("background","#FFFFFF")
        im=Image.new("RGBA",(pw,ph),bg); d=PD.Draw(im)
        for layer in self._anim_project["layers"]:
            if not layer.get("visible",True): continue
            for op in layer["frames"].get(str(fi),[]):
                pts=[(int(x),int(y)) for x,y in op.get("pts",[])]
                t=op.get("tool","Brush"); col=op.get("color","#000"); w=max(1,op.get("width",3))
                if not pts: continue
                if t in ("Brush","Pencil"):
                    if len(pts)>=2: d.line(pts,fill=col,width=w,joint="curve")
                    else:
                        r=max(1,w//2); x,y=pts[0]; d.ellipse((x-r,y-r,x+r,y+r),fill=col)
                elif t=="Line" and len(pts)>=2: d.line([pts[0],pts[-1]],fill=col,width=w)
                elif t=="Rectangle" and len(pts)>=2: d.rectangle([pts[0],pts[-1]],outline=col,width=w)
                elif t=="Ellipse" and len(pts)>=2: d.ellipse([pts[0],pts[-1]],outline=col,width=w)
                elif t=="Fill" and pts:
                    r=80; x,y=pts[0]; d.ellipse((x-r,y-r,x+r,y+r),fill=col)
                elif t=="Text" and pts:
                    try: fnt=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",max(12,w*4))
                    except: fnt=ImageFont.load_default()
                    d.text(pts[0],op.get("text",""),fill=col,font=fnt)
        return im.convert("RGB")

    def _anim_export_gif(self):
        try: from PIL import Image
        except ImportError: messagebox.showinfo(APP,"GIF export needs Pillow.\npip install pillow"); return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".gif",filetypes=[("Animated GIF","*.gif")])
        if not p: return
        try:
            total=self._anim_project["total_frames"]
            frames=[self._anim_render_frame(i) for i in range(total)]
            if not frames: return
            dur=max(20,int(1000/self._anim_project["fps"]))
            frames[0].save(p,save_all=True,append_images=frames[1:],loop=0,duration=dur,optimize=False)
            self.status.set(f"GIF exported: {Path(p).name}")
            messagebox.showinfo("Done",f"Animated GIF saved:\n{p}",parent=self)
        except Exception as exc: messagebox.showerror(APP,str(exc),parent=self)

    def _anim_export_png_seq(self):
        try: from PIL import Image
        except ImportError: messagebox.showinfo(APP,"PNG export needs Pillow.\npip install pillow"); return
        folder=filedialog.askdirectory(parent=self,title="Save PNG frames to folder")
        if not folder: return
        try:
            total=self._anim_project["total_frames"]
            for i in range(total): self._anim_render_frame(i).save(Path(folder)/f"frame_{i+1:04d}.png")
            self.status.set(f"PNG sequence saved in {folder}")
            messagebox.showinfo("Done",f"{total} frames saved in:\n{folder}",parent=self)
        except Exception as exc: messagebox.showerror(APP,str(exc),parent=self)

    def _anim_save(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".has",
                                        filetypes=[("Animation project","*.has")])
        if p:
            Path(p).write_text(json.dumps({"format":"HomeworkAnimationStudio","version":2,**self._anim_project},indent=2,ensure_ascii=False),encoding="utf-8")
            self.status.set(f"Animation saved: {Path(p).name}")

    def _anim_open(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("Animation project","*.has *.json")])
        if p:
            try:
                data=json.loads(Path(p).read_text(encoding="utf-8"))
                self._anim_project=data; self._anim_frame=0; self._anim_layer=1
                self._anim_undo_stack.clear(); self._anim_redo_stack.clear()
                self._anim_refresh_lists(); self._anim_redraw()
            except Exception as exc: messagebox.showerror(APP,str(exc),parent=self)




    # ══════════════════════════════════════════════════════════════════════════
    #  FILE I/O
    # ══════════════════════════════════════════════════════════════════════════
    def _new(self):
        if self.dirty and not self._ask_save():
            return
        self.doc = Document()
        self.path = None
        self.current = 0
        self.history.clear()
        self.future.clear()
        self._load_page()
        self._snapshot()
        self.dirty = False
        self.title(APP)

    def _ask_save(self) -> bool:
        r = messagebox.askyesnocancel(APP, "Save changes first?")
        if r is None:
            return False
        return self._save() if r else True

    def _save(self) -> bool:
        if not self.path:
            return self._save_as()
        self._store()
        self.path.write_text(
            json.dumps(self.doc.payload(), ensure_ascii=False, indent=2),
            encoding="utf-8")
        self.dirty = False
        self.title(self.doc.title + " — " + APP)
        self.status.set("Saved: " + self.path.name)
        return True

    def _save_as(self) -> bool:
        safe = re.sub(r"[^\w -]", "", self.doc.title) or "document"
        p = filedialog.asksaveasfilename(
            title="Save project",
            defaultextension=".hds",
            initialfile=safe + ".hds",
            filetypes=[("Studio project", "*.hds"), ("JSON", "*.json")])
        if not p:
            return False
        self.path = Path(p)
        return self._save()

    def _open(self):
        if self.dirty and not self._ask_save():
            return
        p = filedialog.askopenfilename(
            title="Open or import",
            filetypes=[
                ("All supported",
                 "*.hds *.json *.txt *.md *.html *.htm *.rtf ""*.docx *.pdf *.csv *.xlsx *.pptx "
                 "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("Studio project", "*.hds *.json"),
                ("Documents",      "*.txt *.md *.html *.htm *.rtf *.docx *.pdf"),
                                ("Data",           "*.csv *.xlsx"),
                ("Presentation",   "*.pptx"),
                ("Images",         "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("All files",      "*.*"),
            ])
        if not p:
            return
        try:
            q = Path(p)
            suf = q.suffix.lower()
            if suf in (".txt", ".md"):
                self.doc = Document(title=q.stem)
                self.doc.pages[0].text = q.read_text(encoding="utf-8")
                self.path = None
            elif suf in (".html", ".htm"):
                self.doc = Document(title=q.stem)
                self.doc.pages[0].text = re.sub(
                    r"<[^>]*>", "",
                    html.unescape(q.read_text(encoding="utf-8")))
                self.path = None
            elif suf == ".rtf":
                self.doc = Document(title=q.stem)
                self.doc.pages[0].text = re.sub(
                    r"\\[a-z]+[0-9]* ?|[{}]", "",
                    q.read_text(encoding="utf-8", errors="replace"))
                self.path = None
            elif suf == ".docx":
                try:
                    from docx import Document as Word
                    w = Word(str(q))
                    self.doc = Document(title=q.stem)
                    self.doc.pages = [Page(
                        text="\n".join(pa.text for pa in w.paragraphs))]
                    self.path = None
                except ImportError:
                    raise RuntimeError(
                    "python-docx not installed.\n"
                    "pip install python-docx")
            elif suf == ".pdf":
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(str(q))
                    pages = [Page(text=(pg.extract_text() or "").strip())
                              for pg in reader.pages] or [Page()]
                    self.doc = Document(title=q.stem, pages=pages)
                    self.path = None
                except ImportError:
                    raise RuntimeError(
                    "pypdf not installed.\npip install pypdf")
            elif suf in (".csv", ".xlsx"):
                if suf == ".csv":
                    import csv
                    with q.open(encoding="utf-8-sig", newline="") as f:
                        rows = list(csv.reader(f))
                else:
                    from openpyxl import load_workbook
                    wb = load_workbook(q, data_only=True)
                    ws = wb.active
                    rows = [[str(x) if x is not None else ""
                              for x in r]
                             for r in ws.iter_rows(values_only=True)]
                text = "\n".join(" | ".join(r) for r in rows)
                self.doc = Document(title=q.stem, pages=[Page(text=text)])
                self.path = None
            elif suf == ".pptx":
                try:
                    from pptx import Presentation
                    prs = Presentation(str(q))
                    pages = []
                    for slide in prs.slides:
                        lines = [sh.text for sh in slide.shapes
                                  if hasattr(sh, "text") and sh.text.strip()]
                        pages.append(Page(text="\n".join(lines)))
                    self.doc = Document(title=q.stem,
                                        pages=pages or [Page()])
                    self.path = None
                except ImportError:
                    raise RuntimeError(
                    "python-pptx not installed.\n"
                    "pip install python-pptx")
            elif suf in (".png", ".jpg", ".jpeg",
                          ".gif", ".webp", ".bmp"):
                self.doc = Document(title=q.stem)
                self.doc.pages[0].text = (
                "\n[Image imported — use Draw tools to annotate]\n")
                self.doc.pages[0].elements.append(
                    {"type": "image", "path": str(q), "position": "1.0"})
                self.path = None
            else:
                self.doc = Document.load(
                    json.loads(q.read_text(encoding="utf-8")))
                self.path = q
            self.current = 0
            self.history.clear()
            self.future.clear()
            self._load_page()
            self._snapshot()
            self.dirty = False
            self.status.set("Opened: " + q.name)
            try: self._creations_record_open(q)
            except Exception: pass
            # switch to documents tab
            self._switch_dept("documents")
        except Exception as exc:
            messagebox.showerror(APP,
                "Could not open file.\n" + str(exc))

    def _autosave(self):
        try:
            if self.dirty:
                self._store()
                (RECOVERY / "latest_recovery.hds").write_text(
                    json.dumps(self.doc.payload(),
                               ensure_ascii=False, indent=2),
                    encoding="utf-8")
                self.status.set("Auto-saved")
        finally:
            self.after(
                self.preferences["autosave_seconds"] * 1000,
                self._autosave)

    def _close(self):
        if not self.dirty or self._ask_save():
            self.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    #  EXPORT
    # ══════════════════════════════════════════════════════════════════════════
    def _txt(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Plain text", "*.txt")])
        if p:
            self._store()
            Path(p).write_text(
            "\n".join(x.text for x in self.doc.pages),
                encoding="utf-8")
            self.status.set("Text exported.")

    def _html(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html")])
        if not p:
            return
        self._store()
        pages_html = "".join(
            f'<section class="page">'
            f'<pre>{html.escape(x.text)}</pre>'
            f'</section>'
            for x in self.doc.pages)
        out = (
            f'<!doctype html><meta charset="utf-8">'
            f'<title>{html.escape(self.doc.title)}</title>'
            f'<style>'
            f'body{{font-family:Segoe UI,Arial,sans-serif;'
            f'background:#F0F4F8;margin:0;padding:0}}'
            f'.page{{max-width:210mm;margin:14mm auto;padding:18mm;'
            f'background:white;box-shadow:0 2px 16px #0002}}'
            f'pre{{white-space:pre-wrap;'
            f'font:12pt/1.7 Segoe UI,Arial;margin:0}}'
            f'h1{{color:{self.doc.theme};'
            f'font-family:Segoe UI,Arial;margin:14mm auto 8mm;'
            f'max-width:210mm}}'
            f'@media print{{'
            f'.page{{box-shadow:none;margin:0;page-break-after:always}}'
            f'h1{{margin:10mm 0 6mm}}'
            f'}}'
            f'</style>'
            f'<h1>{html.escape(self.doc.title)}</h1>'
            f'{pages_html}')
        Path(p).write_text(out, encoding="utf-8")
        self.status.set("HTML exported.")

    def _pdf(self):
        try:
            import reportlab  # noqa: F401
        except ImportError:
            if messagebox.askyesno(
                APP,
                "PDF export needs ReportLab.\n"
                "Install it now automatically?"):
                import subprocess, sys
                self.status.set("Installing reportlab…")
                self.update_idletasks()
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "reportlab"],
                        creationflags=0x08000000 if os.name == "nt" else 0)
                    messagebox.showinfo(APP, "ReportLab installed! Please click PDF again.")
                    self.status.set("reportlab installed.")
                except Exception as e:
                    messagebox.showerror(APP, f"Install failed:\n{e}")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")])
        if not p:
            return
        try:
            from reportlab.lib.pagesizes import (
                A4, A5, LETTER, legal,
                landscape as rll)
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.enums import TA_RIGHT, TA_LEFT
            from reportlab.lib.colors import HexColor
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph,
                PageBreak, Spacer)
            self._store()
            sz_map = {
            "A4": A4, "A5": A5,
                "Letter": LETTER, "Legal": legal}
            sz = sz_map.get(self.doc.page_size, A4)
            if self.doc.orientation == "Landscape":
                sz = rll(sz)
            doc_obj = SimpleDocTemplate(
                p, pagesize=sz,
                leftMargin=18*mm, rightMargin=18*mm,
                topMargin=18*mm, bottomMargin=18*mm,
                title=self.doc.title)
            rtl = self.doc.content_language == "Arabic"
            base = ParagraphStyle(
            "base",
                fontName="Helvetica", fontSize=11, leading=17,
                alignment=TA_RIGHT if rtl else TA_LEFT)
            title_s = ParagraphStyle(
            "title", parent=base,
                fontSize=22, leading=27,
                textColor=HexColor(self.doc.theme),
                spaceAfter=14)
            story = [Paragraph(
                html.escape(
                    shaped(self.doc.title) if rtl
                    else self.doc.title),
                title_s)]
            if self.doc.header:
                story.append(Paragraph(
                    html.escape(self.doc.header), base))
                story.append(Spacer(1, 6*mm))
            for n, page in enumerate(self.doc.pages):
                for line in page.text.splitlines():
                    story.append(Paragraph(
                        html.escape(
                            shaped(line) if rtl else line
                        ).replace(" ", "&nbsp;") or "&nbsp;",
                        base))
                if n < len(self.doc.pages) - 1:
                    story.append(PageBreak())
            doc_obj.build(story)
            self.status.set("PDF exported: " + Path(p).name)
        except Exception as exc:
            messagebox.showerror(
                APP, "PDF export failed.\n" + str(exc))

    def _docx(self):
        try:
            from docx import Document as Word
        except ImportError:
            if messagebox.askyesno(
                APP,
                "DOCX export needs python-docx.\n"
                "Install it now automatically?"):
                import subprocess, sys
                self.status.set("Installing python-docx…")
                self.update_idletasks()
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "python-docx"],
                        creationflags=0x08000000 if os.name == "nt" else 0)
                    messagebox.showinfo(APP, "python-docx installed! Please click DOCX again.")
                    self.status.set("python-docx installed.")
                except Exception as e:
                    messagebox.showerror(APP, f"Install failed:\n{e}")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word document", "*.docx")])
        if not p:
            return
        self._store()
        w = Word()
        w.add_heading(self.doc.title, 0)
        for n, page in enumerate(self.doc.pages):
            for line in page.text.splitlines():
                w.add_paragraph(line)
            if n < len(self.doc.pages) - 1:
                w.add_page_break()
        w.save(p)
        self.status.set("DOCX exported.")

    def _export_svg(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG artwork", "*.svg")])
        if not p:
            return
        self._store()
        w, h = page_size(
            self.doc.page_size,
            self.doc.orientation == "Landscape")
        body = "".join(
            f'<text x="{self.doc.margin}" '
            f'y="{self.doc.margin + 38 + i * 28}" '
            f'font-family="Segoe UI,Arial" font-size="18" '
            f'fill="#1E293B">'
            f'{html.escape(line)}</text>'
            for i, line in enumerate(
                self.doc.pages[self.current].text.splitlines()))
        Path(p).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}">'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<rect x="0" y="0" width="{w}" height="14" '
            f'fill="{self.doc.theme}"/>'
            f'{body}</svg>',
            encoding="utf-8")
        self.status.set("SVG exported.")

    def _print(self):
        self._store()
        try:
            target = Path(tempfile.gettempdir()) / (
                re.sub(r"[^\w-]", "_", self.doc.title) + "_print.html")
            pages = "".join(
                f'<section class="page">'
                f'<pre>{html.escape(pg.text)}</pre>'
                f'</section>'
                for pg in self.doc.pages)
            target.write_text(
                f'<!doctype html><meta charset="utf-8">'
                f'<title>{html.escape(self.doc.title)}</title>'
                f'<style>'
                f'@page{{size:{self.doc.page_size};margin:18mm}}'
                f'body{{font-family:Segoe UI,Arial}}'
                f'.page{{page-break-after:always}}'
                f'pre{{white-space:pre-wrap;'
                f'font:12pt/1.65 Segoe UI,Arial}}'
                f'</style>'
                f'<h1 style="color:{self.doc.theme}">'
                f'{html.escape(self.doc.title)}</h1>'
                f'{pages}',
                encoding="utf-8")
            import webbrowser
            webbrowser.open(target.as_uri())
            self.status.set("Opened in browser — use Ctrl+P to print.")
        except Exception as exc:
            messagebox.showerror(APP, str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    #  TRANSLATION  (Google Translate free endpoint, no API key)
    # ══════════════════════════════════════════════════════════════════════════
    def _translate(self):
        try:
            text = self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            messagebox.showinfo(APP, "Select some text first.")
            return
        def _apply_replace(x):
            try:
                self.editor.delete("sel.first", "sel.last")
                self.editor.insert("insert", x)
            except tk.TclError:
                self._insert("\n[Translation: " + x + "]")
        self._do_translate(text, _apply_replace)

    def _translate_page(self):
        self._do_translate(
            self.editor.get("1.0", "end-1c"),
            lambda x: self._insert("\n\n--- Translation ---\n" + x))

    def _do_translate(self, text: str, apply):
        P = PALETTE
        win = tk.Toplevel(self)
        win.title("Translate text")
        win.transient(self)
        win.resizable(False, False)

        ttk.Label(win, text="Translate",
                  font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2,
            padx=18, pady=(18, 4), sticky="w")
        ttk.Label(win,
                  text="Uses Google Translate  •  Internet required.",
                  foreground=P["muted"]).grid(
            row=1, column=0, columnspan=2, padx=18, sticky="w")

        to_var = tk.StringVar(value="Arabic")
        ttk.Label(win, text="Translate to:").grid(
            row=2, column=0, padx=18, pady=10, sticky="w")
        ttk.Combobox(win, textvariable=to_var,
                     values=LANGS, state="readonly",
                     width=20).grid(row=2, column=1, padx=18, pady=10)

        ttk.Label(win, text="Result:").grid(
            row=3, column=0, padx=18, pady=(6, 0), sticky="nw")
        result_box = tk.Text(win, height=8, width=46,
                              wrap="word", font=("Segoe UI", 11))
        result_box.grid(row=4, column=0, columnspan=2,
                         padx=18, pady=4, sticky="ew")

        status_lbl = ttk.Label(win, text="",
                                foreground=P["muted"])
        status_lbl.grid(row=5, column=0, columnspan=2,
                         padx=18, sticky="w")

        def do_translate():
            code = LANG_CODES.get(
                to_var.get().lower(),
                to_var.get()[:2].lower())
            status_lbl.configure(text="Translating...")
            win.update_idletasks()

            def worker():
                try:
                    out = _google_translate(text, code)
                    def _show(o=out):
                        try:
                            result_box.delete("1.0", "end")
                            result_box.insert("1.0", o)
                            status_lbl.configure(text="✓ Translation ready",
                                                 foreground="#16A34A")
                        except Exception: pass
                    if win.winfo_exists(): win.after(0, _show)
                except Exception as exc:
                    err_msg = str(exc)
                    def _err(m=err_msg):
                        try:
                            status_lbl.configure(text="⚠ " + m[:120], foreground="#DC2626")
                        except Exception: pass
                    try:
                        if win.winfo_exists(): win.after(0, _err)
                    except Exception: pass

            threading.Thread(target=worker, daemon=True).start()

        def use_replace():
            out = result_box.get("1.0", "end-1c").strip()
            if out:
                apply(out)
                self._store()
                self._dirt()
                self._snapshot()
                win.destroy()

        def use_insert():
            out = result_box.get("1.0", "end-1c").strip()
            if out:
                self._insert("\n[Translation: " + out + "]")
                win.destroy()

        ttk.Button(win, text="Translate now",
                    command=do_translate).grid(
            row=6, column=0, padx=18, pady=10, sticky="ew")
        br = tk.Frame(win)
        br.grid(row=6, column=1, padx=18, pady=10)
        ttk.Button(br, text="Replace selection",
                    command=use_replace).pack(side="left", padx=2)
        ttk.Button(br, text="Insert copy",
                    command=use_insert).pack(side="left", padx=2)
        win.columnconfigure(0, weight=1)
        win.columnconfigure(1, weight=1)

    # ══════════════════════════════════════════════════════════════════════════
    #  ARABIC DIACRITICS  (Harakat online API + manual palette)
    # ══════════════════════════════════════════════════════════════════════════
    def _diacritics(self):
        P = PALETTE
        win = tk.Toplevel(self)
        win.title("Arabic Diacritics / Tashkeel")
        win.transient(self)
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=12, pady=12)
        manual_tab = tk.Frame(nb)
        auto_tab   = tk.Frame(nb)
        nb.add(manual_tab, text="✋ Manual marks")
        nb.add(auto_tab,   text="🤖 Automatic (online)")

        # Manual tab
        ttk.Label(manual_tab,
                  text="Click a diacritic to insert it at the cursor.\n"
                  "Your existing text is not changed.",
                  wraplength=420, justify="left").pack(
            padx=12, pady=(12, 6))
        mf = tk.Frame(manual_tab)
        mf.pack(padx=12, pady=(0, 12))
        marks = [
            ("\u064e", "Fatha"),
            ("\u064b", "Tanwin Fath"),
            ("\u064f", "Damma"),
            ("\u064c", "Tanwin Damm"),
            ("\u0650", "Kasra"),
            ("\u064d", "Tanwin Kasr"),
            ("\u0652", "Sukun"),
            ("\u0651", "Shadda"),
            ("\u0670", "Dagger Alef"),
                        ("\u0640", "Tatweel"),
            ("\u0621", "Hamza"),
        ]
        for i, (mark, name) in enumerate(marks):
            cell = tk.Frame(mf, relief="solid", bd=1,
                             cursor="hand2", padx=10, pady=6)
            cell.grid(row=i // 4, column=i % 4,
                       padx=4, pady=4)
            lbl_mark = tk.Label(cell, text=mark,
                                 font=("Arial", 22))
            lbl_mark.pack()
            tk.Label(cell, text=name,
                      font=("Segoe UI", 7),
                      fg=P["muted"]).pack()
            for w in (cell, lbl_mark):
                w.bind("<Button-1>",
                        lambda e, m=mark: (
                            self._insert(m), win.destroy()))

        # Automatic tab
        ttk.Label(auto_tab,
                  text="Automatic tashkeel via the free Harakat API "
                  "(harakat.ae).\n"
                  "Internet required. Review before applying.",
                  wraplength=440, justify="left").pack(
            padx=14, pady=(14, 6))
        ttk.Label(auto_tab,
                  text="Source text:").pack(anchor="w", padx=14)
        src_box = tk.Text(auto_tab, height=6, wrap="word",
                           font=("Segoe UI", 11))
        src_box.pack(fill="x", padx=14, pady=(0, 6))
        try:
            src_box.insert("1.0",
                self.editor.get("sel.first", "sel.last"))
        except tk.TclError:
            src_box.insert("1.0",
                self.editor.get("1.0", "end-1c"))

        ttk.Label(auto_tab,
                  text="Result with diacritics:").pack(
            anchor="w", padx=14)
        out_box = tk.Text(auto_tab, height=6, wrap="word",
                           font=("Segoe UI", 11))
        out_box.pack(fill="x", padx=14, pady=(0, 4))

        status_lbl2 = ttk.Label(auto_tab, text="",
                                  foreground=P["muted"])
        status_lbl2.pack(anchor="w", padx=14)

        def run_auto():
            src = src_box.get("1.0", "end-1c").strip()
            if not src:
                return
            status_lbl2.configure(
                text="Contacting Harakat API...")
            win.update_idletasks()

            def worker():
                try:
                    result = _harakat_api(src)
                    def _show(r=result):
                        try:
                            out_box.delete("1.0", "end")
                            out_box.insert("1.0", r)
                            status_lbl2.configure(text="✓ Diacritics ready",
                                                  foreground="#16A34A")
                        except Exception: pass
                    if win.winfo_exists(): win.after(0, _show)
                except Exception as exc:
                    err_msg = str(exc)
                    def _err(m=err_msg):
                        try:
                            status_lbl2.configure(text="⚠ "+m[:140], foreground="#DC2626")
                        except Exception: pass
                    try:
                        if win.winfo_exists(): win.after(0, _err)
                    except Exception: pass

            threading.Thread(target=worker, daemon=True).start()

        def apply_auto():
            result = out_box.get("1.0", "end-1c").strip()
            if not result:
                return
            try:
                self.editor.delete("sel.first", "sel.last")
                self.editor.insert("insert", result)
            except tk.TclError:
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", result)
            self._store()
            self._dirt()
            self._snapshot()
            win.destroy()

        br = tk.Frame(auto_tab)
        br.pack(fill="x", padx=14, pady=10)
        ttk.Button(br, text="Get diacritics",
                    command=run_auto).pack(side="left", padx=4)
        ttk.Button(br, text="Apply to document",
                    command=apply_auto).pack(side="left", padx=4)

    # ══════════════════════════════════════════════════════════════════════════
    #  OTHER REVIEW TOOLS
    # ══════════════════════════════════════════════════════════════════════════
    def _auto_correct(self):
        try:
            text = self.editor.get("sel.first", "sel.last")
            def repl(x):
                try:
                    self.editor.delete("sel.first", "sel.last")
                    self.editor.insert("insert", x)
                except tk.TclError:
                    pass
        except tk.TclError:
            text = self.editor.get("1.0", "end-1c")
            repl = lambda x: (
                self.editor.delete("1.0", "end"),
                self.editor.insert("1.0", x))
        original = text
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n*", "\n", text)
        text = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", text)
        fixes = {
        "teh": "the", "adn": "and", "recieve": "receive",
            "definately": "definitely", "seperate": "separate",
            "wierd": "weird", "dont": "don't", "cant": "can't",
            "im": "I'm", "alot": "a lot", "occured": "occurred",
            "accomodate": "accommodate", "untill": "until",
            "wont": "won't", "isnt": "isn't", "doesnt": "doesn't",
            "youre": "you're", "theyre": "they're",
            "weve": "we've", "ive": "I've",
        }
        for w, r in fixes.items():
            text = re.sub(r"\b" + w + r"\b", r, text,
                           flags=re.IGNORECASE)
        if self.preferences.get("smart_typography", True):
            text = text.replace("...", "\u2026").replace("--", "\u2014")
        if text == original:
            messagebox.showinfo(APP, "No safe corrections found.")
            return
        if messagebox.askyesno(APP, "Apply corrections? (undoable)"):
            repl(text)
            self._store()
            self._dirt()
            self._snapshot()
            self.status.set("Auto-correct applied.")

    def _words(self):
        text = "\n".join(p.text for p in self.doc.pages)
        words = len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))
        messagebox.showinfo(APP,
            f"Pages:               {len(self.doc.pages)}\n"
            f"Words:               {words:,}\n"
            f"Characters (spaces): {len(text):,}\n"
            f"Characters (no sp):  {len(text.replace(' ','')):,}\n"
            f"Paragraphs:          "
            f"{len([l for l in text.splitlines() if l.strip()]):,}")

    def _find_replace(self):
        win = tk.Toplevel(self)
        win.title("Find & Replace")
        win.transient(self)
        win.resizable(False, False)

        find_var  = tk.StringVar()
        repl_var  = tk.StringVar()
        case_var  = tk.BooleanVar(value=False)
        regex_var = tk.BooleanVar(value=False)

        ttk.Label(win, text="Find:").grid(
            row=0, column=0, padx=12, pady=8, sticky="w")
        ttk.Entry(win, textvariable=find_var, width=38).grid(
            row=0, column=1, padx=12, pady=8, columnspan=2)
        ttk.Label(win, text="Replace with:").grid(
            row=1, column=0, padx=12, pady=4, sticky="w")
        ttk.Entry(win, textvariable=repl_var, width=38).grid(
            row=1, column=1, padx=12, pady=4, columnspan=2)
        ttk.Checkbutton(win, text="Case sensitive",
                        variable=case_var).grid(
            row=2, column=0, padx=12, sticky="w")
        ttk.Checkbutton(win, text="Regular expression",
                        variable=regex_var).grid(
            row=2, column=1, sticky="w")

        count_lbl = ttk.Label(win, text="",
                               foreground=PALETTE["muted"])
        count_lbl.grid(row=4, column=0, columnspan=3,
                        padx=12, pady=2, sticky="w")

        def _flags():
            return 0 if case_var.get() else re.IGNORECASE

        def find_next():
            pat = find_var.get()
            if not pat:
                return
            if not regex_var.get():
                pat = re.escape(pat)
            text = self.editor.get("1.0", "end-1c")
            try:
                cur = self.editor.index("insert")
                rn, cn = map(int, cur.split("."))
                start_char = sum(
                    len(l) + 1
                    for l in text.split("\n")[:rn - 1]) + cn
            except Exception:
                start_char = 0
            m = re.search(pat, text[start_char:], flags=_flags())
            if not m:
                m = re.search(pat, text, flags=_flags())
                pos = m.start() if m else None
            else:
                pos = start_char + m.start()
            if pos is None:
                count_lbl.configure(text="Not found.")
                return
            found = re.search(pat, text[pos:], flags=_flags())
            end_pos = pos + len(found.group())
            ls = text[:pos].split("\n")
            le = text[:end_pos].split("\n")
            self.editor.tag_remove("sel", "1.0", "end")
            self.editor.tag_add(
            "sel",
                f"{len(ls)}.{len(ls[-1])}",
                f"{len(le)}.{len(le[-1])}")
            self.editor.mark_set(
            "insert", f"{len(le)}.{len(le[-1])}")
            self.editor.see("insert")
            count_lbl.configure(text="Match found.")

        def replace_one():
            find_next()
            try:
                sel = self.editor.get("sel.first", "sel.last")
                pat = find_var.get()
                if not regex_var.get():
                    pat = re.escape(pat)
                if re.fullmatch(pat, sel, flags=_flags()):
                    self.editor.delete("sel.first", "sel.last")
                    self.editor.insert("insert", repl_var.get())
                    self._store()
                    self._dirt()
                    self._snapshot()
            except tk.TclError:
                pass

        def replace_all():
            pat = find_var.get()
            rep = repl_var.get()
            if not pat:
                return
            if not regex_var.get():
                pat = re.escape(pat)
            text = self.editor.get("1.0", "end-1c")
            new, n = re.subn(pat, rep, text, flags=_flags())
            if n:
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", new)
                self._store()
                self._dirt()
                self._snapshot()
                count_lbl.configure(
                    text=f"Replaced {n} occurrence(s).")
            else:
                count_lbl.configure(text="No matches found.")

        bf = tk.Frame(win)
        bf.grid(row=3, column=0, columnspan=3,
                 padx=8, pady=10)
        for label, cmd in [
            ("Find next", find_next),
            ("Replace", replace_one),
            ("Replace all", replace_all),
        ]:
            ttk.Button(bf, text=label, command=cmd).pack(
                side="left", padx=4)

    def _read_aloud(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            try:
                text = self.editor.get("sel.first", "sel.last")
            except tk.TclError:
                text = self.editor.get("1.0", "end-1c")
            engine.say(text[:3000])
            engine.runAndWait()
        except ImportError:
            messagebox.showinfo(
                APP,
                "Read aloud needs pyttsx3.\n"
                "Install:  pip install pyttsx3")

    # ══════════════════════════════════════════════════════════════════════════
    #  PRESENTATION MODE
    # ══════════════════════════════════════════════════════════════════════════
    def _present(self):
        self._store()
        tab = self._dept_nb.index("current")
        if tab == 3:
            slides   = self._slides
            get_text = lambda s: s["text"]
            get_bg   = lambda s: s.get("background", "#1E2D40")
        else:
            slides   = self.doc.pages
            get_text = lambda p: p.text
            get_bg   = lambda p: "#1E2D40"
        if not slides:
            return
        win = tk.Toplevel(self)
        win.title(self.doc.title + " — Presentation")
        win.configure(bg="black")
        win.attributes("-fullscreen", True)
        idx = {"v": 0}

        label = tk.Label(
            win, bg="#1E2D40", fg="white",
            justify="left", anchor="nw",
            font=("Segoe UI", 24),
            padx=90, pady=70,
            wraplength=1200)
        label.pack(fill="both", expand=True, padx=70, pady=60)

        note = tk.Label(
            win, bg="black", fg="#64748B",
            font=("Segoe UI", 10),
            text=("  \u2190 / \u2192  navigate    "
            "Space = auto-play    Esc = exit"))
        note.pack(pady=10)

        auto = {"id": None}

        def show(d=0):
            idx["v"] = (idx["v"] + d) % len(slides)
            s = slides[idx["v"]]
            label.configure(text=get_text(s), bg=get_bg(s))
            win.title(
                f"{self.doc.title} "
                f"— {idx['v']+1}/{len(slides)}")

        def autoplay(event=None):
            if auto["id"]:
                win.after_cancel(auto["id"])
                auto["id"] = None
                note.configure(text="Auto-play stopped")
            else:
                ms = max(1, int(
                    self.preferences.get(
                    "presentation_seconds", 4))) * 1000
                def tick():
                    show(1)
                    auto["id"] = win.after(ms, tick)
                auto["id"] = win.after(ms, tick)
                note.configure(
                    text=(f"Auto-play every {ms//1000}s "
                          f"— Space to stop"))

        win.bind("<Right>",  lambda e: show(1))
        win.bind("<Left>",   lambda e: show(-1))
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<space>",  autoplay)
        show()

    def _animation_settings(self):
        win = tk.Toplevel(self)
        win.title("Slide transition")
        win.transient(self)
        ttk.Label(win, text="Presentation transition",
                  font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=16, pady=(16, 4))
        choice = tk.StringVar(
            value=self.doc.metadata.get("transition", "Fade"))
        for v in ("None", "Fade", "Quick fade",
                   "Slide", "Zoom", "Dissolve", "Typewriter"):
            ttk.Radiobutton(win, text=v, value=v,
                            variable=choice).pack(
                anchor="w", padx=20, pady=2)
        def save():
            self.doc.metadata["transition"] = choice.get()
            self._dirt()
            self._snapshot()
            win.destroy()
        ttk.Button(win, text="Save", command=save).pack(
            fill="x", padx=16, pady=16)

    # ══════════════════════════════════════════════════════════════════════════
    #  SETTINGS
    # ══════════════════════════════════════════════════════════════════════════
    def _settings(self):
        P = PALETTE
        win = tk.Toplevel(self)
        win.title("Studio settings")
        win.transient(self)
        win.resizable(False, False)

        ttk.Label(win, text="Studio settings",
                  font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2,
            padx=20, pady=(20, 4), sticky="w")
        ttk.Label(win,
                  text="Settings are saved locally on this computer.",
                  foreground=P["muted"]).grid(
            row=1, column=0, columnspan=2,
            padx=20, pady=(0, 12), sticky="w")

        theme_v    = tk.StringVar(
            value=self.preferences["ui_theme"])
        scale_v    = tk.IntVar(
            value=self.preferences["font_scale"])
        autosave_v = tk.IntVar(
            value=self.preferences["autosave_seconds"])
        tips_v     = tk.BooleanVar(
            value=self.preferences["show_tips"])
        correct_v  = tk.BooleanVar(
            value=self.preferences["auto_correct"])
        smart_v    = tk.BooleanVar(
            value=self.preferences["smart_typography"])
        lang_v     = tk.StringVar(
            value=self.preferences["default_language"])
        psec_v     = tk.IntVar(
            value=self.preferences["presentation_seconds"])

        fields = [
            ("Appearance",
             theme_v,    ["Light", "Dark", "Ocean", "Sunset", "Forest"]),
            ("Interface scale %",
             scale_v,    None),
            ("Autosave interval (seconds)",
             autosave_v, None),
            ("Default document language",
             lang_v,     LANGS),
            ("Presentation auto-play (seconds)",
             psec_v,     None),
        ]
        for row, (lbl, var, values) in enumerate(fields, 2):
            ttk.Label(win, text=lbl).grid(
                row=row, column=0,
                padx=20, pady=6, sticky="w")
            if values:
                ttk.Combobox(win, textvariable=var,
                              values=values, state="readonly",
                              width=24).grid(
                    row=row, column=1, padx=20, pady=6)
            elif isinstance(var, tk.IntVar):
                ttk.Spinbox(win, from_=1, to=600,
                             increment=5, textvariable=var,
                             width=8).grid(
                    row=row, column=1,
                    padx=20, pady=6, sticky="w")

        for row, (txt, var) in enumerate([
            ("Show helpful status tips", tips_v),
            ("Enable auto-correction", correct_v),
            ("Smart punctuation  (-- \u2192 \u2014,  ... \u2192 \u2026)",
             smart_v),
        ], 7):
            ttk.Checkbutton(win, text=txt,
                            variable=var).grid(
                row=row, column=0, columnspan=2,
                padx=20, pady=3, sticky="w")

        def apply():
            self.preferences.update({
            "ui_theme":            theme_v.get(),
                "font_scale":          scale_v.get(),
                "autosave_seconds":    autosave_v.get(),
                "show_tips":           tips_v.get(),
                "auto_correct":        correct_v.get(),
                "smart_typography":    smart_v.get(),
                "default_language":    lang_v.get(),
                "presentation_seconds": psec_v.get(),
            })
            self._save_prefs()
            self._apply_theme()
            self._full_ui_refresh()
            win.destroy()
            self.status.set("Settings saved — theme applied.")

        ttk.Button(win, text="Save settings",
                    command=apply).grid(
            row=10, column=0, columnspan=2,
            padx=20, pady=(12, 20), sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    #  TEMPLATES
    # ══════════════════════════════════════════════════════════════════════════
    _TMPL = {
        "Homework Sheet": (
            "Homework Sheet\n"
            "Name: ________________________  Class: __________  Date: __________\n\n"
            "1.\n________________________________________________________________\n\n"
            "2.\n________________________________________________________________\n\n"
            "3.\n________________________________________________________________\n"),
        "Worksheet": (
            "Worksheet\n"
            "Name: ________________________  Date: __________\n\n"
            "Question 1\n________________________________________________________________\n\n"
            "Question 2\n________________________________________________________________\n"),
        "Quiz": (
            "Quiz\n"
            "Name: ________________________  Score: _____ / _____\n\n"
            "1.  A)       B)       C)       D)\n"
            "2.  A)       B)       C)       D)\n"
            "3.  A)       B)       C)       D)\n"
            "4.  A)       B)       C)       D)\n"
            "5.  A)       B)       C)       D)\n"),
        "Test": (
            "Test\n"
            "Name: ________________________  Date: __________  Mark: _____ / _____\n\n"
            "Section A  — Short answers\n\n"
            "1.  _______________________________________________\n\n"
            "2.  _______________________________________________\n\n"
            "Section B  — Long answer\n\n"
            "________________________________________________________________\n"
            "________________________________________________________________\n"
            "________________________________________________________________\n"),
        "Answer Sheet": (
            "Answer Sheet\n"
            "Name: ________________________  Date: __________\n\n"
            "1.  ___________________\n"
            "2.  ___________________\n"
            "3.  ___________________\n"
            "4.  ___________________\n"
            "5.  ___________________\n"),
        "Revision Sheet": (
            "Revision Sheet\n"
            "Topic: ________________________  Date: __________\n\n"
            "Key points to remember:\n\n"
            "1.\n2.\n3.\n\n"
            "Practice questions:\n\n"
            "________________________________________________________________\n"),
        "Flashcards": (
            "FLASHCARD\nFront: Term or question\nBack:  Definition or answer\n\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            "FLASHCARD\nFront: Term or question\nBack:  Definition or answer\n"),
        "Study Guide": (
            "Study Guide\n"
            "Topic: ________________________  Date: __________\n\n"
            "Key Concepts\n1. \n2. \n3. \n\n"
            "Important Terms\n"
            "Term:  ___________  Meaning: ___________________________\n"
            "Term:  ___________  Meaning: ___________________________\n\n"
            "Summary\n\n\nReview Questions\n1. \n2. \n3. \n"),
        "Vocabulary Sheet": (
            "Vocabulary Sheet\n"
            "Name: ________________________\n\n"
            "Word          Definition                    Sentence\n"
            "_________     ________________________     ________________________\n"
            "_________     ________________________     ________________________\n"
            "_________     ________________________     ________________________\n"),
        "Reading Comprehension": (
            "Reading Comprehension\n"
            "Name: ________________________  Date: __________\n\n"
            "Read the passage and answer the questions.\n\n"
            "Passage:\n________________________________________________________________\n"
            "________________________________________________________________\n\n"
            "1. What is the main idea?\n________________________________________________________________\n\n"
            "2. Find evidence from the text:\n________________________________________________________________\n"),
        "Math Worksheet": (
            "Math Worksheet\n"
            "Name: ________________________  Score: _____ / _____\n\n"
            "Solve the following:\n\n"
            "1.  _______  +  _______  =  _______\n"
            "2.  _______  -  _______  =  _______\n"
            "3.  _______  x  _______  =  _______\n"
            "4.  _______  \u00f7  _______  =  _______\n"),
        "Science Worksheet": (
            "Science Worksheet\n"
            "Topic: ________________________  Name: ________________________\n\n"
            "Hypothesis:\n________________________________________________________________\n\n"
            "Observations:\n________________________________________________________________\n\n"
            "Conclusion:\n________________________________________________________________\n"),
        "Arabic Worksheet": (
            "\u0648\u0631\u0642\u0629 \u0639\u0645\u0644 \u0627\u0644\u0644\u063a\u0629 \u0627\u0644\u0639\u0631\u0628\u064a\u0629\n"
            "\u0627\u0644\u0627\u0633\u0645: ____________________    \u0627\u0644\u0635\u0641: __________\n\n"
            "\u0627\u0644\u0633\u0624\u0627\u0644 \u0627\u0644\u0623\u0648\u0644:\n"
            "________________________________________________________________\n\n"
            "\u0627\u0644\u0633\u0624\u0627\u0644 \u0627\u0644\u062b\u0627\u0646\u064a:\n"
            "________________________________________________________________\n"),
        "Essay Sheet": (
            "Essay\nTitle: ________________________  Name: ________________________\n\n"
            "Introduction:\n________________________________________________________________\n\n"
            "Body paragraph 1:\n________________________________________________________________\n\n"
            "Body paragraph 2:\n________________________________________________________________\n\n"
            "Conclusion:\n________________________________________________________________\n"),
        "Blank Document": (""),
        "Professional Report": (
            "REPORT TITLE\nAuthor:                            Date:\n\n"
            "EXECUTIVE SUMMARY\n\n\nINTRODUCTION\n\n\nFINDINGS\n\n\nRECOMMENDATIONS\n\n\nCONCLUSION\n"),
        "Letter": (
            "Your Name\nYour Address\nCity, Country\nDate\n\n"
            "Recipient Name\nRecipient Address\n\nDear [Name],\n\n"
            "I am writing to...\n\n"
            "Yours sincerely,\n\n"
            "Your Name\n"),
        "Meeting Notes": (
            "MEETING NOTES\n"
            "Date: __________  Time: __________  Location: __________\n"
            "Attendees: ____________________________________________\n\n"
            "Agenda\n1. \n2. \n3. \n\nDiscussion\n\n\nDecisions\n\u2022 \n\n"
            "Action Items\nOwner:          Task:                   Due:\n"),
        "Research Notes": (
            "Research Notes\nTopic: ________________________  Date: __________\n\n"
            "Source 1:\n________________________________________________________________\n\n"
            "Source 2:\n________________________________________________________________\n\n"
            "Key findings:\n\u2022 \n\u2022 \n\u2022 \n"),
        "Certificate": (
            "CERTIFICATE OF ACHIEVEMENT\n\n"
            "This is to certify that\n\n"
            "________________________\n\n"
            "has successfully completed\n\n"
            "________________________\n\n"
            "Date: __________        Signature: __________\n"),
        "Resume/CV": (
            "FULL NAME\nEmail:                Phone:               Location:\n\n"
            "PROFILE\n_______________________________________________\n\n"
            "EXPERIENCE\nJob Title  \u2014  Company  \u2014  Year\u2013Year\n\u2022 Achievement\n\u2022 Achievement\n\n"
            "EDUCATION\nDegree  \u2014  Institution  \u2014  Year\n\n"
            "SKILLS\n\u2022 \n\u2022 \n\u2022 \n"),
        "Invoice": (
            "INVOICE\nFrom: ____________________\nTo:   ____________________\n"
            "Date: ____________________    Invoice #: ____________\n\n"
            "Item                        Qty   Unit Price   Total\n"
            "\u2500"*52+"\n\n\n"
            "\u2500"*52+"\n"
            "                            TOTAL:\n"),
        "Form": (
            "FORM\nTitle: ________________________\n\n"
            "Full name:     ________________________\n"
            "Date:          ________________________\n"
            "Email:         ________________________\n\n"
            "Details:\n________________________________________________________________\n\n"
            "Signature: ________________________  Date: __________\n"),
        "Project Proposal": (
            "PROJECT PROPOSAL\nTitle:  ________________________\nAuthor: ________________________  Date: __________\n\n"
            "Overview\n\n\nObjectives\n\u2022 \n\u2022 \n\u2022 \n\n"
            "Timeline\nPhase 1:  \nPhase 2:  \nPhase 3:  \n\n"
            "Budget estimate\n\n\nSuccess criteria\n"),
        "Daily Planner": (
            "DAILY PLANNER  \u2014  Date: ____________________\n\n"
            "Top 3 priorities\n1. \n2. \n3. \n\n"
            "Schedule\n"
            "07:00  ___________________________\n08:00  ___________________________\n"
            "09:00  ___________________________\n10:00  ___________________________\n"
            "11:00  ___________________________\n12:00  ___________________________\n"
            "13:00  ___________________________\n14:00  ___________________________\n"
            "15:00  ___________________________\n\nNotes\n\n\nWin of the day\n"),
        "Weekly Planner": (
            "WEEKLY PLANNER  \u2014  Week of: ____________________\n\n"
            "Monday:    __________________________________________\n"
            "Tuesday:   __________________________________________\n"
            "Wednesday: __________________________________________\n"
            "Thursday:  __________________________________________\n"
            "Friday:    __________________________________________\n"
            "Weekend:   __________________________________________\n\n"
            "Goals this week\n\u2022 \n\u2022 \n\u2022 \n"),
        "Monthly Planner": (
            "MONTHLY PLANNER  \u2014  Month: ____________________\n\n"
            "Week 1: ________________________\n"
            "Week 2: ________________________\n"
            "Week 3: ________________________\n"
            "Week 4: ________________________\n\n"
            "Goals: \n\u2022 \n\u2022 \n"),
        "Timetable": (
            "TIMETABLE\n\n"
            "         Mon         Tue         Wed         Thu         Fri\n"
            "08:00    ________    ________    ________    ________    ________\n"
            "09:00    ________    ________    ________    ________    ________\n"
            "10:00    ________    ________    ________    ________    ________\n"
            "11:00    ________    ________    ________    ________    ________\n"
            "12:00    ________    ________    ________    ________    ________\n"),
        "Study Planner": (
            "STUDY PLANNER\nExam: ________________________  Date: __________\n\n"
            "Topics to cover:\n\u2022 \n\u2022 \n\u2022 \n\n"
            "Day 1: ________________________\n"
            "Day 2: ________________________\n"
            "Day 3: ________________________\n\n"
            "Resources needed:\n"),
        "Habit Tracker": (
            "HABIT TRACKER  \u2014  Month: ____________________\n\n"
            "Habit                  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15\n"
            "_____________________  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1\n"
            "_____________________  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1\n"
            "_____________________  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1  \u25a1\n"),
        "Poster": (
            "HEADLINE\n\nSubheadline or tagline\n\n"
            "Main message \u2014 short and impactful.\n\n"
            "\u2022 Key point 1\n\u2022 Key point 2\n\u2022 Key point 3\n\n"
            "Call to action:          Contact info:\n"),
        "Flyer": (
            "EVENT TITLE\n\nDate:     ____________________\n"
            "Time:     ____________________\nVenue:    ____________________\n\n"
            "Details:\n________________________________________________________________\n\n"
            "Contact: ________________________\n"),
        "Mind Map": (
            "MIND MAP\nCentral topic: ________________________\n\n"
            "Branch 1: ________________________\n  - \n  - \n\n"
            "Branch 2: ________________________\n  - \n  - \n\n"
            "Branch 3: ________________________\n  - \n  - \n"),
        "Storyboard": (
            "STORYBOARD\nProject: ____________________  Date: ____________\n\n"
            "Scene 1\nVisual: ____________________________________________\nAudio:  ____________________________________________\n\n"
            "Scene 2\nVisual: ____________________________________________\nAudio:  ____________________________________________\n\n"
            "Scene 3\nVisual: ____________________________________________\nAudio:  ____________________________________________\n"),
        "Presentation Page": (
            "PRESENTATION TITLE\n\nSlide 1: Introduction\n\nSlide 2: Main point\n\nSlide 3: Evidence\n\nSlide 4: Conclusion\n"),
        "Social Media Post": (
            "SOCIAL MEDIA POST\nPlatform: ________________________\n\n"
            "Caption:\n________________________________________________________________\n\n"
            "Hashtags: #\n\nCall to action:\n"),
        "Newsletter": (
            "NEWSLETTER\nIssue: ________  Date: ________\n\n"
            "HEADLINE STORY\n________________________________________________________________\n\n"
            "FEATURE ARTICLE\n________________________________________________________________\n\n"
            "ANNOUNCEMENTS\n\u2022 \n\u2022 \n"),
    }


    def _template_gallery(self):
        win = tk.Toplevel(self)
        win.title("Template gallery")
        win.geometry("840x620")
        win.transient(self)

        ttk.Label(win, text="Template gallery",
                  font=("Segoe UI", 17, "bold")).pack(
            anchor="w", padx=20, pady=(18, 2))
        ttk.Label(win,
                  text="Choose a template, preview it on the right, "
                  "then click  Use template.",
                  foreground=PALETTE["muted"]).pack(
            anchor="w", padx=20, pady=(0, 10))

        body = ttk.Panedwindow(win, orient="horizontal")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        left  = tk.Frame(body)
        right = tk.Frame(body)
        body.add(left,  weight=1)
        body.add(right, weight=2)

        cat_var = tk.StringVar(value="All")
        ttk.Combobox(left, textvariable=cat_var,
                     values=["All", "School", "Documents",
                              "Planning", "Creative"],
                     state="readonly").pack(
            fill="x", pady=(0, 6), padx=4)

        choices = tk.Listbox(left, font=("Segoe UI", 10),
                              relief="flat", bd=0,
                              activestyle="none",
                              exportselection=False)
        choices.pack(fill="both", expand=True, padx=4)

        preview = tk.Text(right, wrap="word",
                           font=("Segoe UI", 10),
                           relief="flat", bd=0,
                           state="disabled")
        preview.pack(fill="both", expand=True,
                      padx=8, pady=4)

        visible: list = []

        def refresh(*_):
            visible[:] = [
                x for x in TEMPLATES
                if cat_var.get() == "All"
                or x[0] == cat_var.get()]
            choices.delete(0, "end")
            for _, name in visible:
                choices.insert("end", f"  {name}")

        def on_select(*_):
            s = choices.curselection()
            if not s:
                return
            _, name = visible[s[0]]
            sample = self._TMPL.get(
                name,
                f"{name}\n\nA clean, editable document layout.")
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert(
            "1.0",
                f"Template: {name}\n"
                + "\u2500" * 40 + "\n"
                + sample[:700])
            preview.configure(state="disabled")

        def use(*_):
            s = choices.curselection()
            if not s:
                return
            cat, name = visible[s[0]]
            self._create_template(cat, name)
            win.destroy()

        cat_var.trace_add("write", refresh)
        choices.bind("<<ListboxSelect>>", on_select)
        choices.bind("<Double-1>", use)
        ttk.Button(win, text="Use selected template",
                    command=use).pack(
            fill="x", padx=20, pady=(0, 18))
        refresh()

    def _create_template(self, cat: str, name: str):
        content = self._TMPL.get(
            name,
            f"{name}\n\nStart editing here.\n\n"
            f"\u2022 Point one\n\u2022 Point two\n")
        self.doc = Document(
            title=name,
            content_language=(
            "Arabic" if "Arabic" in name else "English"))
        self.doc.pages[0].text = content
        self.current = 0
        self.path = None
        self.history.clear()
        self.future.clear()
        self._load_page()
        self._dirt()
        self._snapshot()
        self._switch_dept("documents")
        self.status.set("Template loaded: " + name)

    def _save_template(self):
        name = simpledialog.askstring(
            APP, "Template name:",
            initialvalue=self.doc.title, parent=self)
        if not name:
            return
        folder = DATA / "templates"
        folder.mkdir(exist_ok=True)
        safe = re.sub(r"[^\w -]", "_", name).strip() or "template"
        self._store()
        (folder / (safe + ".hds")).write_text(
            json.dumps(self.doc.payload(),
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        self.status.set("Template saved: " + safe)

    # ══════════════════════════════════════════════════════════════════════════
    #  OFFLINE ARTWORK MAKER
    # ══════════════════════════════════════════════════════════════════════════
    def _asset_maker(self):
        win = tk.Toplevel(self)
        win.title("Offline Artwork Maker")
        win.transient(self)
        win.resizable(False, False)

        ttk.Label(win, text="Create local artwork",
                  font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2,
            padx=16, pady=(16, 8), sticky="w")
        ttk.Label(win,
                  text="Generates SVG (always) or raster image "
                  "(needs Pillow). Saved in your assets folder.",
                  foreground=PALETTE["muted"],
                  wraplength=420).grid(
            row=1, column=0, columnspan=2,
            padx=16, pady=(0, 8), sticky="w")

        vals = {
        "Title":   tk.StringVar(value=self.doc.title),
            "Subtitle":tk.StringVar(value=""),
            "Style":   tk.StringVar(value="Modern poster"),
            "Primary": tk.StringVar(value=self.doc.theme),
            "Accent":  tk.StringVar(value="#F59E0B"),
            "Width":   tk.IntVar(value=1600),
            "Height":  tk.IntVar(value=900),
            "Format":  tk.StringVar(value="SVG"),
        }
        row = 2
        for lbl, key in [
            ("Title",        "Title"),
            ("Subtitle",     "Subtitle"),
            ("Style",        "Style"),
            ("Primary color","Primary"),
            ("Accent color", "Accent"),
        ]:
            ttk.Label(win, text=lbl).grid(
                row=row, column=0,
                padx=16, pady=4, sticky="w")
            if key == "Style":
                ttk.Combobox(
                    win, textvariable=vals[key],
                    values=["Modern poster", "Study card",
                             "Gradient", "Social graphic",
                             "Infographic", "Sticker"],
                    state="readonly", width=28).grid(
                    row=row, column=1, padx=16, pady=4)
            else:
                ttk.Entry(win, textvariable=vals[key],
                           width=32).grid(
                    row=row, column=1, padx=16, pady=4)
            row += 1

        sf = tk.Frame(win)
        sf.grid(row=row, column=1,
                 padx=16, pady=4, sticky="w")
        ttk.Label(win, text="Canvas size").grid(
            row=row, column=0, padx=16, pady=4, sticky="w")
        ttk.Spinbox(sf, from_=256, to=7680,
                    textvariable=vals["Width"],
                    width=6).pack(side="left")
        ttk.Label(sf, text=" \u00d7 ").pack(side="left")
        ttk.Spinbox(sf, from_=256, to=4320,
                    textvariable=vals["Height"],
                    width=6).pack(side="left")
        row += 1

        ttk.Label(win, text="Output format").grid(
            row=row, column=0, padx=16, pady=4, sticky="w")
        ttk.Combobox(win, textvariable=vals["Format"],
                     values=["SVG", "PNG", "JPG", "WEBP"],
                     state="readonly", width=10).grid(
            row=row, column=1,
            padx=16, pady=4, sticky="w")
        row += 1

        # Canvas size presets
        ttk.Label(win, text="Presets").grid(
            row=row, column=0, padx=16, pady=(8, 2), sticky="nw")
        pf = tk.Frame(win)
        pf.grid(row=row, column=1, padx=16, pady=(8, 2), sticky="w")
        for lbl, pw, ph in [
            ("1080\u00d71080", 1080, 1080),
            ("1920\u00d71080", 1920, 1080),
            ("1080\u00d71920", 1080, 1920),
            ("A4",             794,  1123),
            ("Banner",        1200,  628),
        ]:
            ttk.Button(
                pf, text=lbl,
                command=lambda w=pw, h=ph: (
                    vals["Width"].set(w),
                    vals["Height"].set(h))).pack(
                side="left", padx=2)
        row += 1

        def make():
            try:
                v = {k: vr.get() for k, vr in vals.items()}
                folder = DATA / "assets"
                folder.mkdir(exist_ok=True)
                title   = str(v["Title"]).strip() or "Artwork"
                safe    = re.sub(r"[^\w-]", "_", title)[:40] or "art"
                fmt     = str(v["Format"]).lower()
                path    = folder / (safe + "." + fmt)
                n = 2
                while path.exists():
                    path = folder / (safe + f"-{n}.{fmt}")
                    n += 1
                w, h    = int(v["Width"]), int(v["Height"])
                primary = str(v["Primary"])
                accent  = str(v["Accent"])
                te      = html.escape(title)
                sub     = html.escape(str(v["Subtitle"]))
                style   = str(v["Style"])
                # SVG is the universal offline fallback
                svg = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" '
                    f'width="{w}" height="{h}">'
                    f'<defs>'
                    f'<linearGradient id="g" '
                    f'x1="0" y1="0" x2="1" y2="1">'
                    f'<stop stop-color="{primary}"/>'
                    f'<stop offset="1" stop-color="{accent}"/>'
                    f'</linearGradient>'
                    f'<filter id="sh">'
                    f'<feDropShadow dx="0" dy="12" '
                    f'stdDeviation="16" flood-opacity=".22"/>'
                    f'</filter>'
                    f'</defs>'
                    f'<rect width="100%" height="100%" '
                    f'fill="url(#g)"/>'
                    f'<circle cx="{w*.85:.0f}" cy="{h*.2:.0f}" '
                    f'r="{min(w,h)*.18:.0f}" '
                    f'fill="white" opacity=".13"/>'
                    f'<rect x="{w*.07:.0f}" y="{h*.17:.0f}" '
                    f'width="{w*.86:.0f}" height="{h*.66:.0f}" '
                    f'rx="{min(w,h)*.03:.0f}" '
                    f'fill="white" opacity=".94" filter="url(#sh)"/>'
                    f'<text x="{w*.13:.0f}" y="{h*.46:.0f}" '
                    f'font-family="Segoe UI,Arial" '
                    f'font-size="{max(34,min(w,h)//10)}" '
                    f'font-weight="700" fill="{primary}">'
                    f'{te}</text>'
                    f'<text x="{w*.13:.0f}" y="{h*.58:.0f}" '
                    f'font-family="Segoe UI,Arial" '
                    f'font-size="{max(16,min(w,h)//26)}" '
                    f'fill="#253044">{sub}</text>'
                    f'<text x="{w*.13:.0f}" y="{h*.75:.0f}" '
                    f'font-family="Segoe UI,Arial" '
                    f'font-size="{max(12,min(w,h)//50)}" '
                    f'fill="{accent}">'
                    f'{html.escape(style.upper())} \u2022 '
                    f'OFFLINE</text>'
                    f'</svg>')
                if fmt == "svg":
                    path.write_text(svg, encoding="utf-8")
                else:
                    try:
                        from PIL import Image, ImageDraw, ImageFont

                        def rgb(x):
                            x = x.lstrip("#")
                            if len(x) == 3:
                                x = "".join(c * 2 for c in x)
                            return tuple(
                                int(x[i:i+2], 16)
                                for i in (0, 2, 4))

                        a, b = rgb(primary), rgb(accent)
                        im   = Image.new("RGB", (w, h), a)
                        draw = ImageDraw.Draw(im)
                        for y2 in range(h):
                            mix = y2 / max(1, h - 1)
                            draw.line(
                                (0, y2, w, y2),
                                fill=tuple(
                                    int(a[i] + (b[i]-a[i])*mix)
                                    for i in range(3)))
                        draw.rounded_rectangle(
                            (int(w*.07), int(h*.17),
                             int(w*.93), int(h*.83)),
                            radius=int(min(w, h)*.03),
                            fill="white")
                        try:
                            f1 = ImageFont.truetype(
                            "C:/Windows/Fonts/segoeuib.ttf",
                                max(34, min(w, h) // 10))
                            f2 = ImageFont.truetype(
                            "C:/Windows/Fonts/segoeui.ttf",
                                max(16, min(w, h) // 26))
                        except Exception:
                            f1 = f2 = ImageFont.load_default()
                        draw.text(
                            (int(w*.13), int(h*.37)),
                            title, fill=primary, font=f1)
                        draw.text(
                            (int(w*.13), int(h*.54)),
                            str(v["Subtitle"]),
                            fill="#253044", font=f2)
                        im.save(
                            path,
                            "JPEG" if fmt == "jpg"
                            else fmt.upper())
                    except ImportError:
                        path = path.with_suffix(".svg")
                        path.write_text(svg, encoding="utf-8")
                        messagebox.showinfo(
                            APP,
                            "Pillow not installed — ""SVG created instead.\n"
                            "pip install pillow")
                self._insert(f"\n[Artwork: {path.name}]\n")
                self.status.set("Artwork: " + path.name)
                win.destroy()
            except Exception as exc:
                messagebox.showerror(APP, str(exc), parent=win)

        ttk.Button(win, text="Create artwork",
                    command=make).grid(
            row=row, column=0, columnspan=2,
            padx=16, pady=(14, 20), sticky="ew")


    # ══════════════════════════════════════════════════════════════════════════
    #  CREATIONS TAB  (OneDrive-style file browser)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_creations(self, parent:tk.Frame):
        P = PALETTE
        CBG  = self._bg
        CSURF= self._surface
        CACC = P["accent"]
        CFG  = self._fg
        CMUT = P["muted"]

        # ── top search + filter bar ───────────────────────────────────────────
        top = tk.Frame(parent, bg=CBG)
        top.pack(fill="x", padx=16, pady=(14,6))

        tk.Label(top, text="🗂  My Creations", bg=CBG, fg=CFG,
                  font=("Segoe UI", 16, "bold")).pack(side="left")

        self._creations_search = tk.StringVar()
        self._creations_search.trace_add("write", lambda *_: self._creations_refresh())
        search_frame = tk.Frame(top, bg=CSURF,
                                highlightbackground=P["border"],
                                highlightthickness=1)
        search_frame.pack(side="right", padx=(0,0))
        tk.Label(search_frame, text="🔍", bg=CSURF, fg=CMUT,
                  font=("Segoe UI",11)).pack(side="left", padx=(8,2))
        tk.Entry(search_frame, textvariable=self._creations_search,
                  bg=CSURF, fg=CFG, relief="flat", bd=0,
                  font=("Segoe UI",10), width=26,
                  insertbackground=CACC).pack(side="left", padx=(0,8), pady=4)

        # ── filter chips ──────────────────────────────────────────────────────
        chips_row = tk.Frame(parent, bg=CBG)
        chips_row.pack(fill="x", padx=16, pady=(0,8))
        self._creations_filter = tk.StringVar(value="All")
        for label, val in [("All files","All"),("📄 Documents",".hds"),
                            ("🎬 Videos",".hvs"),("🎞 Animations",".has")]:
            rb = tk.Label(chips_row, text=label,
                           bg=CSURF, fg=CFG, font=("Segoe UI",9),
                           padx=12, pady=4, cursor="hand2",
                           relief="flat")
            rb.pack(side="left", padx=3)
            def _chip_click(e, v=val, w=rb, surf=CSURF, acc=CACC):
                self._creations_filter.set(v)
                for child in chips_row.winfo_children():
                    try: child.configure(bg=surf, fg=CFG)
                    except Exception: pass
                try: w.configure(bg=acc, fg="#FFFFFF")
                except Exception: pass
                self._creations_refresh()
            rb.bind("<Button-1>", _chip_click)

        # ── stats bar ─────────────────────────────────────────────────────────
        self._creations_stats = tk.StringVar(value="Scanning...")
        tk.Label(parent, textvariable=self._creations_stats,
                  bg=CBG, fg=CMUT, font=("Segoe UI",8)).pack(
            anchor="w", padx=16, pady=(0,4))

        # ── main grid area (scrollable) ───────────────────────────────────────
        grid_outer = tk.Frame(parent, bg=CBG)
        grid_outer.pack(fill="both", expand=True, padx=8)

        self._creations_canvas = tk.Canvas(grid_outer, bg=CBG,
                                             highlightthickness=0)
        c_scrollbar = ttk.Scrollbar(grid_outer, orient="vertical",
                                     command=self._creations_canvas.yview)
        self._creations_canvas.configure(yscrollcommand=c_scrollbar.set)
        c_scrollbar.pack(side="right", fill="y")
        self._creations_canvas.pack(side="left", fill="both", expand=True)

        self._creations_inner = tk.Frame(self._creations_canvas, bg=CBG)
        self._creations_inner_id = self._creations_canvas.create_window(
            (0,0), window=self._creations_inner, anchor="nw")
        self._creations_inner.bind("<Configure>",
            lambda e: self._creations_canvas.configure(
                scrollregion=self._creations_canvas.bbox("all")))
        self._creations_canvas.bind("<Configure>",
            lambda e: self._creations_canvas.itemconfig(
                self._creations_inner_id, width=e.width))
        # mousewheel
        self._creations_canvas.bind("<MouseWheel>",
            lambda e: self._creations_canvas.yview_scroll(
                int(-1*(e.delta/120)), "units"))

        self._creations_selected: set = set()
        self._creations_refresh()

    def _creations_scan(self) -> list:
        """Scan for Studio project files only — safe, fast, scoped.
        Only looks in our own data folder + Desktop (1 level).
        No .json (too broad — matches npm, VS Code configs, etc).
        Recently opened files appear first.
        """
        STUDIO_EXTS = {".hds", ".hvs", ".has"}  # NOT .json
        filt  = self._creations_filter.get()  if hasattr(self,"_creations_filter")  else "All"
        query = (self._creations_search.get() if hasattr(self,"_creations_search") else "").lower()

        # Safe shallow scan: only our own folder (deep) + Desktop (1 level)
        search_dirs = [DATA, DATA/"templates", Path.home()/"Desktop"]

        seen = set(); files = []
        for d in search_dirs:
            if not d.exists(): continue
            try:
                # rglob only for our own DATA dir; glob (1-level) for Desktop
                iterator = d.rglob("*") if (d == DATA or d == DATA/"templates") else d.glob("*")
                for p in iterator:
                    if not p.is_file(): continue
                    if p.suffix.lower() not in STUDIO_EXTS: continue
                    if p in seen: continue
                    if filt != "All" and p.suffix.lower() != filt: continue
                    if query and query not in p.name.lower(): continue
                    seen.add(p); files.append(p)
            except Exception:
                pass

        # Recently opened list — put matching ones first
        recents = self._creations_load_recents()
        recent_filtered = []
        for r in recents:
            p = Path(r)
            if not p.exists(): continue
            if p.suffix.lower() not in STUDIO_EXTS: continue
            if filt != "All" and p.suffix.lower() != filt: continue
            if query and query not in p.name.lower(): continue
            if p not in seen:
                seen.add(p); files.append(p)  # add recently opened even if not in scan dirs
            recent_filtered.append(p)

        rest = [f for f in files if f not in set(recent_filtered)]
        rest.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        return (recent_filtered + rest)[:120]

    def _creations_refresh(self, *_):
        if not hasattr(self, "_creations_inner"): return
        # clear
        for w in self._creations_inner.winfo_children(): w.destroy()
        self._creations_selected.clear()
        files = self._creations_scan()
        P = PALETTE
        CBG   = self._bg
        CSURF = self._surface
        CACC  = P["accent"]
        CFG   = self._fg
        CMUT  = P["muted"]

        if hasattr(self, "_creations_stats"):
            loc = str(DATA)
            self._creations_stats.set(
                f"{len(files)} project file{'s' if len(files)!=1 else ''}  •  "
                f"from: {loc}")

        if not files:
            empty_f = tk.Frame(self._creations_inner, bg=CBG)
            empty_f.pack(expand=True, pady=60)
            tk.Label(empty_f, text="📂", bg=CBG, fg=CMUT,
                      font=("Segoe UI",48)).pack()
            tk.Label(empty_f,
                      text="No project files found",
                      bg=CBG, fg=self._fg, font=("Segoe UI",14,"bold")).pack(pady=(8,4))
            tk.Label(empty_f,
                      text="Create a Document, Design, Animation or Video\nand save it to see it appear here.\n\nOr open an existing project file:",
                      bg=CBG, fg=CMUT, font=("Segoe UI",10),
                      justify="center").pack()
            ttk.Button(empty_f, text="📂  Open project file…",
                        command=self._open).pack(pady=12)
            return

        ICONS = {".hds":"📄",".hvs":"🎬",".has":"🎞",".json":"🎨"}
        COLORS = {".hds":"#3B82F6",".hvs":"#8B5CF6",".has":"#10B981",".json":"#F59E0B"}
        LABELS = {".hds":"Document",".hvs":"Video",".has":"Animation",".json":"Design"}

        COLS = 4
        for i, p in enumerate(files):
            ext = p.suffix.lower()
            icon  = ICONS.get(ext, "📁")
            color = COLORS.get(ext, CACC)
            label = LABELS.get(ext, ext[1:].upper())
            try:
                import datetime
                mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
                age = mtime.strftime("%b %d, %Y")
                size_kb = p.stat().st_size // 1024
                size_str = f"{size_kb} KB" if size_kb>0 else "<1 KB"
            except Exception:
                age = "Unknown"; size_str = ""

            # card frame
            card = tk.Frame(self._creations_inner, bg=CSURF,
                             relief="flat", bd=0, cursor="hand2",
                             highlightbackground=P["border"],
                             highlightthickness=1)
            row = i // COLS; col = i % COLS
            card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
            self._creations_inner.columnconfigure(col, weight=1)

            # color accent bar at top
            tk.Frame(card, bg=color, height=4).pack(fill="x")

            # icon
            tk.Label(card, text=icon, bg=CSURF, fg=color,
                      font=("Segoe UI",28)).pack(pady=(12,2))

            # file name
            name = p.stem[:22] + ("…" if len(p.stem)>22 else "")
            tk.Label(card, text=name, bg=CSURF, fg=CFG,
                      font=("Segoe UI",9,"bold"),
                      wraplength=130, justify="center").pack(padx=8)

            # type badge
            badge_row = tk.Frame(card, bg=CSURF); badge_row.pack(pady=3)
            tk.Label(badge_row, text=label, bg=color, fg="#FFF",
                      font=("Segoe UI",7,"bold"),
                      padx=6, pady=1).pack(side="left")

            # date + size
            rec_list = self._creations_load_recents()
            if str(p) in rec_list[:10]:
                tk.Label(card, text="🕑 Recent", bg="#1E3A5F", fg="#7EC8E3",
                          font=("Segoe UI",7,"bold")).pack(pady=1)
            tk.Label(card, text=age, bg=CSURF, fg=CMUT,
                      font=("Segoe UI",7)).pack()
            tk.Label(card, text=size_str, bg=CSURF, fg=CMUT,
                      font=("Segoe UI",7)).pack(pady=(0,8))

            # click actions
            path_ref = p
            card_ref = card  # explicit closure capture — not e.widget.master

            def _open_file(e, path=path_ref, c=card_ref):
                # deselect all cards visually
                for w in self._creations_inner.winfo_children():
                    try: w.configure(highlightbackground=P["border"], highlightthickness=1)
                    except Exception: pass
                try: c.configure(highlightbackground=CACC, highlightthickness=2)
                except Exception: pass
                self._creations_selected = {path}

            def _dbl_open(e, path=path_ref):
                ext = path.suffix.lower()
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    messagebox.showerror(APP, f"Cannot read file:\n{exc}"); return
                try:
                    if ext == ".hds":
                        self.doc = Document.load(raw)
                        self.path = path; self.current = 0
                        self.history.clear(); self.future.clear()
                        self._load_page(); self._snapshot()
                        self.dirty = False
                        self.status.set("Opened: " + path.name)
                        self._creations_record_open(path)
                        self._switch_dept("documents")
                    elif ext == ".hvs":
                        self._video_project = raw
                        self._video_sel_track = 0; self._video_sel_clip = None
                        self._video_refresh()
                        self._creations_record_open(path)
                        self._switch_dept("video")
                    elif ext == ".has":
                        self._anim_project = raw; self._anim_frame = 0
                        self._anim_layer = 1
                        self._anim_undo_stack.clear(); self._anim_redo_stack.clear()
                        self._anim_refresh_lists(); self._anim_redraw()
                        self._creations_record_open(path)
                        self._switch_dept("animation")
                    else:
                        messagebox.showinfo(APP, "Cannot open " + ext + " files by double-click.\nUse the Open button instead.")
                except Exception as exc:
                    messagebox.showerror(APP, f"Error opening {path.name}:\n{exc}")

            # bind all children — use explicit card_ref not e.widget.master
            for w in list(card.winfo_children()) + [card]:
                try:
                    w.bind("<Button-1>", _open_file)
                    w.bind("<Double-Button-1>", _dbl_open)
                    w.bind("<Enter>", lambda e, c=card_ref: c.configure(
                        highlightbackground=CACC, highlightthickness=2))
                    w.bind("<Leave>", lambda e, c=card_ref, sel=path_ref: c.configure(
                        highlightbackground=CACC if sel in self._creations_selected
                        else P["border"], highlightthickness=1))
                except Exception:
                    pass

    def _creations_open_folder(self):
        import subprocess
        try: subprocess.Popen(["explorer", str(DATA)], creationflags=0x08000000)
        except Exception: pass

    def _creations_delete(self):
        if not self._creations_selected:
            messagebox.showinfo(APP, "Click a file to select it first.")
            return
        for p in list(self._creations_selected):
            if messagebox.askyesno(APP, f"Delete {p.name}?"):
                try: p.unlink()
                except Exception as exc: messagebox.showerror(APP, str(exc))
        self._creations_refresh()

    def _creations_copy_path(self):
        if not self._creations_selected:
            messagebox.showinfo(APP, "Click a file first."); return
        p = next(iter(self._creations_selected))
        self.clipboard_clear(); self.clipboard_append(str(p))
        self.status.set(f"Path copied: {p.name}")

    def _creations_export(self):
        if not self._creations_selected:
            messagebox.showinfo(APP, "Click a file first."); return
        src = next(iter(self._creations_selected))
        dst = filedialog.asksaveasfilename(
            initialfile=src.name,
            defaultextension=src.suffix,
            filetypes=[("All files","*.*")])
        if dst:
            import shutil
            shutil.copy2(src, dst)
            self.status.set(f"Exported: {Path(dst).name}")

    # ══════════════════════════════════════════════════════════════════════════
    #  SPREADSHEET  extra methods
    # ══════════════════════════════════════════════════════════════════════════
    def _sheet_fill_color(self):
        c = colorchooser.askcolor(parent=self)[1]
        if c:
            row, col = self._sheet_sel
            key = self._sheet_key(row, col)
            self._sheet_data.setdefault(key, {})["bg"] = c
            if hasattr(self, "_sheet_fill_btn"):
                self._sheet_fill_btn.configure(bg=c)
            self._sheet_draw()

    def _sheet_toggle_border(self):
        row, col = self._sheet_sel
        key = self._sheet_key(row, col)
        cell = self._sheet_data.setdefault(key, {})
        cell["border"] = not cell.get("border", False)
        self._sheet_draw()
        self.status.set("Border " + ("on" if cell["border"] else "off") + f" for {key}")

    def _sheet_apply_format(self):
        if not hasattr(self, "_sheet_fmt_var"):
            return
        row, col = self._sheet_sel
        key = self._sheet_key(row, col)
        cell = self._sheet_data.setdefault(key, {})
        fmt = self._sheet_fmt_var.get()
        cell["format"] = fmt
        val = cell.get("value", "")
        try:
            num = float(val.replace("$", "").replace(",", "").replace("%", ""))
            if fmt == "Currency":
                cell["value"] = f"${num:,.2f}"
            elif fmt == "Percent":
                cell["value"] = f"{num:.1f}%"
            elif fmt == "Number":
                cell["value"] = f"{num:,.2f}"
            elif fmt == "Date":
                import datetime
                cell["value"] = datetime.date.today().strftime("%Y-%m-%d")
        except Exception:
            pass
        self._sheet_draw()
        self.status.set(f"{key} → {fmt}")

    def _sheet_freeze_toggle(self):
        row, col = self._sheet_sel
        if hasattr(self, "_sheet_frozen") and self._sheet_frozen == (row, col):
            self._sheet_frozen = None
            self.status.set("Freeze panes removed")
        else:
            self._sheet_frozen = (row, col)
            self.status.set(f"Frozen at row {row+1}, col {col+1}")
        self._sheet_draw()

    # ══════════════════════════════════════════════════════════════════════════
    #  SLIDES  extra methods
    # ══════════════════════════════════════════════════════════════════════════
    def _slide_pick_bg(self):
        """Color picker for the current slide background."""
        current_bg = self._slides[self._cur_slide].get("background", "#1E2D40")
        c = colorchooser.askcolor(current_bg, parent=self)[1]
        if c:
            if hasattr(self, "_slide_theme"):
                self._slide_theme.set(c)
            self._slides[self._cur_slide]["background"] = c
            self._slide_redraw()

    # ══════════════════════════════════════════════════════════════════════════
    #  VIDEO  extra methods
    # ══════════════════════════════════════════════════════════════════════════
    def _video_duplicate_track(self):
        tr = self._vid_track()
        if tr is None:
            return
        new_tr = copy.deepcopy(tr)
        new_tr["id"] = new_id()
        new_tr["name"] = tr["name"] + " copy"
        self._video_project["tracks"].append(new_tr)
        self._video_refresh()
        self.status.set(f"Duplicated track: {tr['name']}")

    def _video_add_track(self):
        name = simpledialog.askstring("New track", "Track name:", parent=self)
        if not name:
            return
        kind = simpledialog.askstring(
        "Track type", "Type (video / audio / title):",
            initialvalue="video", parent=self) or "video"
        self._video_project["tracks"].append({
        "id": new_id(), "kind": kind.lower().strip(), "name": name,
            "clips": [], "muted": False, "locked": False, "color": "#475569",
        })
        self._video_refresh()
        self.status.set(f"Added track: {name}")

    def _video_set_clip_label(self):
        tr = self._vid_track()
        if tr is None or self._video_sel_clip is None:
            return
        if self._video_sel_clip >= len(tr["clips"]):
            return
        label = self._vid_label_var.get() if hasattr(self, "_vid_label_var") else ""
        tr["clips"][self._video_sel_clip]["label"] = label
        self._video_refresh()
        self.status.set(f"Label set: {label!r}")

    # ══════════════════════════════════════════════════════════════════════════
    #  ANIMATION  extra methods
    # ══════════════════════════════════════════════════════════════════════════
    def _anim_fps_changed(self):
        if not hasattr(self, "_anim_fps_var"):
            return
        try:
            fps = int(self._anim_fps_var.get())
            fps = max(1, min(60, fps))
            self._anim_project["fps"] = fps
            self.status.set(f"FPS: {fps}")
        except Exception:
            pass

    def _anim_pick_bg(self):
        """Pick animation canvas background color."""
        c = colorchooser.askcolor(
            self._anim_project.get("background", "#FFFFFF"), parent=self)[1]
        if c:
            self._anim_project["background"] = c
            if hasattr(self, "_anim_bg_lbl"):
                self._anim_bg_lbl.configure(bg=c)
            self._anim_redraw()

    def _anim_canvas_size(self):
        """Resize the animation canvas."""
        w = simpledialog.askinteger(
        "Canvas width", "Width (px):",
            initialvalue=self._anim_project["width"],
            minvalue=64, maxvalue=4096, parent=self)
        if w is None:
            return
        h = simpledialog.askinteger(
        "Canvas height", "Height (px):",
            initialvalue=self._anim_project["height"],
            minvalue=64, maxvalue=4096, parent=self)
        if h is None:
            return
        self._anim_project["width"] = w
        self._anim_project["height"] = h
        self._anim_redraw()
        self.status.set(f"Canvas resized: {w}×{h}")

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 1 — F1 Keyboard shortcut cheat sheet
    # ══════════════════════════════════════════════════════════════════════════
    def _show_shortcuts(self):
        win = tk.Toplevel(self)
        win.title("Keyboard Shortcuts  —  F1")
        win.geometry("680x560")
        win.transient(self)
        win.configure(bg=self._bg)

        tk.Label(win, text="⌨  Keyboard Shortcuts", bg=self._bg, fg=self._fg,
                  font=("Segoe UI",15,"bold")).pack(anchor="w", padx=20, pady=(16,4))
        tk.Label(win, text="Press Escape or F1 to close", bg=self._bg,
                  fg=PALETTE["muted"], font=("Segoe UI",9)).pack(anchor="w", padx=20)

        outer = tk.Frame(win, bg=self._bg)
        outer.pack(fill="both", expand=True, padx=16, pady=12)

        SECTIONS = [
            ("📄 Documents", [
                ("Ctrl+S","Save"),("Ctrl+Z","Undo"),("Ctrl+Y","Redo"),
                ("Ctrl+B","Bold"),("Ctrl+I","Italic"),("Ctrl+U","Underline"),
                ("Ctrl+H","Find & Replace"),("Ctrl+A","Select all"),
                ("Ctrl+P","Print (opens browser)"),
            ]),
            ("🎞 Animation", [
                ("←/→","Previous / Next frame"),("Space","Play/Pause"),
                ("Ctrl+Z","Undo stroke"),("Ctrl+Y","Redo stroke"),
            ]),
            ("🌐 Global", [
                ("F1","This shortcut panel"),
                ("Alt+F4","Close application"),
            ]),
            ("📊 Spreadsheet", [
                ("Enter","Confirm cell, move right"),
                ("F2","Edit selected cell"),
                ("Ctrl+F","Find & Replace cells"),
            ]),
            ("🖼 Slides", [
                ("→ / Space","Next slide (presenter)"),
                ("←","Previous slide (presenter)"),
                ("Escape","Exit presenter view"),
            ]),
        ]

        col_frame = tk.Frame(outer, bg=self._bg)
        col_frame.pack(fill="both", expand=True)

        for ci, (section, items) in enumerate(SECTIONS):
            col = ci % 2
            if not hasattr(self, f"_sc_col{col}"):
                c = tk.Frame(col_frame, bg=self._bg)
                c.pack(side="left", fill="both", expand=True, padx=6)
                setattr(self, f"_sc_col{col}", c)
            parent_col = getattr(self, f"_sc_col{col}")

            sec_frame = tk.Frame(parent_col, bg=self._surface,
                                  highlightbackground=PALETTE["border"],
                                  highlightthickness=1)
            sec_frame.pack(fill="x", pady=6, ipady=4)

            tk.Label(sec_frame, text=section, bg=self._surface, fg=self._fg,
                      font=("Segoe UI",10,"bold")).pack(anchor="w", padx=10, pady=(6,2))

            for key, desc in items:
                row = tk.Frame(sec_frame, bg=self._surface)
                row.pack(fill="x", padx=8, pady=1)
                tk.Label(row, text=key, bg=PALETTE["accent"], fg="#FFF",
                          font=("Courier New",9,"bold"),
                          padx=6, pady=1).pack(side="left")
                tk.Label(row, text="  "+desc, bg=self._surface, fg=self._fg,
                          font=("Segoe UI",9)).pack(side="left")

        # clean up columns on close
        def _cleanup():
            for attr in ["_sc_col0","_sc_col1"]:
                if hasattr(self, attr): delattr(self, attr)
            win.destroy()

        win.bind("<Escape>", lambda e: _cleanup())
        win.bind("<F1>", lambda e: _cleanup())
        ttk.Button(win, text="Close  (Esc)", command=_cleanup).pack(pady=(0,16))

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 3 — Creations: track recently opened files
    # ══════════════════════════════════════════════════════════════════════════
    def _creations_record_open(self, path: Path):
        """Record a file as recently opened."""
        rf_file = DATA / "recent_files.json"
        try:
            recents = json.loads(rf_file.read_text(encoding="utf-8")) if rf_file.exists() else []
        except Exception:
            recents = []
        entry = str(path)
        recents = [e for e in recents if e != entry]
        recents.insert(0, entry)
        recents = recents[:50]
        rf_file.write_text(json.dumps(recents), encoding="utf-8")

    def _creations_load_recents(self) -> list:
        rf_file = DATA / "recent_files.json"
        try:
            return json.loads(rf_file.read_text(encoding="utf-8")) if rf_file.exists() else []
        except Exception:
            return []

    # ══════════════════════════════════════════════════════════════════════════
    #  TASKS 4-6 — Spreadsheet: multi-sheet, sort, find/replace, chart, auto-fill
    # ══════════════════════════════════════════════════════════════════════════
    def _sheet_find_replace(self):
        """Find & Replace dialog for spreadsheet cells."""
        win = tk.Toplevel(self)
        win.title("Spreadsheet Find & Replace")
        win.transient(self)
        win.resizable(False, False)
        win.configure(bg=self._bg)

        find_var  = tk.StringVar()
        repl_var  = tk.StringVar()
        case_var  = tk.BooleanVar(value=False)
        result_var= tk.StringVar(value="")

        for row, (lbl, var) in enumerate([("Find:", find_var), ("Replace:", repl_var)]):
            tk.Label(win, text=lbl, bg=self._bg, fg=self._fg,
                      font=("Segoe UI",10)).grid(row=row, column=0, padx=12, pady=6, sticky="w")
            ttk.Entry(win, textvariable=var, width=30).grid(
                row=row, column=1, padx=12, pady=6, columnspan=2)

        ttk.Checkbutton(win, text="Case sensitive", variable=case_var).grid(
            row=2, column=0, columnspan=3, padx=12, sticky="w")

        tk.Label(win, textvariable=result_var, bg=self._bg, fg=PALETTE["muted"],
                  font=("Segoe UI",9)).grid(row=3, column=0, columnspan=3, padx=12, sticky="w")

        def do_replace_all():
            find = find_var.get()
            repl = repl_var.get()
            if not find: return
            count = 0
            for key, cell in self._sheet_data.items():
                val = str(cell.get("value",""))
                if case_var.get():
                    if find in val:
                        cell["value"] = val.replace(find, repl)
                        count += 1
                else:
                    if find.lower() in val.lower():
                        import re as _re
                        cell["value"] = _re.sub(re.escape(find), repl, val,
                                                flags=re.IGNORECASE)
                        count += 1
            self._sheet_draw()
            result_var.set(f"Replaced {count} cell(s).")

        bf = tk.Frame(win, bg=self._bg)
        bf.grid(row=4, column=0, columnspan=3, padx=8, pady=10)
        ttk.Button(bf, text="Replace All", command=do_replace_all).pack(side="left", padx=4)
        ttk.Button(bf, text="Close", command=win.destroy).pack(side="left", padx=4)

    def _sheet_sort_column(self):
        """Sort the spreadsheet by the currently selected column."""
        _, col = self._sheet_sel
        direction = simpledialog.askstring(
        "Sort", "Sort direction: asc or desc",
            initialvalue="asc", parent=self)
        if direction is None: return
        asc = direction.strip().lower() != "desc"

        # collect all rows for this column
        row_vals = []
        for row in range(self._ROWS):
            key = self._sheet_key(row, col)
            val = self._sheet_data.get(key, {}).get("value", "")
            row_vals.append((row, val))

        def sort_key(x):
            try: return (0, float(x[1]))
            except Exception: return (1, str(x[1]).lower())

        row_vals.sort(key=sort_key, reverse=not asc)

        # rebuild all columns based on sorted row order
        new_data = {}
        for new_row, (old_row, _) in enumerate(row_vals):
            for c in range(self._COLS):
                old_key = self._sheet_key(old_row, c)
                new_key = self._sheet_key(new_row, c)
                if old_key in self._sheet_data:
                    new_data[new_key] = self._sheet_data[old_key]
        self._sheet_data.clear()
        self._sheet_data.update(new_data)
        self._sheet_draw()
        self.status.set(f"Sorted column {self._sheet_key(0,col)[:-1]} {'↑' if asc else '↓'}")

    def _sheet_add_sheet(self):
        """Add a new sheet tab."""
        if not hasattr(self, "_sheet_tabs"):
            self._sheet_tabs = [{"name":"Sheet 1","data":{}}]
            self._sheet_tab_idx = 0
        name = simpledialog.askstring(
        "New sheet", "Sheet name:",
            initialvalue=f"Sheet {len(self._sheet_tabs)+1}",
            parent=self)
        if not name: return
        # save current
        self._sheet_tabs[self._sheet_tab_idx]["data"] = dict(self._sheet_data)
        self._sheet_tabs.append({"name":name,"data":{}})
        self._sheet_tab_idx = len(self._sheet_tabs)-1
        self._sheet_data.clear()
        self._sheet_draw()
        self._sheet_refresh_tabs()
        self.status.set(f"New sheet: {name}")

    def _sheet_switch_tab(self, idx:int):
        if not hasattr(self,"_sheet_tabs"): return
        # save current
        self._sheet_tabs[self._sheet_tab_idx]["data"] = dict(self._sheet_data)
        self._sheet_tab_idx = idx
        self._sheet_data.clear()
        self._sheet_data.update(self._sheet_tabs[idx]["data"])
        self._sheet_draw()

    def _sheet_refresh_tabs(self):
        """Rebuild the sheet tab strip at the bottom of the spreadsheet."""
        if not hasattr(self,"_sheet_tab_frame"): return
        for w in self._sheet_tab_frame.winfo_children(): w.destroy()
        if not hasattr(self,"_sheet_tabs"):
            self._sheet_tabs=[{"name":"Sheet 1","data":{}}]
            self._sheet_tab_idx=0
        for i, tab in enumerate(self._sheet_tabs):
            is_active = (i == self._sheet_tab_idx)
            b = tk.Label(self._sheet_tab_frame,
                          text=f"  {tab['name']}  ",
                          bg=PALETTE["accent"] if is_active else self._surface,
                          fg="#FFFFFF" if is_active else self._fg,
                          font=("Segoe UI",9,"bold" if is_active else "normal"),
                          padx=4, pady=3, cursor="hand2",
                          relief="flat",
                          highlightbackground=PALETTE["border"],
                          highlightthickness=1)
            b.pack(side="left", padx=2, pady=2)
            b.bind("<Button-1>", lambda e, idx=i: self._sheet_switch_tab(idx))
        # + button
        add_b = tk.Label(self._sheet_tab_frame, text=" ＋ ",
                          bg=self._surface, fg=self._fg,
                          font=("Segoe UI",10), cursor="hand2", pady=3)
        add_b.pack(side="left", padx=2)
        add_b.bind("<Button-1>", lambda e: self._sheet_add_sheet())

    def _sheet_chart(self):
        """Render a chart from the selected range in a popup window."""
        # Ask for range
        range_str = simpledialog.askstring(
        "Chart range",
            "Enter cell range (e.g. A1:C5):",
            initialvalue="A1:B5", parent=self)
        if not range_str: return

        chart_type = simpledialog.askstring(
        "Chart type", "Type: bar / line / pie",
            initialvalue="bar", parent=self)
        if not chart_type: return
        chart_type = chart_type.strip().lower()

        # Parse range
        m = re.match(r"([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)", range_str.strip())
        if not m:
            messagebox.showerror("Chart", "Invalid range. Use format A1:C5")
            return

        def col_idx(s):
            s=s.upper(); r=0
            for ch in s: r=r*26+ord(ch)-64
            return r-1

        c1=col_idx(m.group(1)); r1=int(m.group(2))-1
        c2=col_idx(m.group(3)); r2=int(m.group(4))-1

        # Extract data — first column = labels, rest = series
        labels=[]
        series=[]
        for row in range(r1, r2+1):
            row_vals=[]
            for col in range(c1, c2+1):
                v=self._sheet_data.get(self._sheet_key(row,col),{}).get("value","")
                row_vals.append(v)
            if row_vals:
                labels.append(str(row_vals[0]))
                try: series.append([float(v) for v in row_vals[1:]])
                except Exception: series.append([0.0]*(len(row_vals)-1))

        if not series:
            messagebox.showinfo("Chart","No data found in range."); return

        # Draw chart in a Toplevel canvas
        win=tk.Toplevel(self)
        win.title(f"{chart_type.capitalize()} Chart — {range_str}")
        win.geometry("600x420")
        win.configure(bg=self._bg)

        c=tk.Canvas(win,bg="#1E293B",highlightthickness=0)
        c.pack(fill="both",expand=True,padx=10,pady=10)
        c.update()

        cw=c.winfo_width() or 580
        ch2=c.winfo_height() or 400
        PAD=50; colors=["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6","#06B6D4"]
        max_val=max((v for row in series for v in row),default=1) or 1

        if chart_type=="pie" and series:
            vals=[row[0] if row else 0 for row in series]
            total=sum(vals) or 1
            cx,cy,r=cw//2,ch2//2,min(cw,ch2)//2-40
            start=0
            for i,(lbl,val) in enumerate(zip(labels,vals)):
                extent=val/total*360
                c.create_arc(cx-r,cy-r,cx+r,cy+r,
                               start=start,extent=extent,
                               fill=colors[i%len(colors)],outline="#1E293B",width=2)
                mid_angle=math.radians(start+extent/2)
                lx=cx+int((r+20)*math.cos(mid_angle))
                ly=cy-int((r+20)*math.sin(mid_angle))
                c.create_text(lx,ly,text=f"{lbl}\n{val:.1f}",fill="white",
                               font=("Segoe UI",8),justify="center")
                start+=extent
        elif chart_type=="line":
            num=len(labels)
            if num<2: return
            step=(cw-PAD*2)/(num-1)
            num_series=len(series[0]) if series else 1
            for si in range(num_series):
                pts=[]
                for i,row in enumerate(series):
                    v=row[si] if si<len(row) else 0
                    x=PAD+i*step
                    y=ch2-PAD-int(v/max_val*(ch2-PAD*2))
                    pts.extend([x,y])
                if len(pts)>=4:
                    c.create_line(*pts,fill=colors[si%len(colors)],width=2,smooth=True)
                    for i in range(0,len(pts),2):
                        c.create_oval(pts[i]-4,pts[i+1]-4,pts[i]+4,pts[i+1]+4,
                                       fill=colors[si%len(colors)],outline="white")
            # x labels
            step2=(cw-PAD*2)/max(1,num-1)
            for i,lbl in enumerate(labels):
                c.create_text(PAD+i*step2,ch2-10,text=lbl,fill="#94A3B8",
                               font=("Segoe UI",8))
        else:  # bar
            num=len(labels)
            bar_w=max(8,(cw-PAD*2)//(num+1))
            num_series=len(series[0]) if series else 1
            for i,(lbl,row) in enumerate(zip(labels,series)):
                for si,v in enumerate(row):
                    x1=PAD+i*(bar_w*num_series+6)+si*bar_w
                    x2=x1+bar_w-2
                    bh=int(v/max_val*(ch2-PAD*2))
                    y1=ch2-PAD-bh; y2=ch2-PAD
                    c.create_rectangle(x1,y1,x2,y2,
                                        fill=colors[si%len(colors)],outline="")
                c.create_text(PAD+i*(bar_w*num_series+6)+bar_w//2,
                               ch2-8,text=lbl[:8],fill="#94A3B8",
                               font=("Segoe UI",7))
        # axes
        c.create_line(PAD,PAD,PAD,ch2-PAD,fill="#475569",width=1)
        c.create_line(PAD,ch2-PAD,cw-PAD,ch2-PAD,fill="#475569",width=1)
        c.create_text(cw//2,18,text=f"{chart_type.capitalize()} Chart  —  {range_str}",
                       fill="white",font=("Segoe UI",10,"bold"))

    def _sheet_auto_fill(self):
        """Auto-fill the selected column downward with a detected series."""
        row, col = self._sheet_sel
        # collect values above
        vals = []
        for r in range(max(0,row-5), row+1):
            v = self._sheet_data.get(self._sheet_key(r,col),{}).get("value","")
            if v: vals.append(v)
        if not vals:
            messagebox.showinfo("Auto-fill","No values above to extend."); return
        n = simpledialog.askinteger(
        "Auto-fill","How many cells to fill downward?",
            initialvalue=5,minvalue=1,maxvalue=100,parent=self)
        if not n: return

        # detect numeric series
        try:
            nums=[float(v) for v in vals]
            step=nums[-1]-nums[-2] if len(nums)>=2 else 1.0
            for i in range(1,n+1):
                key=self._sheet_key(row+i,col)
                nv=nums[-1]+step*i
                self._sheet_data.setdefault(key,{})["value"]=\
                    str(int(nv) if nv==int(nv) else round(nv,4))
        except Exception:
            # text series (repeat pattern)
            for i in range(1,n+1):
                key=self._sheet_key(row+i,col)
                self._sheet_data.setdefault(key,{})["value"]=vals[(i-1)%len(vals)]
        self._sheet_draw()
        self.status.set(f"Auto-filled {n} cells")

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 7 — Slides: theme gallery, image-on-slide, presenter view
    # ══════════════════════════════════════════════════════════════════════════
    SLIDE_THEMES = [
        ("Ocean Night",   "#0D2137","#00B4D8"),
        ("Sunset",        "#1A0A2E","#FF6B6B"),
        ("Forest",        "#0D1F0D","#4CAF50"),
        ("Classic Dark",  "#1E2D40","#3B82F6"),
        ("Slate",         "#1E293B","#94A3B8"),
        ("Crimson",       "#3B0000","#EF4444"),
        ("Gold",          "#1C1600","#F59E0B"),
        ("Violet",        "#1A0533","#8B5CF6"),
        ("Teal",          "#001A1A","#14B8A6"),
        ("Pure White",    "#FFFFFF","#1E293B"),
    ]

    def _slide_theme_gallery(self):
        """Show 10 preset slide themes as clickable swatches."""
        win=tk.Toplevel(self)
        win.title("Slide Theme Gallery")
        win.geometry("520x340")
        win.transient(self)
        win.configure(bg=self._bg)

        tk.Label(win,text="🎨  Slide Theme Gallery",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",13,"bold")).pack(anchor="w",padx=18,pady=(14,4))
        tk.Label(win,text="Click a theme to apply it to the current slide.",
                  bg=self._bg,fg=PALETTE["muted"],font=("Segoe UI",9)).pack(anchor="w",padx=18)

        grid=tk.Frame(win,bg=self._bg); grid.pack(padx=14,pady=10)
        for i,(name,bg_col,acc_col) in enumerate(self.SLIDE_THEMES):
            cell=tk.Frame(grid,bg=bg_col,width=88,height=56,cursor="hand2",
                           highlightbackground=acc_col,highlightthickness=2)
            cell.grid(row=i//5,column=i%5,padx=4,pady=4)
            cell.pack_propagate(False)
            # mini preview
            tk.Frame(cell,bg=acc_col,height=4).pack(fill="x")
            tk.Label(cell,text=name,bg=bg_col,fg="white",
                      font=("Segoe UI",7),wraplength=80).pack(expand=True)
            def _apply(bg=bg_col,acc=acc_col):
                self._slides[self._cur_slide]["background"]=bg
                self._slides[self._cur_slide]["accent"]=acc
                if hasattr(self,"_slide_theme"): self._slide_theme.set(bg)
                self._slide_redraw()
                win.destroy()
            cell.bind("<Button-1>",lambda e,fn=_apply:fn())
            for child in cell.winfo_children():
                child.bind("<Button-1>",lambda e,fn=_apply:fn())

    def _slide_add_image(self):
        """Add an image path to the current slide."""
        p=filedialog.askopenfilename(parent=self,
            filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        if not p: return
        self._slides[self._cur_slide]["image"]=p
        self._slide_redraw()
        self.status.set(f"Image added: {Path(p).name}")

    def _present_with_notes(self):
        """Presenter view: main window full-screen + notes in a second window."""
        self._store()
        slides=self._slides
        if not slides: return
        idx={"v":0}

        # ── full-screen presenter window ─────────────────────────────────────
        pwin=tk.Toplevel(self)
        pwin.title("Presenter View")
        pwin.configure(bg="black")
        pwin.attributes("-fullscreen",True)

        slide_canvas=tk.Canvas(pwin,bg="#1E2D40",highlightthickness=0)
        slide_canvas.pack(fill="both",expand=True)

        nav_bar=tk.Frame(pwin,bg="#111827",height=36)
        nav_bar.pack(fill="x")
        nav_bar.pack_propagate(False)
        counter_lbl=tk.Label(nav_bar,text="",bg="#111827",fg="#94A3B8",font=("Segoe UI",10))
        counter_lbl.pack(side="left",padx=14)
        tk.Label(nav_bar,text="← →  navigate  •  Space = autoplay  •  Esc = exit",
                  bg="#111827",fg="#475569",font=("Segoe UI",8)).pack(side="right",padx=14)

        # ── notes window ─────────────────────────────────────────────────────
        nwin=tk.Toplevel(self)
        nwin.title("Speaker Notes")
        nwin.geometry("420x300")
        nwin.configure(bg="#0F172A")
        tk.Label(nwin,text="🗒  Speaker Notes",bg="#0F172A",fg="#E2E8F0",
                  font=("Segoe UI",11,"bold")).pack(anchor="w",padx=12,pady=8)
        notes_lbl=tk.Label(nwin,text="",bg="#0F172A",fg="#CBD5E1",
                            font=("Segoe UI",11),wraplength=390,justify="left",anchor="nw")
        notes_lbl.pack(fill="both",expand=True,padx=12,pady=(0,12))
        next_lbl=tk.Label(nwin,text="",bg="#0F172A",fg="#475569",
                           font=("Segoe UI",9),wraplength=390)
        next_lbl.pack(anchor="w",padx=12,pady=(0,8))

        auto={"id":None}

        def show(d=0):
            idx["v"]=(idx["v"]+d)%len(slides)
            s=slides[idx["v"]]
            # draw slide
            cw=max(200,slide_canvas.winfo_width())
            ch=max(100,slide_canvas.winfo_height())
            slide_canvas.delete("all")
            bg=s.get("background","#1E2D40")
            acc=s.get("accent","#3B82F6")
            slide_canvas.create_rectangle(0,0,cw,ch,fill=bg,outline="")
            slide_canvas.create_rectangle(0,0,cw,8,fill=acc,outline="")
            lines=s["text"].splitlines()
            title=lines[0] if lines else ""
            body="".join(lines[1:]) if len(lines)>1 else ""
            slide_canvas.create_text(cw//2,int(ch*0.3),text=title,fill="white",
                                      font=("Segoe UI",max(20,cw//16),"bold"),
                                      width=int(cw*0.84),justify="center")
            if body.strip():
                slide_canvas.create_text(cw//2,int(ch*0.62),text=body,fill="#CBD5E1",
                                          font=("Segoe UI",max(12,cw//32)),
                                          width=int(cw*0.80),justify="center")
            counter_lbl.configure(text=f"  Slide {idx['v']+1} / {len(slides)}")
            # update notes panel
            notes_lbl.configure(text=s.get("notes","(no notes)"))
            nxt=slides[(idx["v"]+1)%len(slides)]
            next_lbl.configure(
                text="Next: "+nxt["text"].splitlines()[0][:50] if nxt else "")

        def autoplay(e=None):
            if auto["id"]:
                pwin.after_cancel(auto["id"]); auto["id"]=None
            else:
                ms=max(1,int(self.preferences.get("presentation_seconds",4)))*1000
                def tick():
                    show(1); auto["id"]=pwin.after(ms,tick)
                auto["id"]=pwin.after(ms,tick)

        def close_all(e=None):
            if auto["id"]: pwin.after_cancel(auto["id"])
            nwin.destroy(); pwin.destroy()

        pwin.bind("<Right>",  lambda e: show(1))
        pwin.bind("<Left>",   lambda e: show(-1))
        pwin.bind("<space>",  autoplay)
        pwin.bind("<Escape>", close_all)
        pwin.bind("<Configure>",lambda e: show(0))
        show()

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 8 — Design Canvas: undo/redo, snap-to-grid, text edit, templates
    # ══════════════════════════════════════════════════════════════════════════
    def _design_push_undo(self):
        import copy as _copy
        snap=_copy.deepcopy(self._dp())
        if not hasattr(self,"_design_undo"): self._design_undo=[]; self._design_redo=[]
        self._design_undo.append(snap)
        self._design_undo=self._design_undo[-60:]
        self._design_redo.clear()

    def _design_undo(self):
        if not hasattr(self,"_design_undo") or not self._design_undo:
            self.status.set("Nothing to undo"); return
        pg=self._dp()
        if not hasattr(self,"_design_redo"): self._design_redo=[]
        import copy as _copy
        self._design_redo.append(_copy.deepcopy(pg))
        snap=self._design_undo.pop()
        pg.objects=snap.objects; pg.background=snap.background
        self._sel_obj=None; self._dc_redraw()
        self.status.set("Design undone")

    def _design_redo_action(self):
        if not hasattr(self,"_design_redo") or not self._design_redo:
            self.status.set("Nothing to redo"); return
        pg=self._dp()
        if not hasattr(self,"_design_undo"): self._design_undo=[]
        import copy as _copy
        self._design_undo.append(_copy.deepcopy(pg))
        snap=self._design_redo.pop()
        pg.objects=snap.objects; pg.background=snap.background
        self._sel_obj=None; self._dc_redraw()
        self.status.set("Design redone")

    def _design_snap_toggle(self):
        self._design_snap=not getattr(self,"_design_snap",False)
        self.status.set("Snap to grid: "+("ON" if self._design_snap else "OFF"))

    def _design_edit_text_inplace(self, e):
        """Double-click on canvas: if a text object is hit, open inline editor."""
        obj=self._dc_hit(e.x,e.y)
        if obj is None or obj.kind!="text": return
        self._sel_obj=obj
        scale=getattr(self,"_dc_scale",1.0)
        ox=getattr(self,"_dc_ox",0); oy=getattr(self,"_dc_oy",0)
        x=ox+int(obj.x*scale); y=oy+int(obj.y*scale)
        w=max(120,int(obj.w*scale))
        e_var=tk.StringVar(value=obj.text)
        entry=tk.Entry(self.dcanvas,textvariable=e_var,
                        font=("Segoe UI",max(8,int(obj.font_sz*scale))),
                        bg="#FFFBEA",fg="#1E293B",relief="solid",bd=1,
                        width=max(12,w//8))
        entry.place(x=x,y=y)
        entry.focus_set()
        def _commit(ev=None):
            obj.text=e_var.get()
            entry.destroy(); self._dc_redraw()
        entry.bind("<Return>",_commit)
        entry.bind("<Escape>",lambda ev: entry.destroy())
        entry.bind("<FocusOut>",_commit)

    def _design_templates_gallery(self):
        """10 design canvas templates."""
        templates=[
            ("Social Post 1080×1080",1080,1080,"#1E2D40","#3B82F6","Your Title\nTagline here"),
            ("Story 1080×1920",1080,1920,"#0D2137","#00B4D8","Story\nSwipe up"),
            ("Banner 1200×628",1200,628,"#1A0A2E","#FF6B6B","Banner Headline\nSubheadline"),
            ("HD Slide 1920×1080",1920,1080,"#0F172A","#8B5CF6","Presentation\nSubtitle here"),
            ("A4 Portrait 794×1123",794,1123,"#FFFFFF","#315C8A","Document Title\nSubheader"),
            ("Poster 2480×3508",2480,3508,"#1C1600","#F59E0B","POSTER\nEvent details here"),
            ("YouTube Thumbnail",1280,720,"#111","#EF4444","Video Title\nClick bait text"),
            ("Twitter/X Header",1500,500,"#15202B","#1DA1F2","Profile Name\nBio tagline"),
            ("Business Card",1050,600,"#1E293B","#10B981","Full Name\nTitle  •  Email"),
            ("Certificate",2480,1754,"#FFFFF0","#B8860B","Certificate\nof Achievement"),
        ]
        win=tk.Toplevel(self)
        win.title("Design Templates")
        win.geometry("580x420")
        win.transient(self)
        win.configure(bg=self._bg)
        tk.Label(win,text="Design Canvas Templates",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",13,"bold")).pack(anchor="w",padx=18,pady=(14,4))

        lb=tk.Listbox(win,bg=self._surface,fg=self._fg,
                       selectbackground=PALETTE["accent"],selectforeground="#FFF",
                       font=("Segoe UI",10),relief="flat",bd=0,height=12)
        lb.pack(fill="both",expand=True,padx=14,pady=6)
        for t in templates:
            lb.insert("end",f"  {t[0]}  ({t[1]}×{t[2]})")

        def use():
            s=lb.curselection()
            if not s: return
            _,w,h,bg,acc,txt=templates[s[0]]
            self.design_proj.width=w; self.design_proj.height=h
            pg=self._dp()
            if pg:
                pg.background=bg; pg.objects.clear()
                # accent bar
                from c_editor import DesignObject
                pg.objects.append(DesignObject(kind="rect",x=0,y=0,w=w,h=max(8,h//30),
                                               fill=acc,stroke=""))
                # text
                lines=txt.split("\n")
                pg.objects.append(DesignObject(kind="text",x=w*0.1,y=h*0.35,
                                               w=w*0.8,h=h*0.15,fill="",
                                               text=lines[0],text_color="#FFFFFF",
                                               font_sz=max(24,w//20),font_bold=True))
                if len(lines)>1:
                    pg.objects.append(DesignObject(kind="text",x=w*0.1,y=h*0.55,
                                                   w=w*0.8,h=h*0.1,fill="",
                                                   text=lines[1],text_color="#CBD5E1",
                                                   font_sz=max(14,w//40)))
            self._dc_redraw()
            win.destroy()
            self.status.set(f"Template applied: {templates[s[0]][0]}")

        ttk.Button(win,text="Use template",command=use).pack(pady=(0,16),padx=14,fill="x")

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 9 — Animation: tweening, symbol library, audio waveform
    # ══════════════════════════════════════════════════════════════════════════
    def _anim_tween(self):
        """Auto-generate in-between frames between current frame and a target."""
        total=self._anim_project["total_frames"]
        target=simpledialog.askinteger(
        "Tween to frame","Target frame number (1-based):",
            initialvalue=min(self._anim_frame+5,total),
            minvalue=1,maxvalue=total,parent=self)
        if target is None: return
        target-=1  # 0-based
        if target==self._anim_frame:
            messagebox.showinfo(APP,"Choose a different frame."); return

        start=min(self._anim_frame,target)
        end=max(self._anim_frame,target)
        steps=end-start

        # get start and end ops for each layer
        for layer in self._anim_project["layers"]:
            start_ops=layer["frames"].get(str(start),[])
            end_ops=layer["frames"].get(str(end),[])
            if not start_ops and not end_ops: continue
            # simple opacity-blend tween: fade from start to end
            for step in range(1,steps):
                t=step/steps
                if start_ops:
                    import copy as _c
                    tweened=_c.deepcopy(start_ops)
                    for op in tweened:
                        op["opacity"]=round(1.0-t*0.4,2)
                    layer["frames"].setdefault(str(start+step),tweened)
        self._anim_redraw()
        self.status.set(f"Tweened {steps} frames between {start+1} and {end+1}")

    def _anim_symbol_save(self):
        """Save current frame's drawing as a reusable symbol."""
        name=simpledialog.askstring("Save symbol","Symbol name:",parent=self)
        if not name: return
        layer=self._anim_layer_obj()
        if not layer: return
        ops=layer["frames"].get(str(self._anim_frame),[])
        if not ops:
            messagebox.showinfo(APP,"Current frame is empty."); return
        sym_file=DATA/"symbols.json"
        try:
            syms=json.loads(sym_file.read_text(encoding="utf-8")) if sym_file.exists() else {}
        except Exception: syms={}
        syms[name]=ops
        sym_file.write_text(json.dumps(syms,ensure_ascii=False),encoding="utf-8")
        self.status.set(f"Symbol saved: {name}")

    def _anim_symbol_insert(self):
        """Insert a saved symbol into the current frame."""
        sym_file=DATA/"symbols.json"
        try:
            syms=json.loads(sym_file.read_text(encoding="utf-8")) if sym_file.exists() else {}
        except Exception: syms={}
        if not syms:
            messagebox.showinfo(APP,"No symbols saved yet.\nDraw something and use 'Save Symbol'."); return
        win=tk.Toplevel(self); win.title("Symbol Library")
        win.transient(self); win.configure(bg=self._bg)
        tk.Label(win,text="🔷 Symbol Library",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",12,"bold")).pack(padx=14,pady=(12,4),anchor="w")
        lb=tk.Listbox(win,bg=self._surface,fg=self._fg,
                       selectbackground=PALETTE["accent"],selectforeground="#FFF",
                       font=("Segoe UI",10),relief="flat",bd=0,height=10)
        lb.pack(fill="both",expand=True,padx=10,pady=6)
        for n in syms: lb.insert("end",f"  {n}")
        def use():
            s=lb.curselection()
            if not s: return
            name=list(syms.keys())[s[0]]
            import copy as _c
            ops=_c.deepcopy(syms[name])
            self._anim_get_ops().extend(ops)
            self._anim_redraw(); win.destroy()
            self.status.set(f"Symbol inserted: {name}")
        ttk.Button(win,text="Insert",command=use).pack(pady=(0,12),padx=10,fill="x")

    def _anim_audio_waveform(self):
        """Load an audio file and show a waveform preview under the scrubber."""
        p=filedialog.askopenfilename(parent=self,
            filetypes=[("Audio","*.mp3 *.wav *.ogg *.m4a *.aac")])
        if not p: return
        # Draw a fake waveform on a canvas below the scrubber
        # (real decoding requires soundfile/librosa — simulate visually)
        if hasattr(self,"_anim_waveform_win") and self._anim_waveform_win.winfo_exists():
            self._anim_waveform_win.destroy()
        wwin=tk.Toplevel(self); wwin.title("Audio Waveform — "+Path(p).name)
        wwin.geometry("700x120"); wwin.configure(bg="#111827")
        self._anim_waveform_win=wwin
        c=tk.Canvas(wwin,bg="#111827",highlightthickness=0)
        c.pack(fill="both",expand=True)
        c.update()
        import random,math as _m
        cw=c.winfo_width() or 680; ch=c.winfo_height() or 100
        random.seed(hash(p))
        mid=ch//2
        for x in range(0,cw,2):
            amp=random.randint(4,mid-4)*abs(_m.sin(x/40))
            c.create_line(x,mid-amp,x,mid+amp,fill="#3B82F6",width=1)
        c.create_text(cw//2,10,text=Path(p).name,fill="#94A3B8",font=("Segoe UI",8))
        self.status.set(f"Waveform: {Path(p).name}")

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 10 — Video: enhanced timeline (trim handles, waveform hint)
    # ══════════════════════════════════════════════════════════════════════════
    def _video_draw_timeline_enhanced(self):
        """Override: draw clip thumbnails and trim handles on timeline."""
        if not hasattr(self,'_tl_canvas'): return
        c=self._tl_canvas; c.delete("all")
        W=max(800,c.winfo_width())
        tracks=self._video_project["tracks"]
        ROW_H=52; LABEL_W=96; RULER_H=24
        P=PALETTE

        # ruler
        c.create_rectangle(0,0,W,RULER_H,fill="#111827",outline="")
        for sec in range(0,600,5):
            rx=LABEL_W+sec*22
            c.create_line(rx,0,rx,RULER_H,fill="#374151",width=1)
            c.create_text(rx+3,6,text=f"{sec}s",anchor="nw",
                           fill="#9CA3AF",font=("Segoe UI",7))

        total_h=RULER_H+ROW_H*len(tracks)+10
        for ri,track in enumerate(tracks):
            y0=RULER_H+ri*ROW_H; y1=y0+ROW_H-2
            row_bg="#1E2A3A" if ri%2==0 else "#182031"
            c.create_rectangle(0,y0,W,y1,fill=row_bg,outline="")
            c.create_rectangle(0,y0,LABEL_W,y1,fill="#111827",outline="")

            # mute indicator
            mute_icon="🔇" if track.get("muted") else ""
            c.create_text(6,y0+ROW_H//2,
                           text=f"{mute_icon} {track['name'][:10]}",
                           anchor="w",fill="#CBD5E1",font=("Segoe UI",8,"bold"))

            tc=track.get("color","#315C8A")
            kind=track.get("kind","video")

            for ci,clip in enumerate(track["clips"]):
                try:
                    cstart=float(clip.get("offset",ci*5) or 0)
                    end_raw=clip.get("end","") or "5"
                    start_raw=clip.get("start",0) or 0
                    cdur=max(1,float(end_raw)-float(start_raw))
                except (ValueError,TypeError,KeyError):
                    cstart,cdur=float(ci*5),5.0
                cx0=LABEL_W+int(cstart*22)
                cx1=cx0+max(24,int(cdur*22))
                is_sel=(ri==self._video_sel_track and ci==self._video_sel_clip)

                # clip body
                fill_col="#F59E0B" if is_sel else tc
                c.create_rectangle(cx0+1,y0+4,cx1-1,y1-4,
                                    fill=fill_col,outline="white" if is_sel else "",
                                    width=2 if is_sel else 0)

                # audio waveform simulation for audio tracks
                if kind=="audio":
                    import math as _m
                    for x in range(cx0+2,min(cx1-2,cx0+200),3):
                        amp=int((_m.sin((x-cx0)/6)*0.4+0.5)*(ROW_H//2-6))
                        mid_y=(y0+y1)//2
                        c.create_line(x,mid_y-amp,x,mid_y+amp,
                                       fill="#86EFAC",width=1)

                # clip name
                name=Path(clip.get("path","untitled")).stem[:18]
                if clip.get("label"): name=f"[{clip['label'][:12]}]"
                c.create_text(cx0+6,(y0+y1)//2,text=name,
                               anchor="w",fill="white",font=("Segoe UI",7))

                # trim handle left
                c.create_rectangle(cx0+1,y0+4,cx0+8,y1-4,
                                    fill="#1E293B",outline="white",width=1)
                # trim handle right
                c.create_rectangle(cx1-8,y0+4,cx1-1,y1-4,
                                    fill="#1E293B",outline="white",width=1)

        # markers
        for m in self._video_project.get("markers",[]):
            mx=LABEL_W+int(m["time"]*22)
            c.create_line(mx,0,mx,total_h,fill="#F59E0B",dash=(4,2),width=2)
            c.create_text(mx+2,RULER_H+2,text=m.get("label",""),
                           anchor="nw",fill="#FCD34D",font=("Segoe UI",7))

        c.configure(scrollregion=(0,0,max(W,LABEL_W+600*22),total_h+10))

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 11 — AI Writing Assistant
    # ══════════════════════════════════════════════════════════════════════════
    def _ai_assistant(self):
        """AI writing assistant panel using a free OpenAI-compatible endpoint."""
        win=tk.Toplevel(self)
        win.title("✨ AI Writing Assistant")
        win.geometry("560x600")
        win.transient(self)
        win.configure(bg=self._bg)

        tk.Label(win,text="✨  AI Writing Assistant",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",14,"bold")).pack(anchor="w",padx=18,pady=(16,2))
        tk.Label(win,
                  text="Uses a free AI endpoint. Select text first, then choose an action.",
                  bg=self._bg,fg=PALETTE["muted"],font=("Segoe UI",9),
                  wraplength=520).pack(anchor="w",padx=18,pady=(0,8))

        # quick action buttons
        actions_frame=tk.Frame(win,bg=self._bg); actions_frame.pack(fill="x",padx=14,pady=4)
        for action in ["Make formal","Make casual","Summarize","Expand",
                        "Fix grammar","Translate to Arabic","Continue writing","Make bullet points"]:
            b=tk.Label(actions_frame,text=action,bg=self._surface,fg=self._fg,
                        font=("Segoe UI",9),padx=10,pady=4,cursor="hand2",
                        relief="flat",
                        highlightbackground=PALETTE["border"],highlightthickness=1)
            b.pack(side="left",padx=2,pady=2)
            b.bind("<Enter>",lambda e,w=b:w.configure(bg=PALETTE["accent"],fg="#FFF"))
            b.bind("<Leave>",lambda e,w=b,ob=self._surface:w.configure(bg=ob,fg=self._fg))
            b.bind("<Button-1>",lambda e,a=action:prompt_var.set(a+": "+prompt_var.get()))

        tk.Label(win,text="Your instruction:",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",9,"bold")).pack(anchor="w",padx=18,pady=(8,2))
        prompt_var=tk.StringVar()
        ttk.Entry(win,textvariable=prompt_var,font=("Segoe UI",10)).pack(
            fill="x",padx=14,pady=(0,6))

        tk.Label(win,text="AI endpoint URL (OpenAI-compatible):",
                  bg=self._bg,fg=self._fg,font=("Segoe UI",9)).pack(anchor="w",padx=18)
        endpoint_var=tk.StringVar(value="https://api.openai.com/v1/chat/completions")
        ttk.Entry(win,textvariable=endpoint_var,font=("Segoe UI",9)).pack(
            fill="x",padx=14,pady=(0,2))

        tk.Label(win,text="API Key (optional for free endpoints):",
                  bg=self._bg,fg=self._fg,font=("Segoe UI",9)).pack(anchor="w",padx=18)
        key_var=tk.StringVar()
        ttk.Entry(win,textvariable=key_var,show="•",font=("Segoe UI",9)).pack(
            fill="x",padx=14,pady=(0,6))

        tk.Label(win,text="Result:",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",9,"bold")).pack(anchor="w",padx=18)
        result_box=tk.Text(win,height=10,wrap="word",font=("Segoe UI",10),
                            bg=self._surface,fg=self._fg,relief="flat",bd=1,
                            insertbackground=PALETTE["accent"])
        result_box.pack(fill="both",expand=True,padx=14,pady=(0,4))

        status_lbl=tk.Label(win,text="",bg=self._bg,fg=PALETTE["muted"],
                              font=("Segoe UI",8))
        status_lbl.pack(anchor="w",padx=18)

        def run_ai():
            prompt=prompt_var.get().strip()
            if not prompt:
                status_lbl.configure(text="Enter an instruction first.")
                return
            try: sel_text=self.editor.get("sel.first","sel.last")
            except tk.TclError: sel_text=self.editor.get("1.0","end-1c")[:2000]

            full_prompt=f"{prompt}\n\nText:\n{sel_text[:3000]}"
            status_lbl.configure(text="Sending request…")
            win.update_idletasks()

            def worker():
                try:
                    import urllib.request,json as _json
                    payload=_json.dumps({
                    "model":"gpt-3.5-turbo",
                        "messages":[
                            {"role":"system","content":"You are a helpful writing assistant."},
                            {"role":"user","content":full_prompt}
                        ],
                        "max_tokens":800,"temperature":0.7
                    }).encode("utf-8")
                    headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"}
                    if key_var.get().strip():
                        headers["Authorization"]="Bearer "+key_var.get().strip()
                    req=urllib.request.Request(
                        endpoint_var.get().strip(),data=payload,headers=headers)
                    with urllib.request.urlopen(req,timeout=30) as r:
                        data=_json.loads(r.read().decode("utf-8"))
                    reply=data["choices"][0]["message"]["content"]
                    def _show_reply(r=reply):
                        try:
                            result_box.delete("1.0","end")
                            result_box.insert("1.0",r)
                            status_lbl.configure(text="✓ Done",foreground="#16A34A")
                        except Exception: pass
                    try:
                        if win.winfo_exists(): win.after(0,_show_reply)
                    except Exception: pass
                except Exception as exc:
                    msg=str(exc)[:160]
                    def _show_err(m=msg):
                        try: status_lbl.configure(text="⚠ "+m,foreground="#DC2626")
                        except Exception: pass
                    try:
                        if win.winfo_exists(): win.after(0,_show_err)
                    except Exception: pass

            import threading
            threading.Thread(target=worker,daemon=True).start()

        def apply_result():
            text=result_box.get("1.0","end-1c").strip()
            if not text: return
            try:
                self.editor.delete("sel.first","sel.last")
                self.editor.insert("insert",text)
            except tk.TclError:
                self._insert("\n\n[AI Result]\n"+text+"\n")
            self._store(); self._dirt(); self._snapshot()
            win.destroy()

        bf=tk.Frame(win,bg=self._bg); bf.pack(fill="x",padx=14,pady=(4,16))
        for txt,cmd,style in [("✨ Run AI",run_ai,"accent"),
                                ("✔ Apply to doc",apply_result,"normal"),
                                ("✕ Close",win.destroy,"normal")]:
            bg=PALETTE["accent"] if style=="accent" else self._surface
            fg="#FFF" if style=="accent" else self._fg
            b=tk.Label(bf,text=txt,bg=bg,fg=fg,font=("Segoe UI",9),
                        padx=12,pady=5,cursor="hand2")
            b.pack(side="left",padx=3)
            b.bind("<Button-1>",lambda e,c=cmd:c())

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 12 — Export to ZIP + Cloud sync stub
    # ══════════════════════════════════════════════════════════════════════════
    def _export_zip(self):
        """Export current project + all referenced media into a ZIP file."""
        import zipfile as _zf
        self._store()
        safe=re.sub(r"[^\w -]","",self.doc.title) or "project"
        p=filedialog.asksaveasfilename(
            parent=self,defaultextension=".zip",
            initialfile=safe+".zip",
            filetypes=[("ZIP archive","*.zip")])
        if not p: return
        try:
            with _zf.ZipFile(p,"w",_zf.ZIP_DEFLATED) as zf:
                # project JSON
                proj_json=json.dumps(self.doc.payload(),ensure_ascii=False,indent=2)
                zf.writestr(safe+".hds",proj_json)
                # collect all media referenced in pages
                for page in self.doc.pages:
                    for el in page.elements:
                        mp=Path(el.get("path",""))
                        if mp.exists():
                            zf.write(mp,"media/"+mp.name)
                # assets folder
                for asset in (DATA/"assets").glob("*"):
                    if asset.is_file():
                        zf.write(asset,"assets/"+asset.name)
                # readme
                zf.writestr("README.txt",
                    f"Project: {self.doc.title}\n"
                    f"Exported by C EDITOR\n"
                    f"Open .hds file with the Studio app.\n")
            self.status.set(f"ZIP exported: {Path(p).name}")
            messagebox.showinfo(APP,f"Project packed into:\n{p}")
        except Exception as exc:
            messagebox.showerror(APP,str(exc))

    def _cloud_sync_stub(self):
        """Cloud sync guide — shows instructions for Google Drive/OneDrive."""
        win=tk.Toplevel(self); win.title("☁ Cloud Sync")
        win.geometry("500x420"); win.transient(self)
        win.configure(bg=self._bg)
        tk.Label(win,text="☁  Cloud Sync",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",14,"bold")).pack(anchor="w",padx=18,pady=(16,4))

        msg=(
        "Your project files are saved in:\n"
            f"  {DATA}\n""To sync with cloud storage:\n"
            "Google Drive\n"
            "  1. Install Google Drive desktop app\n"
            "  2. Move your .hds files to your Drive folder\n""  3. They sync automatically\n"
            "OneDrive\n"
            "  1. Your Desktop & Documents may already be synced\n""  2. Move projects to OneDrive folder\n"
            "Dropbox\n"
            "  1. Install Dropbox desktop app\n""  2. Move files to Dropbox folder\n"
            "Or use Export → ZIP to create a portable archive\n""you can upload anywhere manually."
        )
        txt=tk.Text(win,wrap="word",font=("Segoe UI",10),bg=self._surface,
                     fg=self._fg,relief="flat",bd=0,height=16)
        txt.pack(fill="both",expand=True,padx=14,pady=8)
        txt.insert("1.0",msg); txt.configure(state="disabled")

        bf=tk.Frame(win,bg=self._bg); bf.pack(fill="x",padx=14,pady=(0,16))
        ttk.Button(bf,text="📂 Open project folder",
                    command=lambda:os.startfile(str(DATA))).pack(side="left",padx=4)
        ttk.Button(bf,text="📦 Export ZIP",
                    command=self._export_zip).pack(side="left",padx=4)
        ttk.Button(bf,text="Close",command=win.destroy).pack(side="left",padx=4)

    # ══════════════════════════════════════════════════════════════════════════
    #  TASK 13 — Plugin system
    # ══════════════════════════════════════════════════════════════════════════
    def _load_plugins(self):
        """Load Python scripts from DATA/scripts/ as menu items."""
        scripts_dir=DATA/"scripts"
        scripts_dir.mkdir(exist_ok=True)
        plugins=[]
        for script in sorted(scripts_dir.glob("*.py")):
            try:
                import importlib.util as _ilu
                spec=_ilu.spec_from_file_location(script.stem,script)
                mod=_ilu.module_from_spec(spec)
                spec.loader.exec_module(mod)
                name=getattr(mod,"PLUGIN_NAME",script.stem.replace("_"," ").title())
                fn=getattr(mod,"run",None)
                if fn:
                    plugins.append((name,fn,script))
            except Exception as exc:
                plugins.append((f"[Error] {script.name}",None,script))
        return plugins

    def _plugins_menu(self):
        """Open plugin manager and run plugins."""
        plugins=self._load_plugins()
        scripts_dir=DATA/"scripts"
        win=tk.Toplevel(self); win.title("🧩 Plugins")
        win.geometry("500x440"); win.transient(self)
        win.configure(bg=self._bg)

        tk.Label(win,text="🧩  Plugin Manager",bg=self._bg,fg=self._fg,
                  font=("Segoe UI",14,"bold")).pack(anchor="w",padx=18,pady=(16,2))
        tk.Label(win,
                  text=f"Scripts folder: {scripts_dir}\n"
"Drop .py files there and click Reload.",
                  bg=self._bg,fg=PALETTE["muted"],font=("Segoe UI",9),
                  wraplength=460).pack(anchor="w",padx=18,pady=(0,8))

        lb=tk.Listbox(win,bg=self._surface,fg=self._fg,
                       selectbackground=PALETTE["accent"],selectforeground="#FFF",
                       font=("Segoe UI",10),relief="flat",bd=0,height=10)
        lb.pack(fill="both",expand=True,padx=14,pady=4)
        if plugins:
            for name,fn,path in plugins:
                lb.insert("end",f"  {'✓' if fn else '✗'}  {name}  ({path.name})")
        else:
            lb.insert("end","  No plugins found. Add .py scripts to the scripts folder.")

        out_var=tk.StringVar(value="")
        tk.Label(win,textvariable=out_var,bg=self._bg,fg=PALETTE["muted"],
                  font=("Segoe UI",8),wraplength=460).pack(anchor="w",padx=18)

        def run_selected():
            s=lb.curselection()
            if not s or not plugins: return
            name,fn,path=plugins[s[0]]
            if fn is None:
                out_var.set(f"Plugin '{name}' has errors."); return
            try:
                result=fn(app=self)
                out_var.set(f"✓ {name}: {str(result)[:80] if result else 'ran OK'}")
            except Exception as exc:
                out_var.set(f"✗ Error: {exc}")

        def open_folder():
            os.startfile(str(scripts_dir))

        def create_example():
            ex=scripts_dir/"example_plugin.py"
            ex.write_text(
                '"""Example plugin for C EDITOR.\n\nPLUGIN_NAME = "Example Plugin"\n"""\n\nPLUGIN_NAME = "Example Plugin"\n\ndef run(app=None):\n"""Called when user clicks Run in the plugin manager."""\nif app:\napp.status.set("Hello from plugin!")\nreturn "Plugin ran successfully"\n',
                encoding="utf-8")
            out_var.set(f"Created: {ex}")
            win.destroy(); self._plugins_menu()

        bf=tk.Frame(win,bg=self._bg); bf.pack(fill="x",padx=14,pady=(4,16))
        for txt,cmd in [("▶ Run",run_selected),("📂 Open folder",open_folder),
                          ("+ Example",create_example),("↺ Reload",lambda:(win.destroy(),self._plugins_menu())),
                          ("Close",win.destroy)]:
            b=tk.Label(bf,text=txt,bg=self._surface,fg=self._fg,
                        font=("Segoe UI",9),padx=10,pady=4,cursor="hand2")
            b.pack(side="left",padx=2)
            b.bind("<Button-1>",lambda e,c=cmd:c())


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    Studio().mainloop()
