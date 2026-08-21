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
import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel,
                             QDialog, QLineEdit, QFileDialog, QFormLayout, QMessageBox,
                             QCheckBox)
from PyQt6.QtCore import QTimer, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from Simulador_RA4_ventanas_auxiliares import ConfigPFDialog, ConfigCIDialog
from Simulador_RA4_funciones import get_current_decade

# --- Ventana Principal de la Interfaz ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de tablero de operaciones y funcionamiento del RA4")
        self.resize(950, 600)

        # Valores por defecto de simulación
        self.config_param_fisicos = {"parámetros físicos RA4": {"Beta efectivo": 730e-5, "Lambda [s]": 4.7e-5, "lambda_i [s^-1]": [0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87], "fracciones_i": [0.038, 0.213, 0.188, 0.407, 0.128, 0.026]}, "parámetros constructivos RA4": {"Recorrido del núcleo [mm]": 50, "Recorrido de las barras de control [mm]": 250 } }
        self.config_cond_iniciales = {"condiciones iniciales": {"densidad de neutrones": 1091.25, "concentración grupo neutrones retardados": [507140, 1138855, 277082, 221815, 15496, 1139], "paso temporal": 0.001} }

        # Nombres de los archivos por defecto para la simulación
        self.param_fisicos_filename = "00_input_cinetica_RA4.json"
        self.cond_iniciales_filename = "01_input_condiciones_iniciales.json"

        #Cargar configuración si existe
        self.load_params_from_file(self.param_fisicos_filename, silent=True)
        self.load_config_init_from_file(self.cond_iniciales_filename, silent=True)

        # Archivo donde guardo los resultados de la simulación
        self.csv_filename = "simulacion_RA4.csv"

        # Parámetros físicos dinámicos. Posición del nucleo y de las barras de control (valores iniciales para los sliders)
        self.pos_nuc = 0.0   # nucleo
        self.pos_fuente = 0.0   # fuente
        self.pos_BC1 = 0.0   # barra de control 1
        self.pos_BC2 = 0.0   # barra de control 2

        # Parámetros físicos estáticos. Beta efectivo del reactor, tiempo de decaimiento de los neutrones prompt, y de los 6 grupos de reactores retardados
        self.beta_eff = self.config_param_fisicos["parámetros físicos RA4"]["Beta efectivo"]
        self.LAMBDA = self.config_param_fisicos["parámetros físicos RA4"]["Lambda [s]"]
        self.lambda_i = np.array(self.config_param_fisicos["parámetros físicos RA4"]["lambda_i [s^-1]"])
        self.fracciones_i = np.array(self.config_param_fisicos["parámetros físicos RA4"]["fracciones_i"])

        # Variables de estado de la simulación (valores iniciales)
        self.t = 0.0
        self.n = self.config_cond_iniciales["condiciones iniciales"]["densidad de neutrones"]
        self.Ci = np.array(self.config_cond_iniciales["condiciones iniciales"]["concentración grupo neutrones retardados"])

        self.y_actual = np.concatenate(([self.n], self.Ci))

        # Vectores para almacenar datos del gráfico
        self.t_data = []
        self.n_data = []

        # Configuración del Timer para la simulación en tiempo real
        self.timer = QTimer()
        self.timer.timeout.connect(self.simulation_step)

        self.init_ui()
        # chequear que no haya bucles de actualización y redondeos
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
        # Nucleo
        self.lbl_pos_nuc = QLabel(f"Posición del núcleo (%): {self.pos_nuc:.2f} %")
        self.slider_pos_nuc = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_nuc.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_nuc.setValue(int(self.pos_nuc))
        self.slider_pos_nuc.valueChanged.connect(self.update_parameters)

        # Fuente
        self.lbl_pos_fuente = QLabel(f"Posición de la fuente (%): {self.pos_fuente:.2f} %")
        self.slider_pos_fuente = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_fuente.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_fuente.setValue(int(self.pos_fuente))
        self.slider_pos_fuente.valueChanged.connect(self.update_parameters)

        # Barra de control 1
        self.lbl_pos_BC1 = QLabel(f"Posición de la barra de control 1 (BC1): {self.pos_BC1:.2f} %")
        self.slider_pos_BC1 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_BC1.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_BC1.setValue(int(self.pos_BC1))
        self.slider_pos_BC1.valueChanged.connect(self.update_parameters)

        # Barra de control 2
        self.lbl_pos_BC2 = QLabel(f"Posición de la barra de control 2 (BC2): {self.pos_BC2:.2f} %")
        self.slider_pos_BC2 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_BC2.setRange(0, 100)  # Mapea a 0 - 100.0
        self.slider_pos_BC2.setValue(int(self.pos_BC2))
        self.slider_pos_BC2.valueChanged.connect(self.update_parameters)

        control_layout.addWidget(self.lbl_pos_nuc)
        control_layout.addWidget(self.slider_pos_nuc)
        control_layout.addWidget(self.lbl_pos_fuente)
        control_layout.addWidget(self.slider_pos_fuente)
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

        # Botones de Configuración de las condiciones iniciales
        self.btn_config_init = QPushButton("Condiciones Iniciales...")
        self.btn_config_init.clicked.connect(self.open_config_init_dialog)

        self.btn_load_init_file = QPushButton("Cargar conf. de Condiciones desde archivo")
        self.btn_load_init_file.clicked.connect(self.manual_load_init_config)

        control_layout.addWidget(self.btn_config_init)
        control_layout.addWidget(self.btn_load_init_file)

        control_layout.addSpacing(10)

        # Botones de Configuración de los parámetros físicos del reactor
        self.btn_config_input_param = QPushButton("Parámetros físicos del reactor...")
        self.btn_config_input_param.clicked.connect(self.open_config_param_dialog)

        self.btn_load_input_param_file = QPushButton("Cargar config. de Parámetros desde archivo")
        self.btn_load_input_param_file.clicked.connect(self.manual_load_param_config)

        control_layout.addWidget(self.btn_config_input_param)
        control_layout.addWidget(self.btn_load_input_param_file)

        control_layout.addSpacing(15)

        # Opciones de simulación y visualización (Checkboxes)
        self.chk_log_scale = QCheckBox("Escala Logarítmica (Eje Y)")
        self.chk_log_scale.stateChanged.connect(self.update_y_scale)
        control_layout.addWidget(self.chk_log_scale)

        control_layout.addStretch()
        main_layout.addLayout(control_layout, stretch=1)

    # --- Lógica de Parámetros y Archivos ---
    def update_parameters(self):
        self.pos_nuc = self.slider_pos_nuc.value()
        self.pos_fuente = self.slider_pos_fuente.value()
        self.pos_BC1 = self.slider_pos_BC1.value()
        self.pos_BC2 = self.slider_pos_BC2.value()

        self.lbl_pos_nuc.setText(f"Pos. del núcleo (%): {self.pos_nuc:.2f} %")
        self.lbl_pos_fuente.setText(f"Pos. de la fuente (%): {self.pos_fuente:.2f} %")
        self.lbl_pos_BC1.setText(f"Pos. de la barra de control 1 (BC1): {self.pos_BC1:.2f} %")
        self.lbl_pos_BC2.setText(f"Pos. de la barra de control 2 (BC2): {self.pos_BC2:.2f} %")

    def open_config_init_dialog(self):
        dialog = ConfigCIDialog(self, self.config_cond_iniciales)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_values()
            filename, _ = QFileDialog.getSaveFileName(self, "Guardar Condiciones Iniciales como...", "", "JSON Files (*.json)")
            if filename:
                self.config_cond_iniciales = new_config
                self.save_config_to_file(filename)
                self.reset_simulation()
            else:
                # Si se cancela el guardado, aun así aplicamos los cambios en memoria
                self.config_cond_iniciales = new_config
                self.reset_simulation()

    def open_config_param_dialog(self):
        dialog = ConfigPFDialog(self, self.config_param_fisicos)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = dialog.get_values()
            filename, _ = QFileDialog.getSaveFileName(self, "Guardar Parámetros del Reactor como...", "", "JSON Files (*.json)")
            if filename:
                self.config_param_fisicos = new_params
                self.save_params_to_file(filename)
                self.reset_simulation()
            else:
                # Si se cancela el guardado, aun así aplicamos los cambios en memoria
                self.config_param_fisicos = new_params
                self.reset_simulation()

    def save_config_to_file(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.config_cond_iniciales, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la configuración: {e}")

    def save_params_to_file(self, filename):
        try:
            with open(filename, 'w') as f:
                json.dump(self.config_param_fisicos, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar las constantes: {e}")

    def load_config_init_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.config_cond_iniciales = json.load(f)
                if not silent:
                    QMessageBox.information(self, "Éxito", "Configuración cargada correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo de configuración: {e}")
        else:
            # Si el archivo por defecto no existe, lo creamos con los valores iniciales
            self.save_config_to_file(filename)

    def load_params_from_file(self, filename, silent=False):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.config_param_fisicos = json.load(f)
                if not silent:
                    QMessageBox.information(self, "Éxito", "Constantes cargadas correctamente.")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "Error", f"Error al leer el archivo de constantes: {e}")
        else:
            # Si el archivo por defecto no existe, lo creamos con los valores iniciales
            self.save_params_to_file(filename)

    def manual_load_init_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Cargar Configuración", "", "JSON Files (*.json)")
        if filename:
            self.load_config_init_from_file(filename)
            self.reset_simulation()

    def manual_load_param_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Cargar Constantes del Sistema", "", "JSON Files (*.json)")
        if filename:
            self.load_params_from_file(filename)
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
        self.n = self.config_cond_iniciales["condiciones iniciales"]["densidad de neutrones"]
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
            args=(self.beta_eff, self.LAMBDA, self.lambda_i, self.fracciones_i, self.pos_nuc, self.pos_BC1, self.pos_BC2, self.pos_fuente),
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
        t_limit_curr = self.ax.get_xlim()[1]
        if self.t > t_limit_curr:
            self.ax.set_xlim(0, self.t + 5)

        # Ajuste dinámico del eje Y si la amplitud excede los límites visibles
        y_min, y_max = self.ax.get_ylim()
        if self.n > y_max or self.n < y_min:
            self.adjust_y_limits()
            """
            hist_min = min(self.n_data)
            hist_max = max(self.n_data)
            margin = max(1.0, (hist_max - hist_min) * 0.1)
            self.ax.set_ylim(hist_min - margin, hist_max + margin)
            """
        self.canvas.draw()

    def adjust_y_limits(self):
        if not self.n_data:
            margin = max(2.0, abs(self.n) * 0.5)
            self.ax.set_ylim(self.n - margin, self.n + margin)
        else:
            hist_min = min(self.n_data)
            hist_max = max(self.n_data)
            margin = max(1.0, (hist_max - hist_min) * 0.1)
            if self.chk_log_scale.isChecked():
                decade_lower = get_current_decade(hist_min, 1.0)
                decade_upper = get_current_decade(hist_max, 1.0)
                self.ax.set_ylim(decade_lower, decade_upper*10)
            else:
                self.ax.set_ylim(hist_min - margin, hist_max + margin)

    def update_y_scale(self):
        if self.chk_log_scale.isChecked():
            # Symmetrical log scale to handle negative, zero, and positive values elegantly
            self.ax.set_yscale('symlog', linthresh=1.0, linscale=1.0)
            self.ax.yaxis.set_major_locator(ticker.SymmetricalLogLocator(self.ax.yaxis.get_transform()))
            self.ax.yaxis.set_minor_locator(ticker.SymmetricalLogLocator(self.ax.yaxis.get_transform(), subs=range(2, 10)))
        else:
            self.ax.set_yscale('linear')

        self.adjust_y_limits()
        self.canvas.draw()

# --- Ejecución de la App ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
