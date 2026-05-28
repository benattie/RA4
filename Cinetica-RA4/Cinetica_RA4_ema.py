import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# =============================================================================
# 1. PARÁMETROS NUCLEARES (Datos típicos para U-235 en reactor térmico)
# =============================================================================
LAMBDA = 4.7e-5  # Tiempo de generación de neutrones inmediatos [s]

# Constantes de decaimiento (lambda_i) para 6 grupos [s^-1]
lambda_i = np.array([0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87])

# Fracciones de neutrones retardados (beta_i) para 6 grupos
beta_i = np.array([0.038, 0.213, 0.188, 0.407, 0.128, 0.026])
beta = np.sum(beta_i)  # Fracción total de neutrones retardados

# =============================================================================
# 2. DINÁMICA DE LA REACTIVIDAD rho(t)
# =============================================================================
def obtener_reactividad(t):
    """
    Define la reactividad en función del tiempo.
    Simula una inserción de reactividad tipo escalón a los 2 segundos.
    """
    if t < 2.0:
        return 0.0  # Reactor inicialmente crítico estacionario
    else:
        # Insertamos una reactividad menor a beta (sub-prompt critical)
        return 0.0025

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
    dn_dt = ((rho - beta) / LAMBDA) * n + np.sum(lambda_i * C)

    # Ecuaciones para los 6 grupos de precursores dC_i/dt
    dC_dt = (beta_i / LAMBDA) * n - lambda_i * C

    # Devolvemos un único arreglo con todas las derivadas
    return np.concatenate(([dn_dt], dC_dt))

# =============================================================================
# 4. CONDICIONES INICIALES Y CONFIGURACIÓN DE LA SIMULACIÓN
# =============================================================================
# Fijamos una potencia inicial normalizada n0 = 1.0
n0 = 1.0

# Para comenzar en estado estacionario (dn/dt = 0 y dC_i/dt = 0),
# la concentración inicial de precursores debe equilibrar la producción:
C0 = (beta_i / (LAMBDA * lambda_i)) * n0

# Vector de estado inicial completo
y0 = np.concatenate(([n0], C0))

# Tiempo de inicio y fin de la simulación [segundos]
t_span = (0.0, 15.0)
t_eval = np.linspace(t_span[0], t_span[1], 1000)

# =============================================================================
# 5. RESOLUCIÓN NUMÉRICA MEDIANTE MÉTODO IMPLÍCITO (Radau)
# =============================================================================
# Usamos el método 'Radau' por la alta rigidez del sistema.
solucion = solve_ivp(cinetica_puntual, t_span, y0, method='Radau', t_eval=t_eval)

# =============================================================================
# 6. PROCESAMIENTO Y GRÁFICO DE RESULTADOS
# =============================================================================
t = solucion.t
n = solucion.y[0]

plt.figure(figsize=(10, 5))
plt.plot(t, n, label='Potencia de neutrones $n(t)$', color='tab:blue', linewidth=2)
plt.axvline(x=2.0, color='tab:red', linestyle='--', label='Inserción de reactividad ($t=2s$)')

plt.title('Simulación de la Cinética de un Reactor Nuclear (Método Implícito)')
plt.xlabel('Tiempo [segundos]')
plt.ylabel('Potencia Normalizada ($n/n_0$)')
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend()
plt.tight_layout()
plt.show()
