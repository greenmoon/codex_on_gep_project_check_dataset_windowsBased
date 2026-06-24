# -*- coding: utf-8 -*-
"""
jb_A1886_GUItool_check_GEP_dataset_v07.py

Purpose
-------
GUI tool for checking GEP dataset log files in ./jb_GEP_dataset.
- Browse/select one dataset log file.
- Parse lines like: {"fn":1334,"r0":0.625695,"r1":1.069059,"r2":2.660874}
- Plot r0 raw and r0_deglitch vs fn with fixed y-axis range 0..2 m.
- Show bottom x-axis as fn and top x-axis as elapsed time in minutes.
- Window controls:
    1) window size N, default 200 frames
    2) start fn, default first fn in selected file, adjustable by slider/spinbox
    3) slidered deglitch controls for median_win, spike_th_m, jump_th_m
- NEW in v04:
    4) click a curve point to show info box: fn, t (hh:mm:ss), r0
    5) mouse wheel zoom in/out around the clicked point (or current window center)
    6) zoom updates window size and start fn in real time
- NEW in v05:
    7) frame tick default = 50 ms/frame
    8) window size default = full dot count after loading selected file
- NEW in v06:
    9) default spike_TH = 0.130 m
    10) default jump_TH = 0.253 m
- NEW in v07:
    11) add LOG / CSV format selector buttons
    12) LOG parser reads JSON-per-line logs
    13) CSV parser reads columns such as fn, r0_raw/r0, r1, r2

Author: Joybien / ChatGPT
Version: v07
"""

import os
import sys
import json
import csv
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

try:
    from PyQt5 import QtCore, QtWidgets
except ImportError:
    print("[ERROR] PyQt5 not installed. Install by: pip install PyQt5 matplotlib")
    raise

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


JB_STR = "jb_A1886_GUItool_check_GEP_dataset_v07.py"
DEFAULT_DATASET_DIR = "./jb_GEP_dataset"
DEFAULT_WINDOW_SIZE = 200
DEFAULT_FRAME_INTERVAL_MS = 50.0  # change if your real GEP frame tick is different

# Deglitch parameters for r0 -> r0_deglitch
DEFAULT_DEGLITCH_MEDIAN_WIN = 5
DEFAULT_DEGLITCH_SPIKE_TH_M = 0.130
DEFAULT_DEGLITCH_JUMP_TH_M = 0.253

# Slider ranges suitable for this GEP r0 0..2 m case
DEGLITCH_MEDIAN_WIN_MIN = 3
DEGLITCH_MEDIAN_WIN_MAX = 31
DEGLITCH_SPIKE_TH_MIN_M = 0.01
DEGLITCH_SPIKE_TH_MAX_M = 1.00
DEGLITCH_SPIKE_SLIDER_SCALE = 1000
DEGLITCH_JUMP_TH_MIN_M = 0.01
DEGLITCH_JUMP_TH_MAX_M = 1.50
DEGLITCH_JUMP_SLIDER_SCALE = 1000

# Interactive zoom parameters
ZOOM_IN_FACTOR = 0.8   # forward wheel -> smaller window
ZOOM_OUT_FACTOR = 1.25 # backward wheel -> larger window
CLICK_PICK_PIXELS = 12.0


@dataclass
class GEPRecord:
    fn: int
    r0: float
    r1: Optional[float] = None
    r2: Optional[float] = None


