#Módulos de python
import csv
import numpy as np

gpu = None

ejec = True

deltaT = 0.001  # [s]

#Parámetros físicos
#Parámetros del RA4
LAM = 55.62e-6  # [s]
beta_eff = 772e-5

#Valores iniciales
rho_nuc = -5 * beta_eff
rho_BC1 = -0.6 * beta_eff
rho_BC2 = -0.6 * beta_eff
rho_max = 0.28 * beta_eff
rho = rho_max + rho_nuc + rho_BC1 + rho_BC2
S = 1e6

#Tuttle (constantes de los grupos de neutrones retardados)
lam = np.array([0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87], dtype=float)  # [1/s] ctes. de desintegración, del grupo 1 al 6
frac_i = np.array([0.038, 0.213, 0.188, 0.407, 0.128, 0.026], dtype=float)  # [%] fracciones de cada grupo, del 1 al 6
beta_i = frac_i * beta_eff

#Otros valores del RA4
rec_nuc = 50  # [mm]
rec_bc = 250  # [mm]


#Vector de variables. El primero es el flujo, las restantes son los precursores, de C1 a C6
var = np.zeros(7, dtype=float)
var[0] = 1287.5189208984375     #1.2877e3
var[1] = 595893.75              #5.9859e4
var[2] = 1341718.25             #1.3441e5
var[3] = 326782.0               #3.2697e4
var[4] = 261680.28125           #2.6174e4
var[5] = 18282.85546875         #1.8286e3
var[6] = 1343.49462890625       #1.3437e2


class FisicaRA4:
    def __init__(self, deltaT):
        self.deltaT = deltaT
        self._state = {
            "lin1.weight": np.zeros((7, 7), dtype=float),
            "lin1.bias": np.zeros(7, dtype=float),
        }

    def state_dict(self):
        return self._state

    def forward(self, x):
        weights = self._state["lin1.weight"]
        bias = self._state["lin1.bias"]
        dif = weights @ x + bias
        x = x + dif * self.deltaT
        return x

    def __call__(self, x):
        return self.forward(x)


class SistemaFisico():
    def __init__(self, nucleo, b1, b2, fuente):
        self.nucleo = nucleo
        self.b1 = b1
        self.b2 = b2
        self.fuente = fuente
        self.SistRA4 = FisicaRA4(deltaT=deltaT)
        self.SistRA4.state_dict()["lin1.weight"][:, :] = np.zeros((7, 7), dtype=float)
        self.SistRA4.state_dict()["lin1.weight"][0, 0] = ((-5 * 730 * 1e-5) - beta_eff) / LAM
        self.SistRA4.state_dict()["lin1.weight"][0, 1:] = lam
        self.SistRA4.state_dict()["lin1.weight"][1:, 1:] = np.diag(-lam)
        self.SistRA4.state_dict()["lin1.weight"][1:, 0] = beta_i / LAM
        self.SistRA4.state_dict()["lin1.bias"][:] = np.zeros(7, dtype=float)
        self.SistRA4.state_dict()["lin1.bias"][0] = S

    def actualizarEntradas(self):
        #si cambiaron las entradas, seteo una flag para actualizar ro en la
        #proxima iteracion
        self.flag = True

    #Cálculo de la evolución del sistema con el modelo en NumPy
    def calcPaso(self):
        global var
        if self.flag:
            self.get_rho()
            self.flag = False
        var = self.SistRA4(var)
        return float(var[0])  # miro reactividad

    #Funciones para actualizar los parámetros del modelo en caso que haya algún movimiento de fuente o reactividad
    #tipo callback
    def get_rho(self):
        rho = rho_max + ((5 - self.nucleo.getPos()) / 5) * rho_nuc + ((25 - self.b1.getPos()) / 25) * rho_BC1 + ((25 - self.b2.getPos()) / 25) * rho_BC2
        self.SistRA4.state_dict()["lin1.weight"][0, 0] = ((rho) - beta_eff) / LAM

    def getReactividad(self):
        global var
        return float(var[0])


if __name__ == "__main__":
    flag = False
    SistRA4 = FisicaRA4(deltaT=deltaT)
    SistRA4.state_dict()["lin1.weight"][:, :] = np.zeros((7, 7), dtype=float)
    SistRA4.state_dict()["lin1.weight"][0, 0] = ((rho_max) - beta_eff) / LAM # ((-5 * 730 * 1e-5) - beta_eff) / LAM
    SistRA4.state_dict()["lin1.weight"][0, 1:] = lam
    SistRA4.state_dict()["lin1.weight"][1:, 1:] = np.diag(-lam)
    SistRA4.state_dict()["lin1.weight"][1:, 0] = beta_i / LAM
    SistRA4.state_dict()["lin1.bias"][:] = np.zeros(7, dtype=float)
    SistRA4.state_dict()["lin1.bias"][0] = S

    # var = SistRA4(var)
    # print(var)

    t = 0
    contador = 0
    with open('resultados_sistema.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['t', 'phi'])
        while t < 1200:
            var = SistRA4(var)
            contador += 1
            if contador % 500 == 0:
                writer.writerow([t, var[0]])
            t += 0.001
