# modulos de mi codigo
import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# modulos del codigo de raul
import tkinter as tk
import multiprocessing as mtp
import threading as thr
import time as tm
import os

from Cinetica_RA4_modulos import CineticaPuntual # codigo de simulación de la cinética del reactor de raul. Lo uso para control

if __name__ == '__main__':
    mtp.freeze_support()
    __spec__ = None  # evita el error AttributeError: module '__main__' has no attribute '__spec__'

    # =============================================================================
    # 1. PARÁMETROS NUCLEARES (Datos típicos para U-235 en reactor térmico)
    # =============================================================================
    LAMBDA = 4.7e-5  # Tiempo de generación de neutrones inmediatos [s]
    beta_eff = 730e-5

    # Constantes de decaimiento (lambda_i) para 6 grupos [s^-1]
    lambda_i = np.array([0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87])

    # Fracciones de neutrones retardados (beta_i) para 6 grupos
    frac_i = np.array([0.038, 0.213, 0.188, 0.407, 0.128, 0.026]) # Fracción total de neutrones retardados
    beta_i = frac_i*beta_eff

    # =============================================================================
    # 2. DINÁMICA DE LA REACTIVIDAD (propios del RA4)
    # =============================================================================
    rho_dolar = np.array([-5, -0.6, -0.6, 0.3]) # pesos en dolares de las reactividades del (nucleo, barra de contro 1, barra de control 2, reactividad máxima)
    S = 0 # fuente externa de neutrones

    #Valores los primeros dos segundos
    pesos = np.array([1, 1, 1, 1]) # esta configuración supone que estamos en reactividad máxima del nucleo, sin barras de control
    rho_02 = np.sum(beta_eff*rho_dolar*pesos)
    rho_02 = rho_02 + S

    #Valores desde los dos segundos
    pesos = np.array([0, 1, 1, 1]) # esta configuración supone que estamos en reactividad máxima del nucleo, sin barras de control
    rho_2inf = np.sum(beta_eff*rho_dolar*pesos)
    rho_2inf = rho_2inf + S

    def obtener_reactividad(t):
        """
        Define la reactividad en función del tiempo.
        Simula una inserción de reactividad tipo escalón a los 2 segundos.
        """
        if t < 2.0:
            return rho_02
        else:
            return rho_2inf

    # =============================================================================
    # 3. SISTEMA DE ECUACIONES DIFERENCIALES
    # =============================================================================
    def cinetica_puntual(t, y):
        """
        y[0] = n(t) (Densidad/Potencia de neutrones)
        y[1:7] = C_i(t) (Concentración de los 6 grupos de precursores)
        """
        n = y[0]
        C = y[1:]

        rho = obtener_reactividad(t)

        # Ecuación para la densidad de neutrones dn/dt
        dn_dt = ((rho - beta_eff) / LAMBDA) * n + np.sum(lambda_i * C)

        # Ecuaciones para los 6 grupos de precursores dC_i/dt
        dC_dt = (beta_i / LAMBDA) * n - lambda_i * C

        # Devolvemos un único arreglo con todas las derivadas
        return np.concatenate(([dn_dt], dC_dt))

    # =============================================================================
    # 4. CONDICIONES INICIALES Y CONFIGURACIÓN DE LA SIMULACIÓN
    # =============================================================================
    # Pongo el valor inicial del codigo de raul
    #n0 = 1.0
    n0 = 1091.246826171875

    # Para comenzar en estado estacionario (dn/dt = 0 y dC_i/dt = 0),
    # la concentración inicial de precursores debe equilibrar la producción:
    #C0 = (beta_i / (LAMBDA * lambda_i)) * n0

    # valores inciales del codigo de raul
    C0 = np.array([507140.0060000771,
        1138854.7486543525,
        277081.8028195465,
        221810.4566764686,
        15496.368303572082,
        1138.7027742450227
    ])

    # Vector de estado inicial completo
    y0 = np.concatenate(([n0], C0))

    # Tiempo de inicio y fin de la simulación [segundos]
    t_span = (0.0, 15.0)
    t_eval = np.linspace(t_span[0], t_span[1], 15001) # esto da un intervalo de 1 ms

    # =============================================================================
    # 5. RESOLUCIÓN NUMÉRICA MEDIANTE MÉTODO IMPLÍCITO (Radau)
    # =============================================================================
    # Usamos el método 'Radau' por la alta rigidez del sistema.
    print("Inicio mi código")
    solucion = solve_ivp(cinetica_puntual, t_span, y0, method='Radau', t_eval=t_eval)

    # =============================================================================
    # 7. LLAMO A LA FUNCIÓN DE RAÚL
    # =============================================================================
    print("Inicio el código de Raúl")
    deltaT = 0.001 #[s]

    #Otros valores del RA4
    rec_nuc = 50 #[mm]
    rec_bc = 250 #[mm]

    #Vector de variables. El primero es el flujo, las restantes son los precursores, de C1 a C6
    n_0 = 1091.246826171875     #1.2877e3
    C_0 = [
        507140.0060000771,
        1138854.7486543525,
        277081.8028195465,
        221810.4566764686,
        15496.368303572082,
        1138.7027742450227
    ]

    nucleo = CineticaPuntual(LAMBDA, beta_eff, lambda_i, frac_i, deltaT, rho_02, S, n_0, C_0) # inicio el proceso del codigo de raul

    n_t = []
    t_run = 0
    while t_run < 2:
        n_t.append(nucleo.get_n())
        t_run = t_run + deltaT
        tm.sleep(deltaT)

    nucleo.set_rho(rho_2inf)

    while (t_run >=2 and t_run < t_span[1]):
        n_t.append(nucleo.get_n())
        t_run = t_run + deltaT
        tm.sleep(deltaT)

    n_t_raul = np.array(n_t)

    # =============================================================================
    # 6. PROCESAMIENTO Y GRÁFICO DE RESULTADOS
    # =============================================================================
    t = solucion.t
    n = solucion.y[0]
    print("Guardando las salidas")
    error = n - n_t_raul
    out = np.vstack((t, n, n_t_raul, error)).T
    np.savetxt('salida.dat', out, delimiter=",",fmt='%1.4e')

    print("Graficando las salidas")
    plt.figure(figsize=(10, 5))
    plt.plot(t, n, label='Potencia de neutrones $n(t)$', color='tab:blue', linewidth=2)
    plt.plot(t, n_t_raul, label='Potencia de neutrones segun el código de Raúl $n(t)$', color='tab:red', linewidth=2)
    plt.axvline(x=2.0, color='tab:red', linestyle='--', label='Inserción de reactividad ($t=2s$)')

    plt.title('Simulación de la Cinética de un Reactor Nuclear (Método Implícito)')
    plt.xlabel('Tiempo [segundos]')
    plt.ylabel('Potencia Normalizada ($n/n_0$)')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()
