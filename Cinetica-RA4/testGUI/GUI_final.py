import sys
import json
import csv
import os
import math
import time
import queue
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel,
                             QDialog, QLineEdit, QFileDialog, QFormLayout, QMessageBox,
                             QCheckBox)
from PyQt6.QtCore import QThread, QTimer, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- Ventana Auxiliar (Condiciones Iniciales) ---
class ConfigDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Condiciones Iniciales")
        self.resize(300, 150)

        self.config = current_config or {"x0": 5.0, "v0": 0.0, "dt": 0.05}

        layout = QFormLayout(self)

        self.input_x0 = QLineEdit(str(self.config["x0"]))
        self.input_v0 = QLineEdit(str(self.config["v0"]))
        self.input_dt = QLineEdit(str(self.config["dt"]))

        layout.addRow("Posición inicial (x₀):", self.input_x0)
        layout.addRow("Velocidad inicial (v₀):", self.input_v0)
        layout.addRow("Paso de tiempo (Δt):", self.input_dt)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Aplicar")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        layout.addRow(btn_layout)

    def get_values(self):
        try:
            return {
                "x0": float(self.input_x0.text()),
                "v0": float(self.input_v0.text()),
                "dt": float(self.input_dt.text())
            }
        except ValueError:
            QMessageBox.critical(self, "Error", "Por favor ingresa valores numéricos válidos.")
            return self.config

