# modulos para la interfaz gráfica
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel,
                             QDialog, QLineEdit, QFileDialog, QFormLayout, QMessageBox)


# --- Ventana Auxiliar (Condiciones Iniciales) ---
class ConfigCIDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Condiciones Iniciales")
        self.resize(500, 200)

        self.config = current_config or {"condiciones iniciales": {"flujo de neutrones": 1091.25, "concentración grupo neutrones retardados": [507140, 1138855, 277082, 221815, 15496, 1139], "paso temporal": 0.001} }

        layout = QFormLayout(self)

        self.input_n0 = QLineEdit(str(self.config["condiciones iniciales"]["flujo de neutrones"]))
        self.input_Ci = QLineEdit(str(self.config["condiciones iniciales"]["concentración grupo neutrones retardados"]))
        self.input_dt = QLineEdit(str(self.config["condiciones iniciales"]["paso temporal"]))

        layout.addRow("Flujo de neutrones inicial (n_0):", self.input_n0)
        ordinales = ["primer", "segundo", "tercer", "cuarto", "quinto", "sexto"]
        self.concentraciones = self.config["condiciones iniciales"]["concentración grupo neutrones retardados"]
        for i, (orden, concentracion) in enumerate(zip(ordinales, self.concentraciones)):
            layout.addRow(f"Concentración del {orden} grupo de neutrones retardados (C_{i}):", QLineEdit(str(concentracion)))
        layout.addRow("Paso de tiempo (Δt, s):", self.input_dt)
        # Botones de acción
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Aplicar")

        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        layout.addRow(btn_layout)

    def get_values(self):
        try:
            return {
                "condiciones iniciales": {
                    "flujo de neutrones": float(self.input_n0.text()),
                    "concentración grupo neutrones retardados": self.concentraciones,
                    "paso temporal": float(self.input_dt.text())
                }
            }
        except ValueError:
            QMessageBox.critical(self, "Error", "Por favor ingresa valores numéricos válidos.")
            return self.config


# --- Ventana Auxiliar (Parámetros Físicos de la cinética del reactor) ---
class ConfigPFDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Parámetros Físicos del Reactor")
        self.resize(500, 200)

        self.config = current_config or {"parámetros físicos RA4": {"Beta efectivo": 730e-5, "Lambda [s]": 4.7e-5, "lambda_i [s]": [0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87], "fracciones_i": [0.038, 0.213, 0.188, 0.407, 0.128, 0.026]}, "parámetros constructivos RA4": {"Recorrido del núcleo [mm]": 50, "Recorrido de las barras de control [mm]": 250 } }

        layout = QFormLayout(self)

        self.input_beta_eff = QLineEdit(str(self.config["parámetros físicos RA4"]["Beta efectivo"]))
        self.input_LAMBDA = QLineEdit(str(self.config["parámetros físicos RA4"]["Lambda [s]"]))
        self.input_lambda_i = QLineEdit(str(self.config["parámetros físicos RA4"]["lambda_i [s]"]))
        self.input_fracciones_i = QLineEdit(str(self.config["parámetros físicos RA4"]["fracciones_i"]))

        self.input_rec_nuc = QLineEdit(str(self.config["parámetros constructivos RA4"]["Recorrido del núcleo [mm]"]))
        self.input_rec_bc = QLineEdit(str(self.config["parámetros constructivos RA4"]["Recorrido de las barras de control [mm]"]))


        layout.addRow("Beta efectivo del reactor:", self.input_beta_eff)
        layout.addRow("Tiempo de vida medio de los neutrones en el ciclo de reproducción", self.input_LAMBDA)
        lambda_i = self.config["parámetros físicos RA4"]["lambda_i [s]"]
        fracciones_i = self.config["parámetros físicos RA4"]["fracciones_i"]

        for i, (lambdagrupo, fraccion) in enumerate(zip(lambda_i, fracciones_i)):
            layout.addRow(f"Constante de desintegración de los precursores del grupo {i+1} (\\lambda_{i+1}):", QLineEdit(str(lambdagrupo)))
            layout.addRow(f"Fracción de los precursores del grupo {i+1} (C_{i+1}):", QLineEdit(str(fraccion)))

        layout.addRow("Recorrido máximo del núcleo [mm]:", self.input_rec_nuc)
        layout.addRow("Recorrido máximo de las barras de contol [mm]:", self.input_rec_bc)

        # Botones de acción
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Aplicar")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        layout.addRow(btn_layout)

    def get_values(self):
        try:
            return {
                "Beta efectivo del reactor": float(self.input_beta_eff.text()),
                "Tiempo de vida medio de los neutrones en el ciclo de reproducción": float(self.input_LAMBDA.text()),
            }
        except ValueError:
            QMessageBox.critical(self, "Error", "Por favor ingresa valores numéricos válidos.")
            return self.config
