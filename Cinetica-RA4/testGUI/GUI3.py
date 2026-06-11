import sys
import json
import csv
import os
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QSlider, 
    QVBoxLayout, QHBoxLayout, QLabel, QDialog, QLineEdit, 
    QFileDialog, QFormLayout, QGridLayout
)
from PyQt6.QtCore import QTimer, Qt
from scipy.integrate import solve_ivp
import matplotlib.backends.backend_qtagg as mini_mpl
from matplotlib.figure import Figure


# --- SISTEMA FÍSICO (Ecuación Diferencial) ---
def sistema_ecuaciones(t, y, p1, p2, p3):
    """
    Ejemplo de un oscilador no lineal (tipo Van der Pol modificado).
    y[0] = Posición (x), y[1] = Velocidad (v)
    Se comporta como un sistema rígido (stiff) según los parámetros.
    """
    x, v = y[0], y[1]
    dxdt = v
    dvdt = - p1 * x - p2 * (x**2 - 1) * v + p3
    return [dxdt, dvdt]


# --- VENTANA AUXILIAR: CONDICIONES INICIALES ---
class VentanaConfiguracion(QDialog):
    def __init__(self, valores_actuales, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Definir Valores Iniciales")
        self.setModal(True)
        
        self.layout = QFormLayout(self)
        
        # Campos de entrada
        self.input_x0 = QLineEdit(str(valores_actuales.get("x0", 1.0)))
        self.input_v0 = QLineEdit(str(valores_actuales.get("v0", 0.0)))
        
        self.layout.addRow("Posición Inicial (x0):", self.input_x0)
        self.layout.addRow("Velocidad Inicial (v0):", self.input_v0)
        
        # Botón Guardar
        self.btn_guardar = QPushButton("Guardar y Aplicar")
        self.btn_guardar.clicked.connect(self.accept)
        self.layout.addRow(self.btn_guardar)

    def obtener_valores(self):
        try:
            return {
                "x0": float(self.input_x0.text()),
                "v0": float(self.input_v0.text())
            }
        except ValueError:
            return {"x0": 1.0, "v0": 0.0} # Valores por defecto en caso de error de tipeo


# --- VENTANA PRINCIPAL DE LA INTERFAZ ---
class InterfazSimulacion(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Sistema Físico - SciPy Radau")
        self.resize(900, 600)
        
        # Rutas de archivos por defecto
        self.archivo_config = "config_inicial.json"
        self.archivo_csv = "resultados_simulacion.csv"
        
        # Estado inicial de la simulación
        self.valores_iniciales = self.cargar_config_desde_ruta(self.archivo_config)
        self.t_actual = 0.0
        self.y_actual = [self.valores_iniciales["x0"], self.valores_iniciales["v0"]]
        
        # Historial de datos para graficar
        self.historial_t = []
        self.historial_x = []
        self.historial_v = []
        
        # Parámetros variables de los Sliders (valores reales mapeados)
        self.p1 = 1.0
        self.p2 = 1.0
        self.p3 = 0.0
        
        # Configuración del Timer para tiempo real
        self.timer = QTimer()
        self.timer.setInterval(30) # ~30 ms por paso de actualización
        self.timer.timeout.connect(self.dar_paso_simulacion)
        
        self.init_ui()

    def init_ui(self):
        # Widget Central y Layout Principal
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QHBoxLayout(widget_central)
        
        # --- PANEL DE CONTROLES (Izquierda) ---
        panel_controles = QVBoxLayout()
        
        # Botones de simulación
        self.btn_iniciar = QPushButton("Iniciar")
        self.btn_pausar = QPushButton("Pausar")
        self.btn_reiniciar = QPushButton("Reiniciar")
        
        self.btn_iniciar.clicked.connect(self.iniciar_simulacion)
        self.btn_pausar.clicked.connect(self.pausar_simulacion)
        self.btn_reiniciar.clicked.connect(self.reiniciar_simulacion)
        
        panel_controles.addWidget(self.btn_iniciar)
        panel_controles.addWidget(self.btn_pausar)
        panel_controles.addWidget(self.btn_reiniciar)
        
        # Botones de Configuración
        self.btn_config_manual = QPushButton("Definir C. Iniciales")
        self.btn_cargar_archivo = QPushButton("Cargar Config (.json)")
        
        self.btn_config_manual.clicked.connect(self.abrir_ventana_config)
        self.btn_cargar_archivo.clicked.connect(self.buscar_archivo_config)
        
        panel_controles.addWidget(self.btn_config_manual)
        panel_controles.addWidget(self.btn_cargar_archivo)
        
        panel_controles.addSpacing(20)
        
        # Sliders y etiquetas
        self.lbl_p1 = QLabel(f"Parámetro 1 (Fuerza Rest.): {self.p1:.2f}")
        self.slider_p1 = QSlider(Qt.Orientation.Horizontal)
        self.slider_p1.setRange(1, 100)
        self.slider_p1.setValue(10)
        self.slider_p1.valueChanged.connect(self.actualizar_parametros)
        
        self.lbl_p2 = QLabel(f"Parámetro 2 (Amortiguamiento): {self.p2:.2f}")
        self.slider_p2 = QSlider(Qt.Orientation.Horizontal)
        self.slider_p2.setRange(0, 100)
        self.slider_p2.setValue(10)
        self.slider_p2.valueChanged.connect(self.actualizar_parametros)
        
        self.lbl_p3 = QLabel(f"Parámetro 3 (Forzamiento): {self.p3:.2f}")
        self.slider_p3 = QSlider(Qt.Orientation.Horizontal)
        self.slider_p3.setRange(-50, 50)
        self.slider_p3.setValue(0)
        self.slider_p3.valueChanged.connect(self.actualizar_parametros)
        
        panel_controles.addWidget(self.lbl_p1)
        panel_controles.addWidget(self.slider_p1)
        panel_controles.addWidget(self.lbl_p2)
        panel_controles.addWidget(self.slider_p2)
        panel_controles.addWidget(self.lbl_p3)
        panel_controles.addWidget(self.slider_p3)
        
        panel_controles.addStretch()
        layout_principal.addLayout(panel_controles, stretch=1)
        
        # --- PANEL DEL GRÁFICO (Derecha) ---
        self.figura = Figure()
        self.canvas = mini_mpl.FigureCanvasQTAgg(self.figura)
        self.ax = self.figura.add_subplot(111)
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Amplitud / Velocidad")
        self.ax.grid(True)
        
        self.linea_x, = self.ax.plot([], [], label="Posición (x)", color="blue")
        self.linea_v, = self.ax.plot([], [], label="Velocidad (v)", color="red")
        self.ax.legend()
        
        layout_principal.addWidget(self.canvas, stretch=3)
        
        # Inicializar el archivo CSV vacío con cabeceras
        self.preparar_csv()
        self.actualizar_parametros()

    # --- LÓGICA DE ARCHIVOS DE CONFIGURACIÓN ---
    def cargar_config_desde_ruta(self, ruta):
        if os.path.exists(ruta):
            try:
                with open(ruta, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"x0": 1.0, "v0": 0.0} # Por defecto

    def guardar_config(self):
        with open(self.archivo_config, "w") as f:
            json.dump(self.valores_iniciales, f, indent=4)

    def abrir_ventana_config(self):
        ventana = VentanaConfiguracion(self.valores_iniciales, self)
        if ventana.exec() == QDialog.DialogCode.Accepted:
            self.valores_iniciales = ventana.obtener_valores()
            self.guardar_config()
            self.reiniciar_simulacion()

    def buscar_archivo_config(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Cargar Configuración", "", "JSON Files (*.json)")
        if ruta:
            self.valores_iniciales = self.cargar_config_desde_ruta(ruta)
            # Sincronizar archivo por defecto local
            self.guardar_config()
            self.reiniciar_simulacion()

    # --- LÓGICA DE DATOS (CSV) ---
    def preparar_csv(self):
        with open(self.archivo_csv, mode="w", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow(["Tiempo (t)", "Posicion (x)", "Velocidad (v)"])

    def registrar_en_csv(self, t, x, v):
        with open(self.archivo_csv, mode="a", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow([t, x, v])

    # --- SIMULACIÓN Y CONTROL ---
    def actualizar_parametros(self):
        # Mapeamos los enteros de los sliders a floats útiles
        self.p1 = self.slider_p1.value() / 10.0
        self.p2 = self.slider_p2.value() / 10.0
        self.p3 = self.slider_p3.value() / 10.0
        
        self.lbl_p1.setText(f"Parámetro 1 (Fuerza Rest.): {self.p1:.2f}")
        self.lbl_p2.setText(f"Parámetro 2 (Amortiguamiento): {self.p2:.2f}")
        self.lbl_p3.setText(f"Parámetro 3 (Forzamiento): {self.p3:.2f}")

    def iniciar_simulacion(self):
        self.timer.start()

    def pausar_simulacion(self):
        self.timer.stop()

    def reiniciar_simulacion(self):
        self.timer.stop()
        self.t_actual = 0.0
        self.y_actual = [self.valores_iniciales["x0"], self.valores_iniciales["v0"]]
        
        self.historial_t.clear()
        self.historial_x.clear()
        self.historial_v.clear()
        
        self.preparar_csv()
        
        # Limpiar gráfico en pantalla
        self.linea_x.set_data([], [])
        self.linea_v.set_data([], [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def dar_paso_simulacion(self):
        dt = 0.05 # Paso de tiempo de integración por ciclo del timer
        t_siguiente = self.t_actual + dt
        
        # Resolver el paso utilizando el método rígido Radau
        solucion = solve_ivp(
            sistema_ecuaciones,
            [self.t_actual, t_siguiente],
            self.y_actual,
            method='Radau',
            args=(self.p1, self.p2, self.p3),
            rtol=1e-6
        )
        
        # Actualizar variables de estado con el último punto calculado
        print(solucion.y[-1])
        self.t_actual = solucion.t[-1]
        self.y_actual = [solucion.y[0][-1], solucion.y[1][-1]]
        
        # Almacenar en listas para graficar
        self.historial_t.append(self.t_actual)
        self.historial_x.append(self.y_actual[0])
        self.historial_v.append(self.y_actual[1])
        
        # Guardar inmediatamente en el CSV de manera persistente
        self.registrar_en_csv(self.t_actual, self.y_actual[0], self.y_actual[1])
        
        # Actualizar datos del gráfico en tiempo real
        self.linea_x.set_data(self.historial_t, self.historial_x)
        self.linea_v.set_data(self.historial_t, self.historial_v)
        
        # Reajustar límites dinámicamente para simular scroll/avance continuo
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = InterfazSimulacion()
    ventana.show()
    sys.exit(app.exec())