# --- Ventana Auxiliar (Constantes del Sistema) ---
class ConstantsDialog(QDialog):
    def __init__(self, parent=None, current_constants=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Constantes del Sistema")
        self.resize(300, 150)

        self.constants = current_constants or {"m": 1.0, "b": 0.2, "k": 5.0}

        layout = QFormLayout(self)

        self.input_m = QLineEdit(str(self.constants["m"]))
        self.input_b = QLineEdit(str(self.constants["b"]))
        self.input_k = QLineEdit(str(self.constants["k"]))

        layout.addRow("Masa (m):", self.input_m)
        layout.addRow("Amortiguamiento (b):", self.input_b)
        layout.addRow("Constante elástica (k):", self.input_k)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Aplicar")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        layout.addRow(btn_layout)

    def get_values(self):
        try:
            return {
                "m": float(self.input_m.text()),
                "b": float(self.input_b.text()),
                "k": float(self.input_k.text())
            }
        except ValueError:
            QMessageBox.critical(self, "Error", "Por favor ingresa valores numéricos válidos.")
            return self.constants

# --- Hilo Desacoplado: Escritura en Disco por Bloques y Lotes ---
class DiskWriterThread(QThread):
    def __init__(self, filename="simulacion_oscilador.csv", block_size=500, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.block_size = block_size
        self.queue = queue.Queue()
        self._running = True

    def run(self):
        buffer = []
        while self._running or not self.queue.empty():
            try:
                # Esperar lote o muestra individual con tiempo limite
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

# --- Hilo Desacoplado: Simulación Física en Tiempo Real (Con Acumulador Temporal) ---
class SimulationThread(QThread):
    def __init__(self, writer_queue, config, constants, parent=None):
        super().__init__(parent)
        self.writer_queue = writer_queue
        self.lock = threading.Lock()

        # Parámetros físicos
        self.m = constants.get("m", 1.0)
        self.b = constants.get("b", 0.2)
        self.k = constants.get("k", 5.0)
        self.dt = config.get("dt", 0.05)
        self.ext_force = False

        # Estado de la simulación
        self.t = 0.0
        self.x = config.get("x0", 5.0)
        self.v = config.get("v0", 0.0)

        # Buffers de datos para el gráfico
        self.t_data = []
        self.x_data = []

        self._running = False

    def update_params(self, m, b, k):
        with self.lock:
            self.m = m
            self.b = b
            self.k = k

    def set_ext_force(self, enabled):
        with self.lock:
            self.ext_force = enabled

    def set_config(self, config):
        with self.lock:
            self.dt = config.get("dt", 0.05)

    def reset_state(self, x0, v0):
        with self.lock:
            self.t = 0.0
            self.x = x0
            self.v = v0
            self.t_data.clear()
            self.x_data.clear()

    def get_plot_data(self):
        with self.lock:
            return list(self.t_data), list(self.x_data), self.t, self.x

    def run(self):
        self._running = True
        last_time = time.perf_counter()
        accumulator = 0.0

        while self._running:
            now = time.perf_counter()
            elapsed = now - last_time
            last_time = now

            # Evitar desbordamiento ("spiral of death") ante pausas del SO
            if elapsed > 0.2:
                elapsed = 0.2

            accumulator += elapsed

            with self.lock:
                m, b, k = self.m, self.b, self.k
                dt = self.dt
                ext_force = self.ext_force
                x, v, t = self.x, self.v, self.t

            batch_samples = []
            steps = 0
            max_steps_per_cycle = 2000

            # Sub-stepping en tiempo real: avanzar la simulación en sincronía exacta 1:1 con el reloj real
            while accumulator >= dt and steps < max_steps_per_cycle:
                F_ext = 0.0
                if ext_force:
                    F_ext = 1.0 * math.sin(2.0 * math.pi * 60.0 * t)

                a = (-b * v - k * x + F_ext) / m
                v += a * dt
                x += v * dt
                t += dt

                accumulator -= dt
                steps += 1

                # Guardar el 100% de las muestras para la escritura en disco
                batch_samples.append([round(t, 6), round(x, 6), round(v, 6), m, b, k])

            if steps > 0:
                with self.lock:
                    self.x = x
                    self.v = v
                    self.t = t
                    for sample in batch_samples:
                        self.t_data.append(sample[0])
                        self.x_data.append(sample[1])

                self.writer_queue.put(batch_samples)

            # Pequeño ceder de CPU
            time.sleep(0.001)

    def stop(self):
        self._running = False
        self.wait()

# --- Ventana Principal de la Interfaz ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Oscilador Armónico Amortiguado (Tiempo Real + 60 FPS)")
        self.resize(950, 650)

        # Valores por defecto de simulación
        self.config = {"x0": 5.0, "v0": 0.0, "dt": 0.05}
        self.constants = {"m": 1.0, "b": 0.2, "k": 5.0}
        self.config_filename = "config_inicial.json"
        self.constants_filename = "config_constantes.json"
        self.csv_filename = "simulacion_oscilador.csv"

        # Cargar configuración si existe
        self.load_config_from_file(self.config_filename, silent=True)
        self.load_constants_from_file(self.constants_filename, silent=True)

        # Parámetros físicos dinámicos
        self.m = self.constants.get("m", 1.0)
        self.b = self.constants.get("b", 0.2)
        self.k = self.constants.get("k", 5.0)

        # Crear hilo de escritura en disco
        self.writer_thread = DiskWriterThread(filename=self.csv_filename, block_size=500, parent=self)

        # Crear hilo de simulación física en tiempo real
        self.sim_thread = SimulationThread(self.writer_thread.queue, self.config, self.constants, parent=self)

        # Temporizador para la actualización de la gráfica a 60 FPS (16 ms)
        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(16)
        self.plot_timer.timeout.connect(self.update_plot_60fps)

        self.init_ui()
        self.update_ui_from_parameters()
        self.reset_simulation()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- Panel Izquierdo: Gráfico ---
        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Posición (x)")
        self.ax.grid(True)

        self.line, = self.ax.plot([], [], label="Posición (x)", color="blue", lw=2)
        self.ax.legend(loc="upper right")

        main_layout.addWidget(self.canvas, stretch=3)

        # --- Panel Derecho: Controles ---
        control_layout = QVBoxLayout()

        # Sliders y etiquetas
        self.lbl_m = QLabel(f"Masa (m): {self.m:.2f} kg")
        self.slider_m = QSlider(Qt.Orientation.Horizontal)
        self.slider_m.setRange(1, 100)
        self.slider_m.setValue(int(self.m * 10))
        self.slider_m.valueChanged.connect(self.update_parameters)

        self.lbl_b = QLabel(f"Amortiguamiento (b): {self.b:.2f}")
        self.slider_b = QSlider(Qt.Orientation.Horizontal)
        self.slider_b.setRange(0, 100)
        self.slider_b.setValue(int(self.b * 20))
        self.slider_b.valueChanged.connect(self.update_parameters)

        self.lbl_k = QLabel(f"Constante Elástica (k): {self.k:.2f} N/m")
        self.slider_k = QSlider(Qt.Orientation.Horizontal)
        self.slider_k.setRange(1, 200)
        self.slider_k.setValue(int(self.k * 10))
        self.slider_k.valueChanged.connect(self.update_parameters)

        control_layout.addWidget(self.lbl_m)
        control_layout.addWidget(self.slider_m)
        control_layout.addWidget(self.lbl_b)
        control_layout.addWidget(self.slider_b)
        control_layout.addWidget(self.lbl_k)
        control_layout.addWidget(self.slider_k)

        control_layout.addSpacing(15)

        # Botones Principales de Simulación
        self.btn_start = QPushButton("Iniciar")
        self.btn_start.clicked.connect(self.start_simulation)

        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.clicked.connect(self.pause_simulation)

        self.btn_reset = QPushButton("Reiniciar")
        self.btn_reset.clicked.connect(self.reset_simulation)

        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_reset)

        control_layout.addSpacing(15)

        # Botones de Configuración externa (Condiciones Iniciales)
        self.btn_config_init = QPushButton("Condiciones Iniciales...")
        self.btn_config_init.clicked.connect(self.open_config_dialog)

        self.btn_load_file = QPushButton("Cargar Config. desde Archivo")
        self.btn_load_file.clicked.connect(self.manual_load_config)

        control_layout.addWidget(self.btn_config_init)
        control_layout.addWidget(self.btn_load_file)

        control_layout.addSpacing(10)

        # Botones de Configuración externa (Constantes del Sistema)
        self.btn_config_const = QPushButton("Constantes del Sistema...")
        self.btn_config_const.clicked.connect(self.open_constants_dialog)

        self.btn_load_const_file = QPushButton("Cargar Const. desde Archivo")
        self.btn_load_const_file.clicked.connect(self.manual_load_constants)

        control_layout.addWidget(self.btn_config_const)
        control_layout.addWidget(self.btn_load_const_file)

        control_layout.addSpacing(15)

        # Opciones de simulación y visualización (Checkboxes)
        self.chk_log_scale = QCheckBox("Escala Logarítmica (Eje Y)")
        self.chk_log_scale.stateChanged.connect(self.update_y_scale)
        control_layout.addWidget(self.chk_log_scale)

        self.chk_ext_force = QCheckBox("Fuerza Externa (60 Hz, 1 N)")
        self.chk_ext_force.stateChanged.connect(self.check_dt_for_force)
        control_layout.addWidget(self.chk_ext_force)

        control_layout.addStretch()
        main_layout.addLayout(control_layout, stretch=1)

    # --- Lógica de Parámetros y Archivos ---
    def update_parameters(self):
        self.m = self.slider_m.value() / 10.0
        self.b = self.slider_b.value() / 20.0
        self.k = self.slider_k.value() / 10.0

        self.lbl_m.setText(f"Masa (m): {self.m:.2f} kg")
        self.lbl_b.setText(f"Amortiguamiento (b): {self.b:.2f}")
        self.lbl_k.setText(f"Constante Elástica (k): {self.k:.2f} N/m")

        self.constants["m"] = self.m
        self.constants["b"] = self.b
        self.constants["k"] = self.k

        if hasattr(self, 'sim_thread'):
            self.sim_thread.update_params(self.m, self.b, self.k)

    def update_ui_from_parameters(self):
        self.slider_m.blockSignals(True)
        self.slider_b.blockSignals(True)
        self.slider_k.blockSignals(True)

        val_m = int(self.m * 10)
        if val_m > self.slider_m.maximum():
            self.slider_m.setMaximum(val_m)
        if val_m < self.slider_m.minimum():
            self.slider_m.setMinimum(val_m)
        self.slider_m.setValue(val_m)

        val_b = int(self.b * 20)
        if val_b > self.slider_b.maximum():
            self.slider_b.setMaximum(val_b)
        if val_b < self.slider_b.minimum():
            self.slider_b.setMinimum(val_b)
        self.slider_b.setValue(val_b)

        val_k = int(self.k * 10)
        if val_k > self.slider_k.maximum():
            self.slider_k.setMaximum(val_k)
        if val_k < self.slider_k.minimum():
            self.slider_k.setMinimum(val_k)
        self.slider_k.setValue(val_k)

        self.slider_m.blockSignals(False)
        self.slider_b.blockSignals(False)
        self.slider_k.blockSignals(False)

        self.lbl_m.setText(f"Masa (m): {self.m:.2f} kg")
        self.lbl_b.setText(f"Amortiguamiento (b): {self.b:.2f}")
        self.lbl_k.setText(f"Constante Elástica (k): {self.k:.2f} N/m")

    def open_config_dialog(self):
        dialog = ConfigDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_values()
            filename, _ = QFileDialog.getSaveFileName(self, "Guardar Condiciones Iniciales como...", "", "JSON Files (*.json)")
            if filename:
                self.config = new_config
                self.save_config_to_file(filename)
            else:
                self.config = new_config
            self.sim_thread.set_config(self.config)
            self.reset_simulation()

    def open_constants_dialog(self):
        dialog = ConstantsDialog(self, self.constants)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_constants = dialog.get_values()
            filename, _ = QFileDialog.getSaveFileName(self, "Guardar Constantes del Sistema como...", "", "JSON Files (*.json)")
            if filename:
                self.constants = new_constants
                self.m = self.constants.get("m", 1.0)
                self.b = self.constants.get("b", 0.2)
                self.k = self.constants.get("k", 5.0)
                self.save_constants_to_file(filename)
            else:
                self.constants = new_constants
                self.m = self.constants.get("m", 1.0)
                self.b = self.constants.get("b", 0.2)
                self.k = self.constants.get("k", 5.0)
            self.sim_thread.update_params(self.m, self.b, self.k)
            self.update_ui_from_parameters()
            self.reset_simulation()

    def save_config_to_file(self, filename):
        try:
            with open(filename, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la configuración: {e}")

    def save_constants_to_file(self, filename):
        try:
            with open(filename, 'w') as f:
                json.dump(self.constants, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar las constantes: {e}")

    def load_config_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.config = json.load(f)
                if hasattr(self, 'sim_thread'):
                    self.sim_thread.set_config(self.config)
                if not silent:
                    QMessageBox.information(self, "Éxito", "Configuración cargada correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo de configuración: {e}")
        else:
            self.save_config_to_file(filename)

    def load_constants_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.constants = json.load(f)
                if hasattr(self, 'sim_thread'):
                    self.sim_thread.update_params(
                        self.constants.get("m", 1.0),
                        self.constants.get("b", 0.2),
                        self.constants.get("k", 5.0)
                    )
                if not silent:
                    QMessageBox.information(self, "Éxito", "Constantes cargadas correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo de constantes: {e}")
        else:
            self.save_constants_to_file(filename)

    def manual_load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Cargar Configuración", "", "JSON Files (*.json)")
        if filename:
            self.load_config_from_file(filename)
            self.reset_simulation()

    def manual_load_constants(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Cargar Constantes del Sistema", "", "JSON Files (*.json)")
        if filename:
            self.load_constants_from_file(filename)
            self.m = self.constants.get("m", 1.0)
            self.b = self.constants.get("b", 0.2)
            self.k = self.constants.get("k", 5.0)
            self.update_ui_from_parameters()
            self.reset_simulation()

    # --- Lógica de la Simulación Física y Visualización ---
    def start_simulation(self):
        t_data, _, _, _ = self.sim_thread.get_plot_data()
        if not os.path.exists(self.csv_filename) or len(t_data) == 0:
            try:
                with open(self.csv_filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Tiempo (s)", "Posicion (x)", "Velocidad (v)", "m", "b", "k"])
            except PermissionError:
                QMessageBox.warning(self, "Error de archivo", "No se pudo escribir en el CSV. Asegúrese de que no esté abierto en otra aplicación.")
                return

        if not self.writer_thread.isRunning():
            self.writer_thread.start()

        if not self.sim_thread.isRunning():
            self.sim_thread.start()

        self.plot_timer.start(16)  # 16 ms => ~60 FPS

    def pause_simulation(self):
        self.plot_timer.stop()
        if self.sim_thread.isRunning():
            self.sim_thread.stop()

    def reset_simulation(self):
        self.pause_simulation()
        self.sim_thread.reset_state(self.config["x0"], self.config["v0"])

        self.line.set_data([], [])
        self.ax.set_xlim(0, 10)
        self.adjust_y_limits_from_data([])
        self.canvas.draw()

    def adjust_y_limits_from_data(self, x_data):
        if not x_data:
            margin = max(2.0, abs(self.config["x0"]) * 0.5)
            self.ax.set_ylim(self.config["x0"] - margin, self.config["x0"] + margin)
        else:
            hist_min = min(x_data)
            hist_max = max(x_data)
            margin = max(1.0, (hist_max - hist_min) * 0.1)
            self.ax.set_ylim(hist_min - margin, hist_max + margin)

    def update_y_scale(self):
        if self.chk_log_scale.isChecked():
            self.ax.set_yscale('symlog', linthresh=0.1)
        else:
            self.ax.set_yscale('linear')

        _, x_data, _, _ = self.sim_thread.get_plot_data()
        self.adjust_y_limits_from_data(x_data)
        self.canvas.draw()

    def check_dt_for_force(self):
        is_checked = self.chk_ext_force.isChecked()
        if hasattr(self, 'sim_thread'):
            self.sim_thread.set_ext_force(is_checked)

        if is_checked and self.config["dt"] >= 0.005:
            QMessageBox.warning(
                self,
                "Advertencia de Estabilidad Numérica",
                f"La fuerza externa tiene una frecuencia de 60 Hz (período ~0.017 s).\n"
                f"El paso de tiempo actual (Δt = {self.config['dt']} s) es demasiado grande.\n\n"
                f"Para evitar errores numéricos o inestabilidad, se recomienda configurar "
                f"Δt en un valor menor o igual a 0.001 s en 'Condiciones Iniciales...'."
            )

    def update_plot_60fps(self):
        t_data, x_data, current_t, current_x = self.sim_thread.get_plot_data()
        if not t_data:
            return

        # Decimación inteligente para mantener la fluidez de Matplotlib a 60 FPS
        if len(t_data) > 4000:
            step = len(t_data) // 2000
            t_plot = t_data[::step]
            x_plot = x_data[::step]
        else:
            t_plot = t_data
            x_plot = x_data

        self.line.set_data(t_plot, x_plot)

        # Ajuste dinámico del eje X si excede la vista actual
        x_limit_curr = self.ax.get_xlim()[1]
        if current_t > x_limit_curr:
            self.ax.set_xlim(0, current_t + 5)

        # Ajuste dinámico del eje Y si la amplitud excede los límites visibles
        y_min, y_max = self.ax.get_ylim()
        if current_x > y_max or current_x < y_min:
            self.adjust_y_limits_from_data(x_plot)

        self.canvas.draw_idle()

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
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
