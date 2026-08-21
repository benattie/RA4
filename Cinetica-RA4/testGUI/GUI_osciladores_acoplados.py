import sys
import json
import csv
import os
import math
import time
import queue
import threading
from collections import deque
import numpy as np
from scipy.integrate import Radau

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel,
                             QDialog, QLineEdit, QFileDialog, QFormLayout, QMessageBox,
                             QCheckBox)
from PyQt6.QtCore import QThread, QTimer, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- Ventana Auxiliar (Condiciones Iniciales para 3 Osciladores) ---
class ConfigDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Condiciones Iniciales (Osciladores Acoplados)")
        self.resize(350, 250)

        default_config = {
            "x10": 1.0, "v10": 0.0,
            "x20": 0.0, "v20": 0.0,
            "x30": 0.0, "v30": 0.0,
            "dt": 0.001
        }
        self.config = current_config or default_config

        layout = QFormLayout(self)

        self.input_x10 = QLineEdit(str(self.config.get("x10", 1.0)))
        self.input_x20 = QLineEdit(str(self.config.get("x20", 0.0)))
        self.input_x30 = QLineEdit(str(self.config.get("x30", 0.0)))
        self.input_dt = QLineEdit(str(self.config.get("dt", 0.001)))

        layout.addRow("Posición inicial Masa 1 (x₁₀):", self.input_x10)
        layout.addRow("Posición inicial Masa 2 (x₂₀):", self.input_x20)
        layout.addRow("Posición inicial Masa 3 (x₃₀):", self.input_x30)
        layout.addRow("Paso de tiempo (Δt):", self.input_dt)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Aplicar")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        layout.addRow(btn_layout)

    def get_values(self):
        try:
            return {
                "x10": float(self.input_x10.text()),
                "v10": 0.0,
                "x20": float(self.input_x20.text()),
                "v20": 0.0,
                "x30": float(self.input_x30.text()),
                "v30": 0.0,
                "dt": float(self.input_dt.text())
            }
        except ValueError:
            QMessageBox.critical(self, "Error", "Por favor ingresa valores numéricos válidos.")
            return self.config

# --- Ventana Auxiliar (Constantes del Sistema Acoplado) ---
class ConstantsDialog(QDialog):
    def __init__(self, parent=None, current_constants=None):
        super().__init__(parent)
        self.setWindowTitle("Constantes de Resortes y Masas")
        self.resize(350, 250)

        default_constants = {
            "k1": 1.0, "k2": 10.0, "k3": 100.0,
            "m1": 1.0, "m2": 1.0, "m3": 1.0,
            "b1": 0.1, "b2": 0.1, "b3": 0.1
        }
        self.constants = current_constants or default_constants

        layout = QFormLayout(self)

        self.input_k1 = QLineEdit(str(self.constants.get("k1", 1.0)))
        self.input_k2 = QLineEdit(str(self.constants.get("k2", 10.0)))
        self.input_k3 = QLineEdit(str(self.constants.get("k3", 100.0)))
        self.input_m = QLineEdit(str(self.constants.get("m1", 1.0)))
        self.input_b = QLineEdit(str(self.constants.get("b1", 0.1)))

        layout.addRow("Resorte k₁ (N/m):", self.input_k1)
        layout.addRow("Resorte k₂ (N/m):", self.input_k2)
        layout.addRow("Resorte k₃ (N/m):", self.input_k3)
        layout.addRow("Masa (m₁=m₂=m₃) (kg):", self.input_m)
        layout.addRow("Amortiguamiento b:", self.input_b)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Aplicar")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        layout.addRow(btn_layout)

    def get_values(self):
        try:
            m_val = float(self.input_m.text())
            b_val = float(self.input_b.text())
            return {
                "k1": float(self.input_k1.text()),
                "k2": float(self.input_k2.text()),
                "k3": float(self.input_k3.text()),
                "m1": m_val, "m2": m_val, "m3": m_val,
                "b1": b_val, "b2": b_val, "b3": b_val
            }
        except ValueError:
            QMessageBox.critical(self, "Error", "Por favor ingresa valores numéricos válidos.")
            return self.constants