class GEPDatasetParser:
    """Parse GEP dataset files in LOG or CSV format."""

    last_parse_info: Dict[str, str] = {}

    @staticmethod
    def parse_log_line(line: str) -> Optional[GEPRecord]:
        """Parse one JSON-dict line from MobaXterm / UART log."""
        s = line.strip()
        if not s:
            return None
        if not s.startswith("{"):
            return None

        m = re.search(r"\{.*?\}", s)
        if not m:
            return None
        js = m.group(0)

        try:
            d = json.loads(js)
        except Exception:
            return None

        if "fn" not in d or "r0" not in d:
            return None

        try:
            return GEPRecord(
                fn=int(d["fn"]),
                r0=float(d["r0"]),
                r1=float(d["r1"]) if "r1" in d and d["r1"] not in (None, "") else None,
                r2=float(d["r2"]) if "r2" in d and d["r2"] not in (None, "") else None,
            )
        except Exception:
            return None

    @staticmethod
    def _first_existing_key(fieldnames: List[str], candidates: List[str]) -> Optional[str]:
        """Find first matching CSV column name, case-insensitive."""
        lower_to_real = {str(k).strip().lower(): str(k).strip() for k in fieldnames if k is not None}
        for c in candidates:
            k = c.strip().lower()
            if k in lower_to_real:
                return lower_to_real[k]
        return None

    @classmethod
    def parse_csv_file(cls, path: str) -> List[GEPRecord]:
        """
        Parse CSV format.

        Supported example header:
            pc_time,fn,r0_raw,r0_hampel_gate,r0_filtered_ewma,r1,r2,glitch_flag,N,alpha,k1

        r0 source priority:
            r0_raw -> r0 -> r0_hampel_gate -> r0_filtered_ewma
        """
        records: List[GEPRecord] = []
        cls.last_parse_info = {}

        with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            fn_key = cls._first_existing_key(fieldnames, ["fn", "frame", "frame_number", "frame_id"])
            r0_key = cls._first_existing_key(
                fieldnames,
                ["r0_raw", "r0", "r0_hampel_gate", "r0_filtered_ewma", "range0", "range_0"],
            )
            r1_key = cls._first_existing_key(fieldnames, ["r1", "range1", "range_1"])
            r2_key = cls._first_existing_key(fieldnames, ["r2", "range2", "range_2"])
            pc_time_key = cls._first_existing_key(fieldnames, ["pc_time", "time", "timestamp", "datetime"])

            cls.last_parse_info = {
                "mode": "CSV",
                "fn_key": str(fn_key),
                "r0_key": str(r0_key),
                "r1_key": str(r1_key),
                "r2_key": str(r2_key),
                "pc_time_key": str(pc_time_key),
            }

            if fn_key is None or r0_key is None:
                raise ValueError(
                    "CSV missing required columns. Need fn and r0/r0_raw. "
                    f"Found columns: {fieldnames}"
                )

            auto_fn = 0
            for row in reader:
                try:
                    fn_str = str(row.get(fn_key, "")).strip()
                    if fn_str == "":
                        fn = auto_fn
                    else:
                        fn = int(float(fn_str))
                    r0 = float(str(row.get(r0_key, "")).strip())

                    r1 = None
                    r2 = None
                    if r1_key is not None:
                        s1 = str(row.get(r1_key, "")).strip()
                        if s1 != "":
                            r1 = float(s1)
                    if r2_key is not None:
                        s2 = str(row.get(r2_key, "")).strip()
                        if s2 != "":
                            r2 = float(s2)

                    records.append(GEPRecord(fn=fn, r0=r0, r1=r1, r2=r2))
                    auto_fn += 1
                except Exception:
                    # skip malformed CSV rows, keep GUI robust for field data files
                    auto_fn += 1
                    continue

        by_fn: Dict[int, GEPRecord] = {}
        for rec in records:
            by_fn[rec.fn] = rec
        return [by_fn[k] for k in sorted(by_fn.keys())]

    @classmethod
    def parse_log_file(cls, path: str) -> List[GEPRecord]:
        records: List[GEPRecord] = []
        cls.last_parse_info = {"mode": "LOG", "fn_key": "fn", "r0_key": "r0", "r1_key": "r1", "r2_key": "r2"}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                rec = cls.parse_log_line(line)
                if rec is not None:
                    records.append(rec)

        by_fn: Dict[int, GEPRecord] = {}
        for rec in records:
            by_fn[rec.fn] = rec
        return [by_fn[k] for k in sorted(by_fn.keys())]

    @classmethod
    def parse_file(cls, path: str, fmt: str = "LOG") -> List[GEPRecord]:
        fmt = (fmt or "LOG").upper()
        if fmt == "CSV":
            return cls.parse_csv_file(path)
        return cls.parse_log_file(path)

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"A1886 GEP Dataset Checker - {JB_STR}")
        self.resize(1280, 820)

        self.dataset_dir = os.path.abspath(DEFAULT_DATASET_DIR)
        self.current_file: Optional[str] = None
        self.records: List[GEPRecord] = []
        self.first_fn = 0
        self.last_fn = 0

        # current plotted window cache for click/zoom support
        self.current_selected_records: List[GEPRecord] = []
        self.current_fns: List[int] = []
        self.current_r0s: List[float] = []
        self.current_r0_deglitch: List[float] = []

        # interactive selection state
        self.selected_global_fn: Optional[int] = None
        self.selected_rel_ratio: float = 0.5  # relative x-position in current window

        self._build_ui()
        self._connect_canvas_events()
        self.refresh_file_list()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)

        folder_layout = QtWidgets.QHBoxLayout()
        root.addLayout(folder_layout)

        self.dir_edit = QtWidgets.QLineEdit(self.dataset_dir)
        self.dir_edit.setMinimumWidth(520)
        btn_browse = QtWidgets.QPushButton("Browse folder")
        btn_refresh = QtWidgets.QPushButton("Refresh files")
        btn_browse.clicked.connect(self.browse_folder)
        btn_refresh.clicked.connect(self.refresh_file_list)

        folder_layout.addWidget(QtWidgets.QLabel("Dataset folder:"))
        folder_layout.addWidget(self.dir_edit, 1)
        folder_layout.addWidget(btn_browse)
        folder_layout.addWidget(btn_refresh)

        # v07: file format selector buttons. LOG = JSON-per-line, CSV = table columns.
        fmt_layout = QtWidgets.QHBoxLayout()
        root.addLayout(fmt_layout)
        self.radio_log = QtWidgets.QRadioButton("LOG")
        self.radio_csv = QtWidgets.QRadioButton("CSV")
        self.radio_log.setChecked(True)
        self.radio_log.toggled.connect(self.on_data_format_changed)
        self.radio_csv.toggled.connect(self.on_data_format_changed)
        fmt_layout.addWidget(QtWidgets.QLabel("Input format:"))
        fmt_layout.addWidget(self.radio_log)
        fmt_layout.addWidget(self.radio_csv)
        fmt_layout.addStretch(1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        splitter.addWidget(left)

        self.file_list = QtWidgets.QListWidget()
        self.file_list.itemSelectionChanged.connect(self.on_file_selected)
        left_layout.addWidget(QtWidgets.QLabel("Files in jb_GEP_dataset:"))
        left_layout.addWidget(self.file_list, 1)

        self.info_text = QtWidgets.QPlainTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(190)
        left_layout.addWidget(QtWidgets.QLabel("Info:"))
        left_layout.addWidget(self.info_text)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        ctrl = QtWidgets.QGridLayout()
        right_layout.addLayout(ctrl)

        self.win_spin = QtWidgets.QSpinBox()
        self.win_spin.setRange(10, 100000)
        self.win_spin.setValue(DEFAULT_WINDOW_SIZE)
        self.win_spin.valueChanged.connect(self.on_window_size_changed)

        self.start_spin = QtWidgets.QSpinBox()
        self.start_spin.setRange(0, 2_000_000_000)
        self.start_spin.valueChanged.connect(self.on_start_spin_changed)

        self.start_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.start_slider.setRange(0, 0)
        self.start_slider.valueChanged.connect(self.on_start_slider_changed)

        self.frame_ms_spin = QtWidgets.QDoubleSpinBox()
        self.frame_ms_spin.setRange(1.0, 10000.0)
        self.frame_ms_spin.setDecimals(3)
        self.frame_ms_spin.setValue(DEFAULT_FRAME_INTERVAL_MS)
        self.frame_ms_spin.setSuffix(" ms/frame")
        self.frame_ms_spin.valueChanged.connect(self.update_plot)

        self.deglitch_median_spin = QtWidgets.QSpinBox()
        self.deglitch_median_spin.setRange(DEGLITCH_MEDIAN_WIN_MIN, DEGLITCH_MEDIAN_WIN_MAX)
        self.deglitch_median_spin.setSingleStep(2)
        self.deglitch_median_spin.setValue(DEFAULT_DEGLITCH_MEDIAN_WIN)
        self.deglitch_median_spin.setSuffix(" frames")
        self.deglitch_median_spin.valueChanged.connect(self.on_median_spin_changed)

        self.deglitch_median_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.deglitch_median_slider.setRange(DEGLITCH_MEDIAN_WIN_MIN, DEGLITCH_MEDIAN_WIN_MAX)
        self.deglitch_median_slider.setValue(DEFAULT_DEGLITCH_MEDIAN_WIN)
        self.deglitch_median_slider.valueChanged.connect(self.on_median_slider_changed)

        self.deglitch_spike_spin = QtWidgets.QDoubleSpinBox()
        self.deglitch_spike_spin.setRange(DEGLITCH_SPIKE_TH_MIN_M, DEGLITCH_SPIKE_TH_MAX_M)
        self.deglitch_spike_spin.setDecimals(3)
        self.deglitch_spike_spin.setSingleStep(0.01)
        self.deglitch_spike_spin.setValue(DEFAULT_DEGLITCH_SPIKE_TH_M)
        self.deglitch_spike_spin.setSuffix(" m")
        self.deglitch_spike_spin.valueChanged.connect(self.on_spike_spin_changed)

        self.deglitch_spike_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.deglitch_spike_slider.setRange(
            int(DEGLITCH_SPIKE_TH_MIN_M * DEGLITCH_SPIKE_SLIDER_SCALE),
            int(DEGLITCH_SPIKE_TH_MAX_M * DEGLITCH_SPIKE_SLIDER_SCALE),
        )
        self.deglitch_spike_slider.setValue(int(DEFAULT_DEGLITCH_SPIKE_TH_M * DEGLITCH_SPIKE_SLIDER_SCALE))
        self.deglitch_spike_slider.valueChanged.connect(self.on_spike_slider_changed)

        self.deglitch_jump_spin = QtWidgets.QDoubleSpinBox()
        self.deglitch_jump_spin.setRange(DEGLITCH_JUMP_TH_MIN_M, DEGLITCH_JUMP_TH_MAX_M)
        self.deglitch_jump_spin.setDecimals(3)
        self.deglitch_jump_spin.setSingleStep(0.01)
        self.deglitch_jump_spin.setValue(DEFAULT_DEGLITCH_JUMP_TH_M)
        self.deglitch_jump_spin.setSuffix(" m")
        self.deglitch_jump_spin.valueChanged.connect(self.on_jump_spin_changed)

        self.deglitch_jump_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.deglitch_jump_slider.setRange(
            int(DEGLITCH_JUMP_TH_MIN_M * DEGLITCH_JUMP_SLIDER_SCALE),
            int(DEGLITCH_JUMP_TH_MAX_M * DEGLITCH_JUMP_SLIDER_SCALE),
        )
        self.deglitch_jump_slider.setValue(int(DEFAULT_DEGLITCH_JUMP_TH_M * DEGLITCH_JUMP_SLIDER_SCALE))
        self.deglitch_jump_slider.valueChanged.connect(self.on_jump_slider_changed)

        self.chk_r1 = QtWidgets.QCheckBox("also r1")
        self.chk_r2 = QtWidgets.QCheckBox("also r2")
        self.chk_r1.stateChanged.connect(self.update_plot)
        self.chk_r2.stateChanged.connect(self.update_plot)

        ctrl.addWidget(QtWidgets.QLabel("Window size N:"), 0, 0)
        ctrl.addWidget(self.win_spin, 0, 1)
        ctrl.addWidget(QtWidgets.QLabel("Start fn:"), 0, 2)
        ctrl.addWidget(self.start_spin, 0, 3)
        ctrl.addWidget(QtWidgets.QLabel("Frame tick:"), 0, 4)
        ctrl.addWidget(self.frame_ms_spin, 0, 5)
        ctrl.addWidget(self.chk_r1, 0, 6)
        ctrl.addWidget(self.chk_r2, 0, 7)

        ctrl.addWidget(QtWidgets.QLabel("Median win:"), 1, 0)
        ctrl.addWidget(self.deglitch_median_spin, 1, 1)
        ctrl.addWidget(self.deglitch_median_slider, 1, 2, 1, 6)

        ctrl.addWidget(QtWidgets.QLabel("Spike TH:"), 2, 0)
        ctrl.addWidget(self.deglitch_spike_spin, 2, 1)
        ctrl.addWidget(self.deglitch_spike_slider, 2, 2, 1, 6)

        ctrl.addWidget(QtWidgets.QLabel("Jump TH:"), 3, 0)
        ctrl.addWidget(self.deglitch_jump_spin, 3, 1)
        ctrl.addWidget(self.deglitch_jump_slider, 3, 2, 1, 6)

        ctrl.addWidget(QtWidgets.QLabel("Slide start fn:"), 4, 0)
        ctrl.addWidget(self.start_slider, 4, 1, 1, 7)

        hint = QtWidgets.QLabel(
            "Mouse: left click near a dot to select it. Wheel forward/backward = zoom in/out around the selected dot."
        )
        right_layout.addWidget(hint)

        self.canvas = MplCanvas(self)
        right_layout.addWidget(self.canvas, 1)

        self.status = self.statusBar()
        self.status.showMessage("Ready")

    def _connect_canvas_events(self):
        self.canvas.mpl_connect("button_press_event", self.on_canvas_click)
        self.canvas.mpl_connect("scroll_event", self.on_canvas_scroll)

    def get_data_format(self) -> str:
        if hasattr(self, "radio_csv") and self.radio_csv.isChecked():
            return "CSV"
        return "LOG"

    def on_data_format_changed(self):
        self.records = []
        self.current_file = None
        self.selected_global_fn = None
        self.refresh_file_list()
        self.update_plot()

    def browse_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select jb_GEP_dataset folder", self.dir_edit.text())
        if folder:
            self.dir_edit.setText(folder)
            self.refresh_file_list()

    def refresh_file_list(self):
        self.dataset_dir = os.path.abspath(self.dir_edit.text().strip() or DEFAULT_DATASET_DIR)
        self.file_list.clear()

        if not os.path.isdir(self.dataset_dir):
            self.info_text.setPlainText(
                f"[WARN] Folder not found:\n{self.dataset_dir}\n\n"
                f"Please create ./jb_GEP_dataset or browse to the correct folder."
            )
            return

        fmt = self.get_data_format()
        if fmt == "CSV":
            exts = (".csv",)
        else:
            exts = (".log", ".txt", ".json", ".jsonl")
        files = []
        for name in os.listdir(self.dataset_dir):
            path = os.path.join(self.dataset_dir, name)
            if os.path.isfile(path) and name.lower().endswith(exts):
                files.append((os.path.getmtime(path), name, path))
        files.sort(key=lambda x: (x[1].lower()))

        for idx, (_, name, path) in enumerate(files):
            item = QtWidgets.QListWidgetItem(f"{idx:03d}  {name}")
            item.setData(QtCore.Qt.UserRole, path)
            self.file_list.addItem(item)

        self.info_text.setPlainText(
            f"Folder: {self.dataset_dir}\n"
            f"File count: {len(files)}\n"
            f"Select one file to plot r0-fn."
        )

    def on_file_selected(self):
        items = self.file_list.selectedItems()
        if not items:
            return
        self.current_file = items[0].data(QtCore.Qt.UserRole)
        self.load_current_file()

    def load_current_file(self):
        if not self.current_file:
            return
        try:
            self.records = GEPDatasetParser.parse_file(self.current_file, self.get_data_format())
        except Exception as e:
            self.records = []
            self.info_text.setPlainText(f"[ERROR] parse failed:\n{self.current_file}\n{e}")
            return

        self.selected_global_fn = None
        self.selected_rel_ratio = 0.5

        if not self.records:
            self.info_text.setPlainText(f"[WARN] no valid records found:\n{self.current_file}")
            self.update_plot()
            return

        self.first_fn = self.records[0].fn
        self.last_fn = self.records[-1].fn

        # v05: default window size = full number of valid dots / records in selected file.
        self.win_spin.blockSignals(True)
        self.win_spin.setValue(len(self.records))
        self.win_spin.blockSignals(False)

        self._sync_start_controls(keep_value=self.first_fn)

        r0_vals = [r.r0 for r in self.records]
        self.info_text.setPlainText(
            f"File: {os.path.basename(self.current_file)}\n"
            f"Path: {self.current_file}\n"
            f"Records: {len(self.records)}\n"
            f"fn range: {self.first_fn} .. {self.last_fn}\n"
            f"r0 range: {min(r0_vals):.6f} .. {max(r0_vals):.6f}\n"
            f"Default start fn = first fn = {self.first_fn}\n"
            f"Default window size = full dots len = {len(self.records)} frames\n"
            f"Default deglitch: median_win={DEFAULT_DEGLITCH_MEDIAN_WIN}, "
            f"spike_TH={DEFAULT_DEGLITCH_SPIKE_TH_M:.3f} m, "
            f"jump_TH={DEFAULT_DEGLITCH_JUMP_TH_M:.3f} m"
        )
        self.update_plot()

    def _current_max_start(self) -> int:
        if not self.records:
            return 0
        n = max(1, int(self.win_spin.value()))
        return max(self.first_fn, self.last_fn - n + 1)

    def _sync_start_controls(self, keep_value: Optional[int] = None):
        if not self.records:
            return
        max_start = self._current_max_start()
        if keep_value is None:
            keep_value = self.start_spin.value()
        value = max(self.first_fn, min(max_start, int(keep_value)))

        self.start_spin.blockSignals(True)
        self.start_spin.setRange(self.first_fn, max_start)
        self.start_spin.setValue(value)
        self.start_spin.blockSignals(False)

        self.start_slider.blockSignals(True)
        self.start_slider.setRange(self.first_fn, max_start)
        self.start_slider.setValue(value)
        self.start_slider.blockSignals(False)

    def on_window_size_changed(self, value: int):
        del value
        self._sync_start_controls()
        self.update_plot()

    def on_start_spin_changed(self, value: int):
        self.start_slider.blockSignals(True)
        self.start_slider.setValue(value)
        self.start_slider.blockSignals(False)
        self.update_plot()

    def on_start_slider_changed(self, value: int):
        self.start_spin.blockSignals(True)
        self.start_spin.setValue(value)
        self.start_spin.blockSignals(False)
        self.update_plot()

    def _force_odd_median_win(self, value: int) -> int:
        v = max(DEGLITCH_MEDIAN_WIN_MIN, min(DEGLITCH_MEDIAN_WIN_MAX, int(value)))
        if v % 2 == 0:
            v = v + 1 if v < DEGLITCH_MEDIAN_WIN_MAX else v - 1
        return v

    def on_median_spin_changed(self, value: int):
        v = self._force_odd_median_win(value)
        if v != value:
            self.deglitch_median_spin.blockSignals(True)
            self.deglitch_median_spin.setValue(v)
            self.deglitch_median_spin.blockSignals(False)
        self.deglitch_median_slider.blockSignals(True)
        self.deglitch_median_slider.setValue(v)
        self.deglitch_median_slider.blockSignals(False)
        self.update_plot()

    def on_median_slider_changed(self, value: int):
        v = self._force_odd_median_win(value)
        if v != value:
            self.deglitch_median_slider.blockSignals(True)
            self.deglitch_median_slider.setValue(v)
            self.deglitch_median_slider.blockSignals(False)
        self.deglitch_median_spin.blockSignals(True)
        self.deglitch_median_spin.setValue(v)
        self.deglitch_median_spin.blockSignals(False)
        self.update_plot()

    def on_spike_spin_changed(self, value: float):
        iv = int(round(float(value) * DEGLITCH_SPIKE_SLIDER_SCALE))
        self.deglitch_spike_slider.blockSignals(True)
        self.deglitch_spike_slider.setValue(iv)
        self.deglitch_spike_slider.blockSignals(False)
        self.update_plot()

    def on_spike_slider_changed(self, value: int):
        v = float(value) / DEGLITCH_SPIKE_SLIDER_SCALE
        self.deglitch_spike_spin.blockSignals(True)
        self.deglitch_spike_spin.setValue(v)
        self.deglitch_spike_spin.blockSignals(False)
        self.update_plot()

    def on_jump_spin_changed(self, value: float):
        iv = int(round(float(value) * DEGLITCH_JUMP_SLIDER_SCALE))
        self.deglitch_jump_slider.blockSignals(True)
        self.deglitch_jump_slider.setValue(iv)
        self.deglitch_jump_slider.blockSignals(False)
        self.update_plot()

    def on_jump_slider_changed(self, value: int):
        v = float(value) / DEGLITCH_JUMP_SLIDER_SCALE
        self.deglitch_jump_spin.blockSignals(True)
        self.deglitch_jump_spin.setValue(v)
        self.deglitch_jump_spin.blockSignals(False)
        self.update_plot()

    def jb_deglitch(
        self,
        r0_list: List[float],
        median_win: int = DEFAULT_DEGLITCH_MEDIAN_WIN,
        spike_th_m: float = DEFAULT_DEGLITCH_SPIKE_TH_M,
        jump_th_m: float = DEFAULT_DEGLITCH_JUMP_TH_M,
    ) -> List[float]:
        """
        Convert r0 -> r0_deglitch.

        Method
        ------
        1) Use a local median window as the short-term robust reference.
        2) Treat a point as a glitch when either condition is true:
           - abs(r0[k] - local_median[k]) > spike_th_m
           - abs(r0[k] - previous_valid_value) > jump_th_m AND local median is near previous_valid_value
        3) Replace glitch by local median; otherwise keep the original r0 value.

        This is designed for short spike removal. It is not a heavy smoothing filter;
        normal r0 movement is preserved as much as possible.
        """
        if not r0_list:
            return []
        if len(r0_list) < 3:
            return list(r0_list)

        median_win = max(3, int(median_win))
        if median_win % 2 == 0:
            median_win += 1
        half = median_win // 2

        out: List[float] = []
        prev_valid = float(r0_list[0])

        for k, x0 in enumerate(r0_list):
            x = float(x0)
            a = max(0, k - half)
            b = min(len(r0_list), k + half + 1)
            local = sorted(float(v) for v in r0_list[a:b])
            med = local[len(local) // 2]

            spike_flag = abs(x - med) > spike_th_m
            jump_flag = (abs(x - prev_valid) > jump_th_m) and (abs(med - prev_valid) <= spike_th_m)

            if spike_flag or jump_flag:
                y = med
            else:
                y = x

            out.append(float(y))
            prev_valid = float(y)

        return out

    def _format_elapsed_hms(self, fn: int) -> str:
        frame_ms = float(self.frame_ms_spin.value())
        total_sec = int(round((fn - self.first_fn) * frame_ms / 1000.0))
        if total_sec < 0:
            total_sec = 0
        hh = total_sec // 3600
        mm = (total_sec % 3600) // 60
        ss = total_sec % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    def _get_record_by_fn(self, fn: int) -> Optional[GEPRecord]:
        if not self.current_selected_records:
            return None
        for rec in self.current_selected_records:
            if rec.fn == fn:
                return rec
        return None

    def _find_nearest_point(self, event) -> Optional[Tuple[int, float]]:
        if event.inaxes != self.canvas.ax:
            return None
        if not self.current_fns:
            return None

        pts = self.canvas.ax.transData.transform(list(zip(self.current_fns, self.current_r0s)))
        ex, ey = event.x, event.y
        best_i = -1
        best_d2 = None
        for i, (px, py) in enumerate(pts):
            dx = px - ex
            dy = py - ey
            d2 = dx * dx + dy * dy
            if (best_d2 is None) or (d2 < best_d2):
                best_d2 = d2
                best_i = i

        if best_i < 0 or best_d2 is None:
            return None
        if best_d2 > CLICK_PICK_PIXELS * CLICK_PICK_PIXELS:
            return None

        fn = self.current_fns[best_i]
        return fn, self.current_r0s[best_i]

    def on_canvas_click(self, event):
        if event.button != 1:
            return
        found = self._find_nearest_point(event)
        if found is None:
            return
        fn, _ = found
        self.selected_global_fn = int(fn)

        start_fn = self.start_spin.value()
        n = max(1, self.win_spin.value())
        self.selected_rel_ratio = float(fn - start_fn) / float(max(1, n - 1))
        if self.selected_rel_ratio < 0.0:
            self.selected_rel_ratio = 0.0
        if self.selected_rel_ratio > 1.0:
            self.selected_rel_ratio = 1.0

        self.update_plot()

    def on_canvas_scroll(self, event):
        if event.inaxes != self.canvas.ax:
            return
        if not self.records:
            return

        old_n = max(10, int(self.win_spin.value()))
        if event.button == "up":
            new_n = int(round(old_n * ZOOM_IN_FACTOR))
        elif event.button == "down":
            new_n = int(round(old_n * ZOOM_OUT_FACTOR))
        else:
            return

        new_n = max(10, min(100000, new_n))
        new_n = min(new_n, max(10, len(self.records)))
        if new_n == old_n:
            return

        if self.selected_global_fn is not None:
            anchor_fn = self.selected_global_fn
            ratio = self.selected_rel_ratio
        else:
            anchor_fn = self.start_spin.value() + old_n // 2
            ratio = 0.5

        new_start = int(round(anchor_fn - ratio * max(1, new_n - 1)))
        max_start = max(self.first_fn, self.last_fn - new_n + 1)
        if new_start < self.first_fn:
            new_start = self.first_fn
        if new_start > max_start:
            new_start = max_start

        self.win_spin.blockSignals(True)
        self.win_spin.setValue(new_n)
        self.win_spin.blockSignals(False)

        self._sync_start_controls(keep_value=new_start)
        self.update_plot()

    def update_plot(self):
        ax = self.canvas.ax
        fig = self.canvas.fig
        fig.clear()
        ax = fig.add_subplot(111)
        self.canvas.ax = ax

        self.current_selected_records = []
        self.current_fns = []
        self.current_r0s = []
        self.current_r0_deglitch = []

        if not self.records:
            ax.set_title("No valid data selected")
            ax.set_xlabel("fn")
            ax.set_ylabel("range / m")
            ax.grid(True)
            self.canvas.draw()
            return

        self._sync_start_controls()

        start_fn = self.start_spin.value()
        n = self.win_spin.value()
        end_fn = start_fn + n - 1
        frame_ms = float(self.frame_ms_spin.value())

        selected = [r for r in self.records if start_fn <= r.fn <= end_fn]
        self.current_selected_records = selected
        if not selected:
            ax.set_title(f"No data in selected window: fn {start_fn} .. {end_fn}")
            ax.set_xlabel("fn")
            ax.set_ylabel("range / m")
            ax.grid(True)
            self.canvas.draw()
            return

        fns = [r.fn for r in selected]
        r0s = [r.r0 for r in selected]
        r0_deglitch = self.jb_deglitch(
            r0s,
            median_win=int(self.deglitch_median_spin.value()),
            spike_th_m=float(self.deglitch_spike_spin.value()),
            jump_th_m=float(self.deglitch_jump_spin.value()),
        )
        self.current_fns = fns
        self.current_r0s = r0s
        self.current_r0_deglitch = r0_deglitch

        ax.plot(fns, r0s, color="blue", marker=".", linewidth=1.0, label="r0 raw")
        ax.plot(fns, r0_deglitch, color="red", marker=".", linewidth=1.4, label="r0_deglitch")

        if self.chk_r1.isChecked() and any(r.r1 is not None for r in selected):
            ax.plot(fns, [r.r1 for r in selected], marker=".", linewidth=1.0, label="r1")
        if self.chk_r2.isChecked() and any(r.r2 is not None for r in selected):
            ax.plot(fns, [r.r2 for r in selected], marker=".", linewidth=1.0, label="r2")

        elapsed_start_min = (start_fn - self.first_fn) * frame_ms / 1000.0 / 60.0
        elapsed_end_min = (fns[-1] - self.first_fn) * frame_ms / 1000.0 / 60.0

        ax.set_title(
            f"{os.path.basename(self.current_file or '')} | "
            f"fn {fns[0]}..{fns[-1]} | "
            f"time {elapsed_start_min:.3f}..{elapsed_end_min:.3f} min | "
            f"median={int(self.deglitch_median_spin.value())}, "
            f"spike={float(self.deglitch_spike_spin.value()):.3f}m, "
            f"jump={float(self.deglitch_jump_spin.value()):.3f}m"
        )
        ax.set_xlabel("frame number fn")
        ax.set_ylabel("range r / meter")
        ax.set_ylim(0.0, 2.0)
        ax.grid(True)
        ax.legend(loc="best")

        def fn_to_min(x):
            return (x - self.first_fn) * frame_ms / 1000.0 / 60.0

        def min_to_fn(x):
            return x * 60.0 * 1000.0 / frame_ms + self.first_fn

        top = ax.secondary_xaxis("top", functions=(fn_to_min, min_to_fn))
        top.set_xlabel("elapsed time from first fn / min")

        # mark first / last point
        for rec in (selected[0], selected[-1]):
            tmin = (rec.fn - self.first_fn) * frame_ms / 1000.0 / 60.0
            ax.annotate(
                f"fn={rec.fn}\nt={tmin:.3f}m\nr0={rec.r0:.3f}",
                xy=(rec.fn, rec.r0),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=8,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.75),
            )

        # show clicked selection box if selected fn is visible
        if self.selected_global_fn is not None:
            rec = self._get_record_by_fn(self.selected_global_fn)
            if rec is not None:
                try:
                    idx = self.current_fns.index(rec.fn)
                    y_deg = self.current_r0_deglitch[idx]
                except Exception:
                    y_deg = rec.r0
                ax.axvline(rec.fn, color="green", linestyle="--", linewidth=1.0, alpha=0.8)
                ax.plot([rec.fn], [rec.r0], marker="o", markersize=8, color="blue")
                ax.plot([rec.fn], [y_deg], marker="o", markersize=7, color="red")
                ax.annotate(
                    f"fn={rec.fn}\nt={self._format_elapsed_hms(rec.fn)}\nr0={rec.r0:.3f}",
                    xy=(rec.fn, rec.r0),
                    xytext=(12, 14),
                    textcoords="offset points",
                    fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.35", fc="lightyellow", ec="black", alpha=0.95),
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
                )

        fig.tight_layout()
        self.canvas.draw()

        status_msg = (
            f"Plot OK | start_fn={start_fn}, window={n}, records={len(selected)}, "
            f"median_win={int(self.deglitch_median_spin.value())}, "
            f"spike_TH={float(self.deglitch_spike_spin.value()):.3f}m, "
            f"jump_TH={float(self.deglitch_jump_spin.value()):.3f}m, "
            f"time={elapsed_start_min:.3f}..{elapsed_end_min:.3f} min"
        )
        if self.selected_global_fn is not None:
            rec = self._get_record_by_fn(self.selected_global_fn)
            if rec is not None:
                status_msg += f" | selected fn={rec.fn}, t={self._format_elapsed_hms(rec.fn)}, r0={rec.r0:.3f}"
        self.status.showMessage(status_msg)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
