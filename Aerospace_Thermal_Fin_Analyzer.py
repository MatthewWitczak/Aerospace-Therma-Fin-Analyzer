import sys, os, csv, traceback
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QFormLayout, QMessageBox, QDialog, QDialogButtonBox,
    QFileDialog, QFrame
)
from PyQt5.QtGui import QFont, QColor, QPalette, QFontDatabase, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# -------------------- Styl --------------------
PASTEL_BLUE = "#66a3ff"
BORDER = PASTEL_BLUE
BG_GLASS = "rgba(0,0,0,140)"
TXT = PASTEL_BLUE
TXT_SOFT = "rgba(102,163,255,200)"

def apply_glow(widget, hex_color=PASTEL_BLUE, blur=40):
    glow = QGraphicsDropShadowEffect(widget)
    glow.setBlurRadius(blur)
    glow.setOffset(0, 0)
    glow.setColor(QColor(hex_color))
    widget.setGraphicsEffect(glow)

# -------------------- Solver (analityczny) --------------------
class FinParams:
    def __init__(self):
        # Realistyczne domyślne
        self.k = 15.0         # W/(m·K) (superstop ~10–20)
        self.h = 120.0        # W/(m²·K) (konwekcja ogólna)
        self.t = 0.003        # m (grubość żebra)
        self.b = 0.010        # m (szerokość "w głąb" – out-of-plane)
        self.L = 0.03         # m (długość żebra)
        self.Tb = 900.0       # K (temp. u nasady)
        self.Tinf = 600.0     # K (otoczenie)
        # Uwaga: końcówka adiabatyczna

def solve_fin(p: FinParams, npts=300):
    # Przekrój i obwód
    A_c = p.t * p.b
    P   = 2.0 * (p.t + p.b)
    if A_c <= 0 or P <= 0 or p.k <= 0 or p.h <= 0 or p.L <= 0:
        raise ValueError("Parametry muszą być > 0.")
    m = np.sqrt(p.h * P / (p.k * A_c))
    theta_b = p.Tb - p.Tinf
    x = np.linspace(0.0, p.L, npts)
    theta = theta_b * np.cosh(m*(p.L - x)) / np.cosh(m*p.L)   # adiabatyczna końcówka
    T = p.Tinf + theta

    Q_f = p.k * A_c * m * theta_b * np.tanh(m*p.L)
    eta = np.tanh(m*p.L) / (m*p.L)
    eps = (p.k * m / p.h) * np.tanh(m*p.L)  # efektywność (effectiveness)

    return x, T, dict(m=m, Q=Q_f, eta=eta, eps=eps, Ac=A_c, P=P)

# -------------------- Worker --------------------
class SolverThread(QThread):
    done = pyqtSignal(object)   # (x, T, metrics)
    failed = pyqtSignal(str)
    def __init__(self, params: FinParams):
        super().__init__()
        self.params = params
    def run(self):
        try:
            x, T, M = solve_fin(self.params)
            self.done.emit((x, T, M))
        except Exception:
            self.failed.emit(traceback.format_exc())

# -------------------- Canvas --------------------
class FinCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(7.6, 5.6), dpi=100, facecolor='none')
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111, facecolor='none')
        self.setStyleSheet("background: transparent;")
        self._setup_style()
        self.reset_empty()

    def _setup_style(self):
        self.ax.set_xlabel('x [m]', color=TXT, labelpad=10)
        self.ax.set_ylabel('T [K]', color=TXT, labelpad=10)
        self.ax.tick_params(colors=TXT, which='both', labelsize=11)
        for spine in self.ax.spines.values():
            spine.set_color(PASTEL_BLUE); spine.set_alpha(0.7); spine.set_linewidth(1.0)
        self.ax.grid(True, color=PASTEL_BLUE, alpha=0.15, linewidth=0.9)
        self.fig.subplots_adjust(right=0.83, left=0.09, top=0.95, bottom=0.10)

    def reset_empty(self):
        self.ax.clear()
        self._setup_style()
        self.draw()

    def plot_profile(self, x, T):
        self.ax.clear()
        self._setup_style()
        self.ax.plot(x, T, linewidth=2.2, color=PASTEL_BLUE, label="T(x)")
        self.ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0),
                       facecolor=(0,0,0,0.6), edgecolor=PASTEL_BLUE)
        self.draw()

