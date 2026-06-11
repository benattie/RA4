import sys
import csv
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel, QFormLayout)
from PyQt6.QtCore import QTimer, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class SimuladorGrafico(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulación Física en Tiempo Real con PyQt6")
        self.setGeometry(100, 100, 900, 600)

        # --- Variables de la Simulación ---
        self.dt = 0.05  # Paso de tiempo
        self.reset_sim_variables()

        # Nombre del archivo CSV
        self.csv_filename = "simulacion_fisica.csv"
        self.inicializar_csv()

        # --- Configuración del Timer para el loop de física ---
        self.timer = QTimer()
        self.timer.setInterval(20)  # ~50 FPS
        self.timer.timeout.connect(self.loop_simulacion)

        # --- Configuración de la Interfaz de Usuario ---
        self.init_ui()

    def reset_sim_variables(self):
        """Reinicia el estado físico del sistema."""
        self.t = 0.0
        self.x = 5.0   # Posición inicial (desplazamiento del resorte)
        self.v = 0.0   # Velocidad inicial
        self.t_data = []
        self.x_data = []

    def inicializar_csv(self):
        """Crea el archivo CSV e inserta las cabeceras."""
        with open(self.csv_filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Tiempo (s)", "Posicion (m)", "Velocidad (m/s)"])

    def init_ui(self):
        # Widget central y layout principal (Horizontal: Controles | Gráfico)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- Panel Izquierdo: Controles ---
        panel_controles = QWidget()
        layout_controles = QVBoxLayout(panel_controles)
        main_layout.addWidget(panel_controles, stretch=1)

        # Sliders (Formulario)
        form_layout = QFormLayout()

        # Slider Masa (m)
        self.slider_m = QSlider(Qt.Orientation.Horizontal)
        self.slider_m.setRange(1, 100)  # Representa 0.1 a 10.0 kg
        self.slider_m.setValue(20)
        self.lbl_m = QLabel("2.0 kg")
        self.slider_m.valueChanged.connect(lambda v: self.lbl_m.setText(f"{v/10:.1f} kg"))
        form_layout.addRow(QLabel("Masa (m):"), self.slider_m)
        form_layout.addRow("", self.lbl_m)

        # Slider Amortiguamiento (b)
        self.slider_b = QSlider(Qt.Orientation.Horizontal)
        self.slider_b.setRange(0, 50)   # Representa 0.0 a 5.0 Ns/m
        self.slider_b.setValue(5)
        self.lbl_b = QLabel("0.5 Ns/m")
        self.slider_b.valueChanged.connect(lambda v: self.lbl_b.setText(f"{v/10:.1f} Ns/m"))
        form_layout.addRow(QLabel("Amortiguamiento (b):"), self.slider_b)
        form_layout.addRow("", self.lbl_b)

        # Slider Constante Elástica (k)
        self.slider_k = QSlider(Qt.Orientation.Horizontal)
        self.slider_k.setRange(5, 100)  # Representa 0.5 a 10.0 N/m
        self.slider_k.setValue(30)
        self.lbl_k = QLabel("3.0 N/m")
        self.slider_k.valueChanged.connect(lambda v: self.lbl_k.setText(f"{v/10:.1f} N/m"))
        form_layout.addRow(QLabel("Constante Resorte (k):"), self.slider_k)
        form_layout.addRow("", self.lbl_k)

        layout_controles.addLayout(form_layout)
        layout_controles.addSpacing(20)

        # Botones de control
        self.btn_iniciar = QPushButton("Iniciar")
        self.btn_pausar = QPushButton("Pausar")
        self.btn_reiniciar = QPushButton("Reiniciar")

        self.btn_iniciar.clicked.connect(self.start_sim)
        self.btn_pausar.clicked.connect(self.pause_sim)
        self.btn_reiniciar.clicked.connect(self.reset_sim)

        layout_controles.addWidget(self.btn_iniciar)
        layout_controles.addWidget(self.btn_pausar)
        layout_controles.addWidget(self.btn_reiniciar)
        layout_controles.addStretch()

        # --- Panel Derecho: Gráfico Matplotlib ---
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Posición vs Tiempo")
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Posición (m)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'r-', lw=2)

        main_layout.addWidget(self.canvas, stretch=2)

    # --- Lógica de los Botones ---
    def start_sim(self):
        self.timer.start()

    def pause_sim(self):
        self.timer.stop()

    def reset_sim(self):
        self.timer.stop()
        self.reset_sim_variables()
        self.inicializar_csv()  # Sobrescribe el CSV para una nueva simulación
        self.line.set_data([], [])
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(-6, 6)
        self.canvas.draw()

    # --- Loop Principal (Cálculo, Gráfico y CSV) ---
    def loop_simulacion(self):
        # 1. Obtener parámetros actualizados desde los sliders
        m = self.slider_m.value() / 10.0
        b = self.slider_b.value() / 10.0
        k = self.slider_k.value() / 10.0

        # 2. Calcular ecuaciones diferenciales (Método de Euler-Maruyama / Euler simple)
        # F_total = - k*x - b*v = m*a  -> a = (-k*x - b*v) / m
        a = (-k * self.x - b * self.v) / m
        self.v += a * self.dt
        self.x += self.v * self.dt
        self.t += self.dt

        # 3. Guardar datos en las estructuras internas
        self.t_data.append(self.t)
        self.x_data.append(self.x)

        # 4. Guardar datos en el archivo CSV (modo append 'a')
        with open(self.csv_filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([round(self.t, 3), round(self.x, 4), round(self.v, 4)])

        # 5. Actualizar el gráfico dinámicamente
        self.line.set_data(self.t_data, self.x_data)

        # Ajustar límites del eje X dinámicamente si el tiempo excede la vista actual
        if self.t > self.ax.get_xlim()[1]:
            self.ax.set_xlim(0, self.t + 5)

        # Ajustar límites del eje Y si la oscilación es más grande de lo esperado
        if self.x > self.ax.get_ylim()[1] or self.x < self.ax.get_ylim()[0]:
            self.ax.set_ylim(self.x - 2, self.x + 2)

        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = SimuladorGrafico()
    ventana.show()
    sys.exit(app.exec())
