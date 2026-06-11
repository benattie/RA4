import sys
import json
import csv
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                QHBoxLayout, QPushButton, QSlider, QLabel,
                                QDialog, QLineEdit, QFileDialog, QFormLayout, QMessageBox)
from PyQt6.QtCore import QTimer, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- Ventana Auxiliar (Condiciones Iniciales) ---
class ConfigDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Condiciones Iniciales")
        self.resize(300, 150)

        self.config = current_config or {"x0": 1.0, "v0": 0.0, "dt": 0.05}

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

# --- Ventana Principal de la Interfaz ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Oscilador Armónico Amortiguado")
        self.resize(800, 600)

        # Valores por defecto de simulación
        self.config = {"x0": 5.0, "v0": 0.0, "dt": 0.02}
        self.config_filename = "config_inicial.json"
        self.csv_filename = "simulacion_oscilador.csv"

        # Cargar configuración si existe
        self.load_config_from_file(self.config_filename, silent=True)

        # Parámetros físicos dinámicos (valores iniciales para los sliders)
        self.m = 1.0   # Masa
        self.b = 0.2   # Constante de amortiguamiento
        self.k = 5.0   # Constante del resorte

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
        self.reset_simulation()

    def init_ui(self):
        # Contenedor principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- Panel Izquierdo: Gráfico ---
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Posición (x)")
        self.ax.grid(True)
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

        control_layout.addSpacing(20)

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

        control_layout.addSpacing(20)

        # Botones de Configuración externa
        self.btn_config_init = QPushButton("Condiciones Iniciales...")
        self.btn_config_init.clicked.connect(self.open_config_dialog)

        self.btn_load_file = QPushButton("Cargar Config. desde Archivo")
        self.btn_load_file.clicked.connect(self.manual_load_config)

        control_layout.addWidget(self.btn_config_init)
        control_layout.addWidget(self.btn_load_file)

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

    def open_config_dialog(self):
        dialog = ConfigDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_values()
            self.save_config_to_file(self.config_filename)
            self.reset_simulation()

    def save_config_to_file(self, filename):
        try:
            with open(filename, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la configuración: {e}")

    def load_config_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.config = json.load(f)
                if not silent:
                    QMessageBox.information(self, "Éxito", "Configuración cargada correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo: {e}")

    def manual_load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Cargar Configuración", "", "JSON Files (*.json)")
        if filename:
            self.load_config_from_file(filename)
            self.reset_simulation()

    # --- Lógica de la Simulación Física ---
    def start_simulation(self):
        # Si el CSV no existe, crearlo con cabeceras
        if not os.path.exists(self.csv_filename) or self.t == 0.0:
            with open(self.csv_filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Tiempo (s)", "Posicion (x)", "Velocidad (v)", "m", "b", "k"])

        # Intervalo del QTimer en milisegundos (aproximado al dt de la simulación)
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

        # Limpiar gráfico
        self.ax.clear()
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Posición (x)")
        self.ax.grid(True)
        self.canvas.draw()

    def simulation_step(self):
        dt = self.config["dt"]

        # Algoritmo de integración numérica (Euler-Cromer)
        # Ecuación diferencial: m*a + b*v + k*x = 0  ->  a = (-b*v - k*x) / m
        a = (-self.b * self.v - self.k * self.x) / self.m
        self.v += a * dt
        self.x += self.v * dt
        self.t += dt

        # Guardar en memoria para el gráfico
        self.t_data.append(self.t)
        self.x_data.append(self.x)

        # Guardar en tiempo real en el archivo CSV
        try:
            with open(self.csv_filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([self.t, self.x, self.v, self.m, self.b, self.k])
        except PermissionError:
            # Por si el usuario tiene el CSV abierto en Excel mientras corre la simulación
            pass

        # Actualizar gráfico de forma eficiente
        self.ax.clear()
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Posición (x)")
        self.ax.grid(True)
        self.ax.plot(self.t_data, self.x_data, label="Posición (x)", color="blue")
        self.ax.legend(loc="upper right")
        self.canvas.draw()

# --- Ejecución de la App ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