# -------------------- Dialogs --------------------
class ParamDialog(QDialog):
    def __init__(self, font_family, p: FinParams, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parameters")
        self.setModal(True); self.setMinimumWidth(480)
        self.font_family = font_family
        self._p = p

        label_font = QFont(self.font_family, 12)
        input_font = QFont(self.font_family, 12)

        def mkle(val):
            le = QLineEdit(str(val))
            le.setStyleSheet(f"background-color:{BG_GLASS}; color:{TXT}; border:1px solid {BORDER}; padding:6px;")
            le.setFont(input_font); return le
        def mkl(txt):
            l = QLabel(txt); l.setFont(label_font)
            l.setStyleSheet(f"color:{TXT_SOFT}; background:transparent;"); return l

        self.le_k   = mkle(p.k)
        self.le_h   = mkle(p.h)
        self.le_t   = mkle(p.t)
        self.le_b   = mkle(p.b)
        self.le_L   = mkle(p.L)
        self.le_Tb  = mkle(p.Tb)
        self.le_Tinf= mkle(p.Tinf)

        form = QFormLayout()
        form.addRow(mkl("k [W/(m·K)]"), self.le_k)
        form.addRow(mkl("h [W/(m²·K)]"), self.le_h)
        form.addRow(mkl("thickness t [m]"), self.le_t)
        form.addRow(mkl("width b [m]"), self.le_b)
        form.addRow(mkl("length L [m]"), self.le_L)
        form.addRow(mkl("T_b [K]"), self.le_Tb)
        form.addRow(mkl("T∞ [K]"), self.le_Tinf)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(
            "QPushButton { background-color: rgba(0,0,0,150); border: 2px solid " + BORDER +
            "; color: " + TXT + "; padding: 8px 12px; font-size: 14px; }"
            "QPushButton:hover { background-color: #001133; }"
        )

        root = QVBoxLayout(); root.addLayout(form); root.addWidget(buttons, alignment=Qt.AlignRight)
        self.setLayout(root)

    def apply(self):
        try:
            p = self._p
            p.k = float(self.le_k.text()); p.h = float(self.le_h.text())
            p.t = float(self.le_t.text()); p.b = float(self.le_b.text())
            p.L = float(self.le_L.text())
            p.Tb = float(self.le_Tb.text()); p.Tinf = float(self.le_Tinf.text())
            if min(p.k, p.h, p.t, p.b, p.L) <= 0:
                raise ValueError("Wszystkie wartości muszą być > 0.")
        except Exception as e:
            QMessageBox.warning(self, "Input error", f"Check inputs.\n\n{e}", QMessageBox.Ok)
            return False
        return True

class PresetDialog(QDialog):
    def __init__(self, font_family, apply_cb, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Presets")
        self.setModal(True); self.setMinimumWidth(520)
        self.apply_cb = apply_cb

        title = QLabel("SELECT PRESET")
        title.setFont(QFont(font_family, 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:" + TXT + ";")
        info = QLabel("Presets ustawiają kilka parametrów jednocześnie.")
        info.setFont(QFont(font_family, 11)); info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color:" + TXT_SOFT + ";")

        btn_style = (
            "QPushButton { background-color: rgba(0,0,0,150); border: 2px solid " + BORDER +
            "; color: " + TXT + "; padding: 10px; font-size: 14px; }"
            "QPushButton:hover { background-color: #001133; }"
        )

        presets = [
            ("Baseline (k=15, h=120, t=3mm, b=10mm, L=30mm, Tb=900K, T∞=600K)",
             dict(k=15.0, h=120.0, t=0.003, b=0.010, L=0.03, Tb=900.0, Tinf=600.0)),
            ("High convection (h=300) + thinner fin (t=2mm)",
             dict(h=300.0, t=0.002)),
            ("Thick fin (t=5mm) + long (L=50mm)",
             dict(t=0.005, L=0.050)),
            ("Cool ambient (T∞=500K) + hot base (T_b=1000K)",
             dict(Tinf=500.0, Tb=1000.0)),
        ]

        layout = QVBoxLayout(); layout.addWidget(title); layout.addWidget(info); layout.addSpacing(6)
        for name, changes in presets:
            b = QPushButton(name); b.setStyleSheet(btn_style); b.setFont(QFont(font_family, 12))
            def make_handler(opts):
                def handler():
                    self.apply_cb(opts); self.accept()
                return handler
            b.clicked.connect(make_handler(changes))
            layout.addWidget(b)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        close_box.button(QDialogButtonBox.Close).setStyleSheet(
            "QPushButton { background-color: rgba(0,0,0,150); border: 2px solid " + BORDER +
            "; color: " + TXT + "; padding: 8px 12px; font-size: 14px; }"
            "QPushButton:hover { background-color: #001133; }"
        )
        layout.addSpacing(8); layout.addWidget(close_box, alignment=Qt.AlignRight)
        self.setLayout(layout)

# ---------- Dialog: About ----------
class AboutDialog(QDialog):
    def __init__(self, font_family, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setModal(True)
        self.setMinimumWidth(600)

        title = QLabel("ABOUT APPLICATION")
        title.setFont(QFont(font_family, 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #3399ff;")

        description = QLabel(
            "The application is a 1D thermal analysis tool for cooling fins.\n"
            "It numerically solves the steady-state heat conduction equation with convection along a fin, "
            "using a finite-difference method.\n\n"
            "The program allows the user to define:\n"
            " • Geometric parameters – fin length, cross-sectional area, and perimeter.\n"
            " • Material properties – thermal conductivity k.\n"
            " • Boundary conditions – base temperature T_b, ambient temperature T_∞, and convection coefficient h.\n\n"
            "The solver computes the temperature distribution along the fin and visualizes it as a plot.\n"
            "Results can be exported to CSV (tabular data) or PNG (temperature profile graph).\n\n"
            "The tool demonstrates the principles of heat conduction–convection coupling, "
            "fin efficiency, and the impact of material and design choices on thermal performance."
        )
        description.setFont(QFont(font_family, 12))
        description.setWordWrap(True)
        description.setStyleSheet("color: rgba(51,153,255,220);")

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Close).setStyleSheet(
            "QPushButton { background-color: rgba(0,0,0,150); border: 2px solid #3399ff;"
            "color: #3399ff; padding: 8px 12px; font-size: 14px; }"
            "QPushButton:hover { background-color: #001a33; }"
        )

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(description)
        layout.addSpacing(15)
        layout.addWidget(btns, alignment=Qt.AlignRight)
        self.setLayout(layout)


# -------------------- Canvas + UI --------------------
class FinCanvasWidget(FigureCanvas):
    pass  # (zostawione dla ewentualnej rozbudowy)

class ResultsBox(QFrame):
    def __init__(self, font_family):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background-color:{BG_GLASS}; border:2px solid {BORDER}; border-radius:8px; }}")
        layout = QVBoxLayout()
        title = QLabel("RESULTS")
        title.setFont(QFont(font_family, 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:" + PASTEL_BLUE + ";")
        apply_glow(title, blur=20)
        self.lab_Q  = QLabel("Q = — W")
        self.lab_eta= QLabel("η = —")
        self.lab_eps= QLabel("ε = —")
        self.lab_m  = QLabel("m = — 1/m")
        for w in (self.lab_Q, self.lab_eta, self.lab_eps, self.lab_m):
            w.setFont(QFont(font_family, 15)); w.setAlignment(Qt.AlignCenter)
            w.setStyleSheet("color:" + TXT_SOFT + ";")
        layout.addWidget(title); layout.addWidget(self.lab_Q); layout.addWidget(self.lab_eta)
        layout.addWidget(self.lab_eps); layout.addWidget(self.lab_m)
        self.setLayout(layout)
        apply_glow(self, blur=18)

class FinUI(QWidget):
    def __init__(self):
        super().__init__()
        self.init_font()
        self.params = FinParams()
        self._worker = None
        self._last = None  # (x, T, metrics)
        self.initUI()

    def init_font(self):
        self.font_family = "Arial"
        font_path = os.path.join(os.path.dirname(__file__), "Aurebesh.ttf")
        if os.path.exists(font_path):
            fid = QFontDatabase.addApplicationFont(font_path)
            fams = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
            if fams: self.font_family = fams[0]

    def initUI(self):
        self.setWindowTitle("Aerospace Thermal Fin Analyzer")
        self.resize(1200, 760)

        # Tło (opcjonalna grafika)
        bg_path = os.path.join(os.path.dirname(__file__), "cooling_bg.jpg")
        pal = QPalette(); pal.setColor(QPalette.Window, QColor(0, 0, 0))
        if os.path.exists(bg_path):
            pal.setBrush(QPalette.Window, QPixmap(bg_path))
        pal.setColor(QPalette.WindowText, QColor(PASTEL_BLUE))
        self.setPalette(pal)

        # Header
        title = QLabel("AEROSPACE THERMAL FIN ANALYZER")
        title.setFont(QFont(self.font_family, 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:" + PASTEL_BLUE + "; background: transparent;")
        apply_glow(title, blur=50)

        sub = QLabel("AEROSPACE ENGINEERING • THERMAL ANALYSIS • HEAT TRANSFER")
        sub.setFont(QFont(self.font_family, 13))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:" + TXT_SOFT + "; background: transparent;")
        apply_glow(sub, blur=30)

        # Buttons
        btn_style = (
            "QPushButton { background-color: rgba(0,0,0,150); border: 2px solid " + BORDER +
            "; color: " + TXT + "; padding: 12px 16px; font-size: 16px; }"
            "QPushButton:hover { background-color: #001133; }"
        )
        self.btn_params = QPushButton("PARAMETERS")
        self.btn_presets= QPushButton("PRESETS")
        self.btn_run    = QPushButton("RUN")
        self.btn_png    = QPushButton("EXPORT PNG")
        self.btn_csv    = QPushButton("EXPORT CSV")
        self.btn_clear  = QPushButton("CLEAR")
        self.btn_about  = QPushButton("ABOUT")
        for b in (self.btn_params, self.btn_presets, self.btn_run, self.btn_png, self.btn_csv, self.btn_clear, self.btn_about):
            b.setFont(QFont(self.font_family, 13, QFont.Bold))
            b.setStyleSheet(btn_style); apply_glow(b, blur=20)

        btn_col = QVBoxLayout()
        for b in (self.btn_params, self.btn_presets, self.btn_run, self.btn_png, self.btn_csv, self.btn_clear, self.btn_about):
            btn_col.addWidget(b)

        # Results
        self.results = ResultsBox(self.font_family)
        btn_col.addSpacing(10); btn_col.addWidget(self.results); btn_col.addStretch(1)

        # Canvas
        self.canvas = FinCanvas()

        # Layout
        header = QVBoxLayout(); header.addWidget(title); header.addWidget(sub)
        mid = QHBoxLayout(); mid.addLayout(btn_col, 0); mid.addWidget(self.canvas, 1)
        root = QVBoxLayout(); root.addLayout(header); root.addLayout(mid)
        self.setLayout(root)

        # Signals
        self.btn_params.clicked.connect(self.open_params)
        self.btn_presets.clicked.connect(self.open_presets)
        self.btn_run.clicked.connect(self.on_run)
        self.btn_png.clicked.connect(self.on_export_png)
        self.btn_csv.clicked.connect(self.on_export_csv)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_about.clicked.connect(self.open_about)

        self.on_clear()

    # ---- Actions ----
    def open_params(self):
        dlg = ParamDialog(self.font_family, self.params, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply()

    def open_presets(self):
        def apply_cb(changes: dict):
            for k, v in changes.items():
                setattr(self.params, k, v)
        PresetDialog(self.font_family, apply_cb, parent=self).exec_()

    def open_about(self):
        AboutDialog(self.font_family, parent=self).exec_()

    def on_clear(self):
        self.canvas.reset_empty()
        self.results.lab_Q.setText("Q = — W")
        self.results.lab_eta.setText("η = —")
        self.results.lab_eps.setText("ε = —")
        self.results.lab_m.setText("m = — 1/m")

    def on_run(self):
        if hasattr(self, "_worker") and self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Fin Designer", "Solver już pracuje.")
            return
        self._worker = SolverThread(self.params)
        self._worker.done.connect(self.on_done)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def on_done(self, payload):
        x, T, M = payload
        self._last = (x, T, M, dict(k=self.params.k, h=self.params.h, t=self.params.t, b=self.params.b, L=self.params.L, Tb=self.params.Tb, Tinf=self.params.Tinf))
        self.canvas.plot_profile(x, T)
        self.results.lab_Q.setText(f"Q = {M['Q']:.2f} W")
        self.results.lab_eta.setText(f"η = {M['eta']:.3f} (-)")
        self.results.lab_eps.setText(f"ε = {M['eps']:.3f} (-)")
        self.results.lab_m.setText(f"m = {M['m']:.1f} 1/m")

    def on_failed(self, err):
        QMessageBox.critical(self, "Solver error", err)

    def on_export_png(self):
        if not getattr(self, "_last", None):
            QMessageBox.information(self, "Export", "Brak wyników do eksportu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz PNG", "fin_profile.png", "PNG (*.png)")
        if not path: return
        x, T, *_ = self._last
        fig = Figure(figsize=(7.6,5.6), dpi=120)
        ax = fig.add_subplot(111)
        ax.plot(x, T, lw=2.2)
        ax.set_xlabel("x [m]"); ax.set_ylabel("T [K]"); ax.set_title("Fin temperature profile")
        fig.savefig(path, dpi=200, bbox_inches="tight")

    def on_export_csv(self):
        if not getattr(self, "_last", None):
            QMessageBox.information(self, "Export", "Brak wyników do eksportu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz CSV", "fin_profile.csv", "CSV (*.csv)")
        if not path: return
        x, T, M, P = self._last
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["# params", P])
            w.writerow(["# m [1/m]", M["m"]])
            w.writerow(["# Q [W]", M["Q"]])
            w.writerow(["# eta [-]", M["eta"]])
            w.writerow(["# eps [-]", M["eps"]])
            w.writerow(["x [m]", "T [K]"])
            for xi, Ti in zip(x, T):
                w.writerow([xi, Ti])

# -------------------- Run --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = FinUI()
    ui.show()
    sys.exit(app.exec_())
