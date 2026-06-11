#modulos para la simulacion
import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

from Simulador_RA4_funciones import obtener_reactividad, cinetica_puntual

# modulos para la interfaz gráfica
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

from Simulador_RA4_ventanas_auxiliares import ConfigPFDialog, ConfigCIDialog


# --- Ventana Principal de la Interfaz ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de tablero de operaciones y funcionamiento del RA4")
        self.resize(950, 600)

        # Valores por defecto de simulación
        self.config_cond_iniciales_filename = "01_input_condiciones_iniciales_default.json"
        self.config_cond_iniciales = self.load_config_from_file(self.config_cond_iniciales_filename, silent=True)

        self.config_param_fisicos_filename = "00_input_cinetica_RA4_default.json"
        self.config_param_fisicos = self.load_config_from_file(self.config_param_fisicos_filename, silent=True)

        self.csv_filename = "simulacion_RA4.csv"

        # Parámetros físicos dinámicos. Posición del nucleo y de las barras de control (valores iniciales para los sliders)
        self.pos_nuc = 0.0   # nucleo
        self.pos_BC1 = 0.0   # barra de control 1
        self.pos_BC2 = 0.0   # barra de control 2

        # Parámetros físicos estáticos. Beta efectivo del reactor, tiempo de decaimiento de los neutrones prompt, y de los 6 grupos de reactores retardados
        self.beta_eff = self.config_param_fisicos["parámetros físicos RA4"]["Beta efectivo"]
        self.LAMBDA = self.config_param_fisicos["parámetros físicos RA4"]["Lambda [s]"]
        self.lambda_i = np.array(self.config_param_fisicos["parámetros físicos RA4"]["lambda_i [s]"])
        self.fracciones_i = np.array(self.config_param_fisicos["parámetros físicos RA4"]["fracciones_i"])

        # Variables de estado de la simulación (valores iniciales)
        self.t = 0.0
        self.n = self.config_cond_iniciales["condiciones iniciales"]["flujo de neutrones"]
        self.Ci = np.array(self.config_cond_iniciales["condiciones iniciales"]["concentración grupo neutrones retardados"])

        self.y_actual = np.concatenate(([self.n], self.Ci))

        # Vectores para almacenar datos del gráfico
        self.t_data = []
        self.n_data = []

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
        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Flujo de neutrones (n)")
        self.ax.grid(True)
        
        # Línea de trazado persistente (en lugar de recrearla con plot en cada iteración)
        self.line, = self.ax.plot([], [], label="Flujo de neutrones (n)", color="blue", lw=2)
        self.ax.legend(loc="upper right")
        
        main_layout.addWidget(self.canvas, stretch=3)

        # --- Panel Derecho: Controles ---
        control_layout = QVBoxLayout()

        # Sliders y etiquetas
        self.lbl_pos_nuc = QLabel(f"Posición del núcleo (%): {self.pos_nuc:.2f} %")
        self.slider_pos_nuc = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_nuc.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_nuc.setValue(int(self.pos_nuc))
        self.slider_pos_nuc.valueChanged.connect(self.update_parameters)

        self.lbl_pos_BC1 = QLabel(f"Posición de la barra de control 1 (BC1): {self.pos_BC1:.2f} %")
        self.slider_pos_BC1 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_BC1.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_BC1.setValue(int(self.pos_BC1))
        self.slider_pos_BC1.valueChanged.connect(self.update_parameters)

        self.lbl_pos_BC2 = QLabel(f"Posición de la barra de control 2 (BC2): {self.pos_BC2:.2f} %")
        self.slider_pos_BC2 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_BC2.setRange(0, 100)  # Mapea a 0 - 100.0
        self.slider_pos_BC2.setValue(int(self.pos_BC2))
        self.slider_pos_BC2.valueChanged.connect(self.update_parameters)

        control_layout.addWidget(self.lbl_pos_nuc)
        control_layout.addWidget(self.slider_pos_nuc)
        control_layout.addWidget(self.lbl_pos_BC1)
        control_layout.addWidget(self.slider_pos_BC1)
        control_layout.addWidget(self.lbl_pos_BC2)
        control_layout.addWidget(self.slider_pos_BC2)

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

        self.btn_load_init_file = QPushButton("Cargar conf. de cond. iniciales desde archivo")
        self.btn_load_init_file.clicked.connect(self.manual_load_config)

        self.btn_config_input_cinetica = QPushButton("Parámetros físicos de la cinética...")
        self.btn_config_input_cinetica.clicked.connect(self.open_config_dialog_parametros_cinetica)

        self.btn_load_input_cinetica_file = QPushButton("Cargar config. de parámetros físicos desde archivo")
        self.btn_load_input_cinetica_file.clicked.connect(self.manual_load_config)

        control_layout.addWidget(self.btn_config_init)
        control_layout.addWidget(self.btn_load_init_file)
        control_layout.addWidget(self.btn_config_input_cinetica)
        control_layout.addWidget(self.btn_load_input_cinetica_file)

        control_layout.addStretch()
        main_layout.addLayout(control_layout, stretch=1)

    # --- Lógica de Parámetros y Archivos ---
    def update_parameters(self):
        self.pos_nuc = self.slider_pos_nuc.value()
        self.pos_BC1 = self.slider_pos_BC1.value()
        self.pos_BC2 = self.slider_pos_BC2.value()

        self.lbl_pos_nuc.setText(f"Pos. del núcleo (%): {self.pos_nuc:.2f} %")
        self.lbl_pos_BC1.setText(f"Pos. de la barra de control 1 (BC1): {self.pos_BC1:.2f} %")
        self.lbl_pos_BC2.setText(f"Pos. de la barra de control 2 (BC2): {self.pos_BC2:.2f} %")

    def open_config_dialog(self):
        dialog = ConfigCIDialog(self, self.config_cond_iniciales)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config_cond_iniciales = dialog.get_values()
            self.save_config_to_file(self.config_cond_iniciales_filename)
            self.reset_simulation()

    def open_config_dialog_parametros_cinetica(self):
        dialog_2 = ConfigPFDialog(self, self.config_param_fisicos)
        if dialog_2.exec() == QDialog.DialogCode.Accepted:
            self.config_param_fisicos = dialog_2.get_values()
            self.save_config_to_file(self.config_param_fisicos_filename)
            self.reset_simulation()

    def save_config_to_file(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la configuración: {e}")

    def load_config_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                    return self.config
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
            try:
                with open(self.csv_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Tiempo (s)", "Flujo de neutrones (n)", "pos_nuc (%)", "pos_BC1 (%)", "pos_BC2 (%)"])
            except PermissionError:
                QMessageBox.warning(self, "Error de archivo", "No se pudo escribir en el CSV. Asegúrese de que no esté abierto en otra aplicación.")
                return

        # Intervalo del QTimer en milisegundos (sincronizado con el dt de la simulación)
        interval = int(self.config_cond_iniciales["condiciones iniciales"]["paso temporal"] * 1000)
        self.timer.start(max(1, interval))

    def pause_simulation(self):
        self.timer.stop()

    def reset_simulation(self):
        self.timer.stop()
        self.t = 0.0
        self.n = self.config_cond_iniciales["condiciones iniciales"]["flujo de neutrones"]
        self.Ci = np.array(self.config_cond_iniciales["condiciones iniciales"]["concentración grupo neutrones retardados"])
        self.t_data.clear()
        self.n_data.clear()

        # Limpiar datos de la línea en lugar de limpiar todo el gráfico
        self.line.set_data([], [])
        
        # Establecer límites del gráfico de forma limpia
        self.ax.set_xlim(0, 10)
        
        # Definir rango dinámico inicial para el eje Y basado en x0
        margin = max(2.0, abs(self.n) * 0.5)
        self.ax.set_ylim(self.n - margin, self.n + margin)
        
        self.canvas.draw()

    def simulation_step(self):
        dt = self.config_cond_iniciales["condiciones iniciales"]["paso temporal"]
        t_siguiente = self.t + dt

        # Resolver el paso utilizando el método rígido Radau
        solucion = solve_ivp(
            cinetica_puntual,
            [self.t, t_siguiente],
            self.y_actual,
            method='Radau',
            args=(self.beta_eff, self.LAMBDA, self.lambda_i, self.fracciones_i, self.pos_nuc, self.pos_BC1, self.pos_BC2),
            rtol=1e-6
        )

        # Actualizar variables de estado con el último punto calculado
        self.t = solucion.t[-1]
        self.y_actual = [solucion.y[0][-1], solucion.y[1][-1], solucion.y[2][-1], solucion.y[3][-1], solucion.y[4][-1], solucion.y[5][-1], solucion.y[6][-1]] # quisiera ver de pasar esto de una forma más elegante, usando el comando solucion.y[:,-1]), pero por algun motivo que aun no comprendo termina dando error.
        self.n = self.y_actual[0]

        # Guardar en memoria para el gráfico
        self.t_data.append(self.t)
        self.n_data.append(self.y_actual[0])

        # Guardar en tiempo real en el archivo CSV (protegido contra PermissionError)
        try:
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([round(self.t, 3), round(self.y_actual[0], 4), self.pos_nuc, self.pos_BC1, self.pos_BC2])
        except PermissionError:
            # Se ignora silenciosamente si el archivo está abierto (evita colapsar el programa)
            pass

        # Actualizar datos del gráfico de manera eficiente (sin borrar los ejes)
        self.line.set_data(self.t_data, self.n_data)

        # Ajuste dinámico del eje X si excede la vista actual
        x_limit_curr = self.ax.get_xlim()[1]
        if self.t > x_limit_curr:
            self.ax.set_xlim(0, self.t + 5)

        # Ajuste dinámico del eje Y si la amplitud excede los límites visibles
        y_min, y_max = self.ax.get_ylim()
        if self.n > y_max or self.n < y_min:
            hist_min = min(self.n_data)
            hist_max = max(self.n_data)
            margin = max(1.0, (hist_max - hist_min) * 0.1)
            self.ax.set_ylim(hist_min - margin, hist_max + margin)

        self.canvas.draw()

# --- Ejecución de la App ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
