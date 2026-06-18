import sys
import json
import csv
import os
import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel,
                             QDialog, QLineEdit, QFileDialog, QFormLayout, QMessageBox,
                             QCheckBox)
from PyQt6.QtCore import QTimer, Qt
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

        # Botones de acción
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

        # Botones de acción
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

# --- Ventana Principal de la Interfaz ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Oscilador Armónico Amortiguado (Optimizado)")
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

        # Parámetros físicos dinámicos (valores iniciales para los sliders)
        self.m = self.constants.get("m", 1.0)
        self.b = self.constants.get("b", 0.2)
        self.k = self.constants.get("k", 5.0)

        # Variables de estado de la simulación
        self.t = 0.0
        self.x = self.config["x0"]
        self.v = self.config["v0"]

        # Vectores para almacenar datos del gráfico
        self.t_data = []
        self.x_data = []

        # Configuración del Timer para la simulación en tiempo real
        self.timer = QTimer()
        self.timer.timeout.connect(self.simulation_step)

        self.init_ui()
        self.update_ui_from_parameters()
        self.reset_simulation()

    def init_ui(self):
        # Contenedor principal
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
        
        # Línea de trazado persistente (en lugar de recrearla con plot en cada iteración)
        self.line, = self.ax.plot([], [], label="Posición (x)", color="blue", lw=2)
        self.ax.legend(loc="upper right")
        
        main_layout.addWidget(self.canvas, stretch=3)

        # --- Panel Derecho: Controles ---
        control_layout = QVBoxLayout()

        # Sliders y etiquetas
        self.lbl_m = QLabel(f"Masa (m): {self.m:.2f} kg")
        self.slider_m = QSlider(Qt.Orientation.Horizontal)
        self.slider_m.setRange(1, 100)  # Mapea a 0.1 - 10.0
        self.slider_m.setValue(int(self.m * 10))
        self.slider_m.valueChanged.connect(self.update_parameters)

        self.lbl_b = QLabel(f"Amortiguamiento (b): {self.b:.2f}")
        self.slider_b = QSlider(Qt.Orientation.Horizontal)
        self.slider_b.setRange(0, 100)  # Mapea a 0.0 - 5.0
        self.slider_b.setValue(int(self.b * 20))
        self.slider_b.valueChanged.connect(self.update_parameters)

        self.lbl_k = QLabel(f"Constante Elástica (k): {self.k:.2f} N/m")
        self.slider_k = QSlider(Qt.Orientation.Horizontal)
        self.slider_k.setRange(1, 200)  # Mapea a 0.1 - 20.0
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

    def update_ui_from_parameters(self):
        # Bloquear señales para evitar bucles de actualización y redondeos
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
                self.reset_simulation()
            else:
                # Si se cancela el guardado, aun así aplicamos los cambios en memoria
                self.config = new_config
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
                self.update_ui_from_parameters()
                self.reset_simulation()
            else:
                # Si se cancela el guardado, aun así aplicamos los cambios en memoria
                self.constants = new_constants
                self.m = self.constants.get("m", 1.0)
                self.b = self.constants.get("b", 0.2)
                self.k = self.constants.get("k", 5.0)
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
                if not silent:
                    QMessageBox.information(self, "Éxito", "Configuración cargada correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo de configuración: {e}")
        else:
            # Si el archivo por defecto no existe, lo creamos con los valores iniciales
            self.save_config_to_file(filename)

    def load_constants_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.constants = json.load(f)
                if not silent:
                    QMessageBox.information(self, "Éxito", "Constantes cargadas correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo de constantes: {e}")
        else:
            # Si el archivo por defecto no existe, lo creamos con los valores iniciales
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

    # --- Lógica de la Simulación Física ---
    def start_simulation(self):
        # Si el CSV no existe, crearlo con cabeceras
        if not os.path.exists(self.csv_filename) or self.t == 0.0:
            try:
                with open(self.csv_filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Tiempo (s)", "Posicion (x)", "Velocidad (v)", "m", "b", "k"])
            except PermissionError:
                QMessageBox.warning(self, "Error de archivo", "No se pudo escribir en el CSV. Asegúrese de que no esté abierto en otra aplicación.")
                return

        # Intervalo del QTimer en milisegundos (sincronizado con el dt de la simulación)
        interval = int(self.config["dt"] * 1000)
        self.timer.start(max(1, interval))

    def pause_simulation(self):
        self.timer.stop()

    def reset_simulation(self):
        self.timer.stop()
        self.t = 0.0
        self.x = self.config["x0"]
        self.v = self.config["v0"]
        self.t_data.clear()
        self.x_data.clear()

        # Limpiar datos de la línea en lugar de limpiar todo el gráfico
        self.line.set_data([], [])
        
        # Establecer límites del gráfico de forma limpia
        self.ax.set_xlim(0, 10)
        
        # Definir rango dinámico inicial para el eje Y basado en x0
        self.adjust_y_limits()
        
        self.canvas.draw()

    def adjust_y_limits(self):
        if not self.x_data:
            margin = max(2.0, abs(self.x) * 0.5)
            self.ax.set_ylim(self.x - margin, self.x + margin)
        else:
            hist_min = min(self.x_data)
            hist_max = max(self.x_data)
            margin = max(1.0, (hist_max - hist_min) * 0.1)
            self.ax.set_ylim(hist_min - margin, hist_max + margin)

    def update_y_scale(self):
        if self.chk_log_scale.isChecked():
            # Symmetrical log scale to handle negative, zero, and positive values elegantly
            self.ax.set_yscale('symlog', linthresh=0.1)
        else:
            self.ax.set_yscale('linear')
        
        self.adjust_y_limits()
        self.canvas.draw()

    def check_dt_for_force(self):
        if self.chk_ext_force.isChecked() and self.config["dt"] >= 0.005:
            QMessageBox.warning(
                self,
                "Advertencia de Estabilidad Numérica",
                f"La fuerza externa tiene una frecuencia de 60 Hz (período ~0.017 s).\n"
                f"El paso de tiempo actual (Δt = {self.config['dt']} s) es demasiado grande.\n\n"
                f"Para evitar errores numéricos o inestabilidad, se recomienda configurar "
                f"Δt en un valor menor o igual a 0.001 s en 'Condiciones Iniciales...'."
            )

    def simulation_step(self):
        dt = self.config["dt"]

        # Algoritmo de integración numérica (Euler-Cromer) con opción de fuerza externa
        F_ext = 0.0
        if self.chk_ext_force.isChecked():
            # Fuerza armónica externa de 60 Hz y amplitud máxima 1 N
            # F(t) = 1.0 * sin(2 * pi * f * t)
            F_ext = 1.0 * math.sin(2.0 * math.pi * 60.0 * self.t)

        a = (-self.b * self.v - self.k * self.x + F_ext) / self.m
        self.v += a * dt
        self.x += self.v * dt
        self.t += dt

        # Guardar en memoria para el gráfico
        self.t_data.append(self.t)
        self.x_data.append(self.x)

        # Guardar en tiempo real en el archivo CSV (protegido contra PermissionError)
        try:
            with open(self.csv_filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([round(self.t, 3), round(self.x, 4), round(self.v, 4), self.m, self.b, self.k])
        except PermissionError:
            # Se ignora silenciosamente si el archivo está abierto (evita colapsar el programa)
            pass

        # Actualizar datos del gráfico de manera eficiente (sin borrar los ejes)
        self.line.set_data(self.t_data, self.x_data)

        # Ajuste dinámico del eje X si excede la vista actual
        x_limit_curr = self.ax.get_xlim()[1]
        if self.t > x_limit_curr:
            self.ax.set_xlim(0, self.t + 5)

        # Ajuste dinámico del eje Y si la amplitud excede los límites visibles
        y_min, y_max = self.ax.get_ylim()
        if self.x > y_max or self.x < y_min:
            self.adjust_y_limits()

        self.canvas.draw()

# --- Ejecución de la App ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
