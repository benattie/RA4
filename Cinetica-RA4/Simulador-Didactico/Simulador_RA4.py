#modulos para la simulacion
import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import Radau # Uso esto en vez de solve_ivp porque necesito ajustar cosas en tiempo real

from Simulador_RA4_SimulationThread import SimulationThread

# modulos para trabajar mutiproceso
import time
import queue
import threading
from collections import deque

# Escritura en disco
from Simulador_RA4_DiskWriterThread import DiskWriterThread

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
from PyQt6.QtCore import QThread, QTimer, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from Simulador_RA4_ventanas_auxiliares import ConfigPFDialog, ConfigCIDialog
from Simulador_RA4_funciones_auxiliares import get_current_decade


# --- Ventana Principal de la Interfaz ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de tablero de operaciones y funcionamiento del RA4")
        self.resize(950, 600)

        # Valores por defecto de simulación
        self.config_param_fisicos = {"parámetros físicos RA4": {"Beta efectivo": 730e-5, "Lambda [s]": 4.7e-5, "lambda_i [s^-1]": [0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87], "fracciones_i": [0.038, 0.213, 0.188, 0.407, 0.128, 0.026]}, "parámetros constructivos RA4": {"Recorrido del núcleo [mm]": 50, "Recorrido de las barras de control [mm]": 250 }, "paso temporal": 0.005 }
        self.config_cond_iniciales = {"condiciones iniciales": {"densidad de neutrones": 1000, "concentración grupo neutrones retardados": [0, 0, 0, 0, 0, 0]} }

        # Nombres de los archivos por defecto para la simulación
        self.param_fisicos_filename = "00_input_cinetica_RA4.json"
        self.cond_iniciales_filename = "01_input_condiciones_iniciales.json"

        #Cargar configuración si existe
        self.load_params_from_file(self.param_fisicos_filename, silent=True)
        self.load_config_init_from_file(self.cond_iniciales_filename, silent=True)

        # Archivo donde guardo los resultados de la simulación
        self.csv_filename = "simulacion_RA4.csv"

        # Parámetros físicos dinámicos (valores por defecto). Posición del nucleo y de las barras de control (valores iniciales para los sliders)
        self.config = {
            "pos nucleo": 0.0,
            "pos fuente": 0.0,
            "pos BC1": 0.0,
            "pos BC2": 0.0
            }

        self.pos_nucleo = self.config["pos nucleo"]   # nucleo
        self.pos_fuente = self.config["pos fuente"]   # fuente
        self.pos_BC1 = self.config["pos BC1"]   # barra de control 1
        self.pos_BC2 = self.config["pos BC2"]   # barra de control 2

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

        self.writer_thread = DiskWriterThread(filename=self.csv_filename, block_size=500, parent=self)
        self.sim_thread = SimulationThread(self.writer_thread.queue, self.config_param_fisicos, self.config_cond_iniciales, self.config, parent=self)

        self.background = None
        self.needs_full_draw = True

        self.current_window_min = 0.0
        self.current_window_max = 60.0

        # Configuración del Timer para la simulación en tiempo real
        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(16)
        self.plot_timer.timeout.connect(self.update_plot_60fps)

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
        self.line, = self.ax.plot([], [], label="Flujo de neutrones (n)", color="blue", lw=2, animated=True)
        self.ax.legend(loc="lower right")
        
        main_layout.addWidget(self.canvas, stretch=3)

        # --- Panel Derecho: Controles ---
        control_layout = QVBoxLayout()

        # Sliders y etiquetas
        # Nucleo
        self.lbl_pos_nucleo = QLabel(f"Pos. del núcleo (%): {self.pos_nucleo:.2f} %")
        self.slider_pos_nucleo = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_nucleo.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_nucleo.setValue(int(self.pos_nucleo))
        self.slider_pos_nucleo.valueChanged.connect(self.update_parameters)

        # Fuente
        self.lbl_pos_fuente = QLabel(f"Pos. de la fuente (%): {self.pos_fuente:.2f} %")
        self.slider_pos_fuente = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_fuente.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_fuente.setValue(int(self.pos_fuente))
        self.slider_pos_fuente.valueChanged.connect(self.update_parameters)

        # Barra de control 1
        self.lbl_pos_BC1 = QLabel(f"Pos. de la barra de control 1 (BC1): {self.pos_BC1:.2f} %")
        self.slider_pos_BC1 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_BC1.setRange(0, 100)  # Mapea a 0.0 - 100.0
        self.slider_pos_BC1.setValue(int(self.pos_BC1))
        self.slider_pos_BC1.valueChanged.connect(self.update_parameters)

        # Barra de control 2
        self.lbl_pos_BC2 = QLabel(f"Pos. de la barra de control 2 (BC2): {self.pos_BC2:.2f} %")
        self.slider_pos_BC2 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos_BC2.setRange(0, 100)  # Mapea a 0 - 100.0
        self.slider_pos_BC2.setValue(int(self.pos_BC2))
        self.slider_pos_BC2.valueChanged.connect(self.update_parameters)

        control_layout.addWidget(self.lbl_pos_nucleo)
        control_layout.addWidget(self.slider_pos_nucleo)
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
        self.chk_sliding_window = QCheckBox("Modo Osciloscopio (Páginas de 60 s)")
        self.chk_sliding_window.setChecked(True)
        self.chk_sliding_window.stateChanged.connect(self.trigger_full_redraw)
        control_layout.addWidget(self.chk_sliding_window)

        control_layout.addSpacing(10)

        self.chk_log_scale = QCheckBox("Escala Logarítmica (Eje Y)")
        self.chk_log_scale.stateChanged.connect(self.update_y_scale)
        control_layout.addWidget(self.chk_log_scale)

        control_layout.addStretch()
        main_layout.addLayout(control_layout, stretch=1)

    def trigger_full_redraw(self):
        self.needs_full_draw = True

    def update_parameters(self):
        self.pos_nucleo = float(self.slider_pos_nucleo.value())
        self.pos_fuente = float(self.slider_pos_fuente.value())
        self.pos_BC1 = float(self.slider_pos_BC1.value())
        self.pos_BC2 = float(self.slider_pos_BC2.value())

        self.lbl_pos_nucleo.setText(f"Pos. del núcleo (%): {self.pos_nucleo:.2f} %")
        self.lbl_pos_fuente.setText(f"Pos. de la fuente (%): {self.pos_fuente:.2f} %")
        self.lbl_pos_BC1.setText(f"Pos. de la barra de control 1 (BC1): {self.pos_BC1:.2f} %")
        self.lbl_pos_BC2.setText(f"Pos. de la barra de control 2 (BC2): {self.pos_BC2:.2f} %")

        self.config["pos nucleo"] = self.pos_nucleo
        self.config["pos fuente"] = self.pos_fuente
        self.config["pos BC1"] = self.pos_BC1
        self.config["pos BC2"] = self.pos_BC2

        if hasattr(self, 'sim_thread'):
            self.sim_thread.update_params(self.pos_nucleo, self.pos_fuente, self.pos_BC1, self.pos_BC2)

    def open_config_init_dialog(self):
        dialog = ConfigCIDialog(self, self.config_cond_iniciales)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_values()
            filename, _ = QFileDialog.getSaveFileName(self, "Guardar Condiciones Iniciales como...", "", "JSON Files (*.json)")
            if filename:
                self.config_cond_iniciales = new_config
                self.sim_thread.reset_state(self.config_cond_iniciales)
                self.save_config_to_file(filename)
                self.reset_simulation()
            else:
                # Si se cancela el guardado, aun así aplicamos los cambios en memoria
                self.config_cond_iniciales = new_config
                self.sim_thread.reset_state(self.config_cond_iniciales)
                self.reset_simulation()

    def open_config_param_dialog(self):
        dialog = ConfigPFDialog(self, self.config_param_fisicos)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = dialog.get_values()
            filename, _ = QFileDialog.getSaveFileName(self, "Guardar Parámetros del Reactor como...", "", "JSON Files (*.json)")
            if filename:
                self.config_param_fisicos = new_params
                self.sim_thread.set_config(self.config_param_fisicos)
                self.save_params_to_file(filename)
                self.reset_simulation()
            else:
                # Si se cancela el guardado, aun así aplicamos los cambios en memoria
                self.config_param_fisicos = new_params
                self.sim_thread.set_config(self.config_param_fisicos)
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

    def start_simulation(self):
        t_data, _, _, _ = self.sim_thread.get_plot_data()
        # Si el CSV no existe, crearlo con cabeceras
        if not os.path.exists(self.csv_filename) or self.t == 0.0:
            try:
                with open(self.csv_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Tiempo (s)", "Flujo de neutrones (n)", "pos_nucleo (%)", "pos fuente (%)", "pos_BC1 (%)", "pos_BC2 (%)"])
            except PermissionError:
                QMessageBox.warning(self, "Error de archivo", "No se pudo escribir en el CSV. Asegúrese de que no esté abierto en otra aplicación.")
                return

        if not self.writer_thread.isRunning():
            self.writer_thread.start()

        if not self.sim_thread.isRunning():
            self.sim_thread.start()

        self.needs_full_draw = True
        self.plot_timer.start(17)

    def pause_simulation(self):
        self.plot_timer.stop()
        if self.sim_thread.isRunning():
            self.sim_thread.stop()

    def update_plot_60fps(self):
        t_data, n_data, current_t, y_actual = self.sim_thread.get_plot_data()
        if not t_data:
            return

        t_arr = np.array(t_data)

        if self.chk_sliding_window.isChecked():
            window_size = 60.0
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
            n_plot = n_data[idx_start:]
        else:
            t_min = 0.0
            t_max = max(60.0, current_t + 2.0)
            if len(t_data) > 12000:
                step = len(t_data) // 6000
                t_plot = t_data[::step]
                n_plot = n_data[::step]
            else:
                t_plot = t_data
                n_plot = n_data

        curr_xlim = self.ax.get_xlim()
        curr_ylim = self.ax.get_ylim()

        if abs(curr_xlim[0] - t_min) > 0.01 or abs(curr_xlim[1] - t_max) > 0.01:
            self.ax.set_xlim(t_min, t_max)
            self.needs_full_draw = True

        all_max = max(y_actual, 1000)
        target_ylim = max(2.5, all_max * 1.3)
        if target_ylim > curr_ylim[1] or target_ylim < curr_ylim[1] * 0.5:
            self.ax.set_ylim(-1, target_ylim)
            self.needs_full_draw = True

        if self.needs_full_draw or self.background is None:
            self.canvas.draw()
            self.background = self.canvas.copy_from_bbox(self.ax.bbox)
            self.needs_full_draw = False

        self.line.set_data(t_plot, n_plot)

        self.canvas.restore_region(self.background)
        self.ax.draw_artist(self.line)
        self.canvas.blit(self.ax.bbox)

    def reset_simulation(self):
        self.pause_simulation()
        self.sim_thread.reset_state(self.config_cond_iniciales, self.config_param_fisicos)
        self.t_data.clear()
        self.n_data.clear()

        # Limpiar datos de la línea en lugar de limpiar todo el gráfico
        self.line.set_data([], [])

        # Establecer límites del gráfico de forma limpia
        self.current_window_min = 0.0
        self.current_window_max = 60.0

        self.ax.set_xlim(0, 60)

        # Definir rango dinámico inicial para el eje Y basado en x0
        margin = max(2.0, abs(self.n) * 0.5)
        self.ax.set_ylim(self.n - margin, self.n + margin)

        self.needs_full_draw = True
        self.canvas.draw()

    def closeEvent(self, event):
        self.plot_timer.stop()
        if hasattr(self, 'sim_thread') and self.sim_thread.isRunning():
            self.sim_thread.stop()
        if hasattr(self, 'writer_thread') and self.writer_thread.isRunning():
            self.writer_thread.stop()
        super().closeEvent(event)

    def adjust_y_limits(self):
        if not self.n_data:
            margin = max(2.0, abs(self.n) * 0.5)
            max_ylim = max(self.n + margin, 1000)
            self.ax.set_ylim(0, max_ylim)
        else:
            hist_min = min(self.n_data)
            hist_max = max(self.n_data)
            margin = max(1.0, (hist_max - hist_min) * 0.1)
            if self.chk_log_scale.isChecked():
                decade_lower = get_current_decade(hist_min, 1.0)
                decade_upper = get_current_decade(hist_max, 1.0)
                max_decade = max(decade_upper*10, 1000)
                self.ax.set_ylim(decade_lower, max_decade)
            else:
                self.ax.set_ylim(hist_min - margin, hist_max + margin)

    def update_y_scale(self):
        if self.chk_log_scale.isChecked():
            # Symmetrical log scale to handle negative, zero, and positive values elegantly
            self.ax.set_yscale('symlog', linthresh=1.0, linscale=0.5)
            self.ax.yaxis.set_major_locator(ticker.SymmetricalLogLocator(self.ax.yaxis.get_transform()))
            self.ax.yaxis.set_minor_locator(ticker.SymmetricalLogLocator(self.ax.yaxis.get_transform(), subs=range(2, 10)))

            #self.ax.set_yscale('log', nonpositive='clip')
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