# --- Hilo Desacoplado: Escritura en Disco por Bloques ---
class DiskWriterThread(QThread):
    def __init__(self, filename=None, block_size=500, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.block_size = block_size
        self.queue = queue.Queue()
        self._running = True

    def run(self):
        buffer = []
        while self._running or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.05)
                if isinstance(item, list) and len(item) > 0 and isinstance(item[0], list):
                    buffer.extend(item)
                else:
                    buffer.append(item)
                self.queue.task_done()
                if len(buffer) >= self.block_size:
                    self._flush_buffer(buffer)
                    buffer = []
            except queue.Empty:
                if buffer:
                    self._flush_buffer(buffer)
                    buffer = []
        if buffer:
            self._flush_buffer(buffer)
            buffer = []

    def _flush_buffer(self, buffer):
        if not buffer:
            return
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(buffer)
        except PermissionError:
            pass

    def stop(self):
        self._running = False
        self.wait()

# --- Hilo Desacoplado: Simulación Física Ultrarrápida (Vectorizada + Ring Buffer) ---
class CoupledSimulationThread(QThread):
    def __init__(self, writer_queue, config=None, constants=None, parent=None):
        super().__init__(parent)
        self.writer_queue = writer_queue
        self.lock = threading.Lock()

        # Buffers acotados (Ring Buffers de tamaño 15,000) para evitar uso excesivo de memoria y pausas de GC
        self.t_data = deque(maxlen=15000)
        self.x1_data = deque(maxlen=15000)
        self.x2_data = deque(maxlen=15000)
        self.x3_data = deque(maxlen=15000)

        self._running = False
        self.solver = None

        # Carga inicial de parámetros físicos y configuración mediante método dedicado
        self.load_from_config(config or {}, constants or {})

    def load_from_config(self, config, constants):
        """Carga/actualiza parámetros físicos y condiciones iniciales desde otra fuente, función o clase."""
        with self.lock:
            self.k1 = constants.get("k1", 1.0)
            self.k2 = constants.get("k2", 10.0)
            self.k3 = constants.get("k3", 100.0)

            self.m1 = constants.get("m1", 1.0)
            self.m2 = constants.get("m2", 1.0)
            self.m3 = constants.get("m3", 1.0)

            self.b1 = constants.get("b1", 0.1)
            self.b2 = constants.get("b2", 0.1)
            self.b3 = constants.get("b3", 0.1)

            self.dt = config.get("dt", 0.001)

            self.t = 0.0
            self.y = np.array([
                config.get("x10", 1.0), config.get("v10", 0.0),
                config.get("x20", 0.0), config.get("v20", 0.0),
                config.get("x30", 0.0), config.get("v30", 0.0)
            ], dtype=float)

            self.t_data.clear()
            self.x1_data.clear()
            self.x2_data.clear()
            self.x3_data.clear()

    def _derivatives(self, t, y):
        x1, v1, x2, v2, x3, v3 = y
        with self.lock:
            k1, k2, k3 = self.k1, self.k2, self.k3
            m1, m2, m3 = self.m1, self.m2, self.m3
            b1, b2, b3 = self.b1, self.b2, self.b3

        dx1 = v1
        dv1 = (-(k1 + k2) * x1 + k2 * x2 - b1 * v1) / m1

        dx2 = v2
        dv2 = (k2 * x1 - (k2 + k3) * x2 + k3 * x3 - b2 * v2) / m2

        dx3 = v3
        dv3 = (k3 * x2 - k3 * x3 - b3 * v3) / m3

        return [dx1, dv1, dx2, dv2, dx3, dv3]

    def _jacobian(self, t, y):
        with self.lock:
            k1, k2, k3 = self.k1, self.k2, self.k3
            m1, m2, m3 = self.m1, self.m2, self.m3
            b1, b2, b3 = self.b1, self.b2, self.b3

        return np.array([
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [-(k1 + k2) / m1, -b1 / m1, k2 / m1, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [k2 / m2, 0.0, -(k2 + k3) / m2, -b2 / m2, k3 / m2, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, k3 / m3, 0.0, -k3 / m3, -b3 / m3]
        ], dtype=float)

    def init_solver(self):
        with self.lock:
            y0 = self.y.copy()
            t0 = self.t
            dt = self.dt

        self.solver = Radau(
            self._derivatives,
            t0, y0,
            t_bound=np.inf,
            max_step=dt,
            rtol=1e-6,
            atol=1e-8,
            jac=self._jacobian
        )

    def update_params(self, k1, k2, k3, m=1.0, b=0.1):
        with self.lock:
            self.k1 = k1
            self.k2 = k2
            self.k3 = k3
            self.m1 = self.m2 = self.m3 = m
            self.b1 = self.b2 = self.b3 = b

    def set_config(self, config):
        with self.lock:
            self.dt = config.get("dt", 0.005)

    def reset_state(self, x10, x20, x30):
        with self.lock:
            self.t = 0.0
            self.y = np.array([x10, 0.0, x20, 0.0, x30, 0.0], dtype=float)
            self.t_data.clear()
            self.x1_data.clear()
            self.x2_data.clear()
            self.x3_data.clear()
        self.init_solver()

    def get_plot_data(self):
        with self.lock:
            return (list(self.t_data), list(self.x1_data), list(self.x2_data), list(self.x3_data),
                    self.t, self.y[0], self.y[2], self.y[4])

    def run(self):
        self._running = True
        if self.solver is None:
            self.init_solver()

        last_time = time.perf_counter()
        accumulator = 0.0

        while self._running:
            now = time.perf_counter()
            elapsed = now - last_time
            last_time = now

            if elapsed > 0.2:
                elapsed = 0.2

            accumulator += elapsed

            with self.lock:
                dt = self.dt

            if accumulator >= dt:
                n_steps = int(accumulator // dt)
                if n_steps > 1000:
                    n_steps = 1000

                advance_time = n_steps * dt
                target_t = self.t + advance_time

                try:
                    # Avanzar el solver Radau hasta superar target_t
                    while self.solver.t < target_t:
                        self.solver.step()

                    # Evaluación Vectorizada de Alta Velocidad (1 sola llamada a dense_output)
                    sol = self.solver.dense_output()
                    t_eval = np.linspace(self.t + dt, target_t, n_steps)
                    y_eval = sol(t_eval)  # Matriz NumPy 6 x n_steps

                    self.t = target_t
                    self.y = y_eval[:, -1]
                    accumulator -= advance_time

                    with self.lock:
                        k1, k2, k3 = self.k1, self.k2, self.k3

                    batch_samples = []
                    for i in range(n_steps):
                        t_i = float(t_eval[i])
                        x1_i, v1_i, x2_i, v2_i, x3_i, v3_i = y_eval[:, i]
                        batch_samples.append([
                            round(t_i, 6), round(x1_i, 6), round(v1_i, 6),
                            round(x2_i, 6), round(v2_i, 6), round(x3_i, 6), round(v3_i, 6),
                            k1, k2, k3
                        ])
                        with self.lock:
                            self.t_data.append(t_i)
                            self.x1_data.append(x1_i)
                            self.x2_data.append(x2_i)
                            self.x3_data.append(x3_i)

                    self.writer_queue.put(batch_samples)
                except Exception:
                    pass

            time.sleep(0.001)

    def stop(self):
        self._running = False
        self.wait()

# --- Ventana Principal del Sistema Acoplado (Optimización Vectorizada de Alto Rendimiento) ---
class CoupledMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Osciladores Acoplados Rígidos (Rendimiento Extremo - Sin Lag)")
        self.resize(1000, 680)

        self.config = {
            "x10": 1.0, "v10": 0.0,
            "x20": 0.0, "v20": 0.0,
            "x30": 0.0, "v30": 0.0,
            "dt": 0.001
        }
        self.constants = {
            "k1": 1.0, "k2": 10.0, "k3": 100.0,
            "m1": 1.0, "m2": 1.0, "m3": 1.0,
            "b1": 0.1, "b2": 0.1, "b3": 0.1
        }
        self.csv_filename = "simulacion_acoplados.csv"

        self.k1 = self.constants["k1"]
        self.k2 = self.constants["k2"]
        self.k3 = self.constants["k3"]

        self.writer_thread = DiskWriterThread(filename=self.csv_filename, block_size=500, parent=self)
        self.sim_thread = CoupledSimulationThread(self.writer_thread.queue, self.config, self.constants, parent=self)

        self.background = None
        self.needs_full_draw = True

        self.current_window_min = 0.0
        self.current_window_max = 10.0

        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(16)
        self.plot_timer.timeout.connect(self.update_plot_60fps)

        self.init_ui()
        self.reset_simulation()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- Panel Izquierdo: Gráfico Multi-Traza ---
        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Posición (x)")
        self.ax.set_title("Resortes: k₁=1, k₂=10, k₃=100 N/m (Optimización C-Vectorizada)")
        self.ax.grid(True)

        self.line1, = self.ax.plot([], [], label="Masa 1 (x₁) [k₁=1]", color="blue", lw=1.5, animated=True)
        self.line2, = self.ax.plot([], [], label="Masa 2 (x₂) [k₂=10]", color="green", lw=1.5, animated=True)
        self.line3, = self.ax.plot([], [], label="Masa 3 (x₃) [k₃=100]", color="red", lw=1.5, animated=True)
        self.ax.legend(loc="upper right")

        main_layout.addWidget(self.canvas, stretch=3)

        # --- Panel Derecho: Controles ---
        control_layout = QVBoxLayout()

        self.lbl_k1 = QLabel(f"Resorte k₁: {self.k1:.1f} N/m")
        self.slider_k1 = QSlider(Qt.Orientation.Horizontal)
        self.slider_k1.setRange(1, 50)
        self.slider_k1.setValue(int(self.k1))
        self.slider_k1.valueChanged.connect(self.update_parameters)

        self.lbl_k2 = QLabel(f"Resorte k₂: {self.k2:.1f} N/m")
        self.slider_k2 = QSlider(Qt.Orientation.Horizontal)
        self.slider_k2.setRange(1, 100)
        self.slider_k2.setValue(int(self.k2))
        self.slider_k2.valueChanged.connect(self.update_parameters)

        self.lbl_k3 = QLabel(f"Resorte k₃: {self.k3:.1f} N/m")
        self.slider_k3 = QSlider(Qt.Orientation.Horizontal)
        self.slider_k3.setRange(10, 300)
        self.slider_k3.setValue(int(self.k3))
        self.slider_k3.valueChanged.connect(self.update_parameters)

        control_layout.addWidget(self.lbl_k1)
        control_layout.addWidget(self.slider_k1)
        control_layout.addWidget(self.lbl_k2)
        control_layout.addWidget(self.slider_k2)
        control_layout.addWidget(self.lbl_k3)
        control_layout.addWidget(self.slider_k3)

        control_layout.addSpacing(15)

        self.btn_start = QPushButton("Iniciar Simulación")
        self.btn_start.clicked.connect(self.start_simulation)

        self.btn_pause = QPushButton("Pausar Simulación")
        self.btn_pause.clicked.connect(self.pause_simulation)

        self.btn_reset = QPushButton("Reiniciar Simulación")
        self.btn_reset.clicked.connect(self.reset_simulation)

        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_reset)

        control_layout.addSpacing(15)

        # Opciones de visualización
        self.chk_sliding_window = QCheckBox("Modo Osciloscopio (Páginas de 10 s)")
        self.chk_sliding_window.setChecked(True)
        self.chk_sliding_window.stateChanged.connect(self.trigger_full_redraw)
        control_layout.addWidget(self.chk_sliding_window)

        control_layout.addSpacing(10)

        self.btn_config_init = QPushButton("Condiciones Iniciales...")
        self.btn_config_init.clicked.connect(self.open_config_dialog)

        self.btn_config_const = QPushButton("Constantes del Sistema...")
        self.btn_config_const.clicked.connect(self.open_constants_dialog)

        control_layout.addWidget(self.btn_config_init)
        control_layout.addWidget(self.btn_config_const)

        control_layout.addStretch()
        main_layout.addLayout(control_layout, stretch=1)

    def trigger_full_redraw(self):
        self.needs_full_draw = True

    def update_parameters(self):
        self.k1 = float(self.slider_k1.value())
        self.k2 = float(self.slider_k2.value())
        self.k3 = float(self.slider_k3.value())

        self.lbl_k1.setText(f"Resorte k₁: {self.k1:.1f} N/m")
        self.lbl_k2.setText(f"Resorte k₂: {self.k2:.1f} N/m")
        self.lbl_k3.setText(f"Resorte k₃: {self.k3:.1f} N/m")

        self.constants["k1"] = self.k1
        self.constants["k2"] = self.k2
        self.constants["k3"] = self.k3

        if hasattr(self, 'sim_thread'):
            self.sim_thread.update_params(self.k1, self.k2, self.k3)

    def open_config_dialog(self):
        dialog = ConfigDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_values()
            self.sim_thread.set_config(self.config)
            self.reset_simulation()

    def open_constants_dialog(self):
        dialog = ConstantsDialog(self, self.constants)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.constants = dialog.get_values()
            self.k1 = self.constants["k1"]
            self.k2 = self.constants["k2"]
            self.k3 = self.constants["k3"]
            self.slider_k1.setValue(int(self.k1))
            self.slider_k2.setValue(int(self.k2))
            self.slider_k3.setValue(int(self.k3))
            self.sim_thread.update_params(self.k1, self.k2, self.k3)
            self.reset_simulation()

    def start_simulation(self):
        t_data, _, _, _, _, _, _, _ = self.sim_thread.get_plot_data()
        if not os.path.exists(self.csv_filename) or len(t_data) == 0:
            try:
                with open(self.csv_filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Tiempo (s)", "x1", "v1", "x2", "v2", "x3", "v3", "k1", "k2", "k3"])
            except PermissionError:
                QMessageBox.warning(self, "Error de archivo", "No se pudo escribir en el CSV.")
                return

        if not self.writer_thread.isRunning():
            self.writer_thread.start()

        if not self.sim_thread.isRunning():
            self.sim_thread.start()

        self.needs_full_draw = True
        self.plot_timer.start(16)

    def pause_simulation(self):
        self.plot_timer.stop()
        if self.sim_thread.isRunning():
            self.sim_thread.stop()

    def reset_simulation(self):
        self.pause_simulation()
        self.sim_thread.reset_state(
            self.config.get("x10", 1.0),
            self.config.get("x20", 0.0),
            self.config.get("x30", 0.0)
        )
        self.line1.set_data([], [])
        self.line2.set_data([], [])
        self.line3.set_data([], [])

        self.current_window_min = 0.0
        self.current_window_max = 10.0
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(-2.5, 2.5)
        self.needs_full_draw = True
        self.canvas.draw()

    def update_plot_60fps(self):
        t_data, x1_data, x2_data, x3_data, current_t, x1, x2, x3 = self.sim_thread.get_plot_data()
        if not t_data:
            return

        t_arr = np.array(t_data)

        if self.chk_sliding_window.isChecked():
            window_size = 10.0
            overlap = 2.0

            if current_t <= window_size:
                t_min = 0.0
                t_max = window_size
            else:
                if current_t > self.current_window_max:
                    self.current_window_min = current_t - overlap
                    self.current_window_max = self.current_window_min + window_size
                    self.needs_full_draw = True

                t_min = self.current_window_min
                t_max = self.current_window_max

            idx_start = int(np.searchsorted(t_arr, t_min))
            t_plot = t_data[idx_start:]
            x1_plot = x1_data[idx_start:]
            x2_plot = x2_data[idx_start:]
            x3_plot = x3_data[idx_start:]
        else:
            t_min = 0.0
            t_max = max(10.0, current_t + 2.0)
            if len(t_data) > 12000:
                step = len(t_data) // 6000
                t_plot = t_data[::step]
                x1_plot = x1_data[::step]
                x2_plot = x2_data[::step]
                x3_plot = x3_data[::step]
            else:
                t_plot = t_data
                x1_plot = x1_data
                x2_plot = x2_data
                x3_plot = x3_data

        curr_xlim = self.ax.get_xlim()
        curr_ylim = self.ax.get_ylim()

        if abs(curr_xlim[0] - t_min) > 0.01 or abs(curr_xlim[1] - t_max) > 0.01:
            self.ax.set_xlim(t_min, t_max)
            self.needs_full_draw = True

        all_max = max(abs(x1), abs(x2), abs(x3), 1.5)
        target_ylim = max(2.5, all_max * 1.3)
        if target_ylim > curr_ylim[1] or target_ylim < curr_ylim[1] * 0.5:
            self.ax.set_ylim(-target_ylim, target_ylim)
            self.needs_full_draw = True

        if self.needs_full_draw or self.background is None:
            self.canvas.draw()
            self.background = self.canvas.copy_from_bbox(self.ax.bbox)
            self.needs_full_draw = False

        self.line1.set_data(t_plot, x1_plot)
        self.line2.set_data(t_plot, x2_plot)
        self.line3.set_data(t_plot, x3_plot)

        self.canvas.restore_region(self.background)
        self.ax.draw_artist(self.line1)
        self.ax.draw_artist(self.line2)
        self.ax.draw_artist(self.line3)
        self.canvas.blit(self.ax.bbox)

    def closeEvent(self, event):
        self.plot_timer.stop()
        if hasattr(self, 'sim_thread') and self.sim_thread.isRunning():
            self.sim_thread.stop()
        if hasattr(self, 'writer_thread') and self.writer_thread.isRunning():
            self.writer_thread.stop()
        super().closeEvent(event)

# --- Ejecución de la App ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoupledMainWindow()
    window.show()
    sys.exit(app.exec())
