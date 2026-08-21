import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# 1. Definición de las constantes de tiempo y tasas de decaimiento (lambda = 1/tau)
taus = np.array([5.5e-5, 0.01, 0.03, 0.1, 0.3, 1.4, 4.0])
lambdas = 1.0 / taus

# 2. Definición del sistema de EDOs acopladas
def sistema_rigido(t, y):
    """
    Sistema acoplado dy/dt = A * y.
    Matriz A con autovalores -1/tau y un ligero acoplamiento entre variables.
    """
    dydt = np.empty_like(y)
    
    # Términos diagonales (dominados por su respectiva constante de tiempo)
    dydt = -lambdas * y
    
    # Pequeño acoplamiento entre modos contiguos para simular interacción
    dydt[:-1] += 0.05 * lambdas[:-1] * y[1:]
    return dydt

# 3. Jacobiano analítico del sistema
def jacobiano_sistema(t, y):
    """
    Matriz Jacobiana J_ij = df_i / dy_j.
    Proporcionarla analíticamente acelera la convergencia de Newton en Radau.
    """
    J = np.diag(-lambdas)
    np.fill_diagonal(J[:-1, 1:], 0.05 * lambdas[:-1])
    return J

# 4. Condición inicial y ventana de simulación
y0 = np.ones(len(taus))
t_span = (0.0, 10.0)  # De t = 0 a t = 10 s (suficiente para ver tau_max = 4s)

# 5. Configuración de parámetros de control de paso
dt_initial = taus[0] / 5.0     # 1.1e-5 s (basado en tau_min)
dt_max = taus[-1] / 10.0       # 0.4 s (basado en tau_max)

# 6. Ejecución del solver Radau
sol = solve_ivp(
    fun=sistema_rigido,
    t_span=t_span,
    y0=y0,
    method='Radau',
    jac=jacobiano_sistema,      # Pasa el Jacobiano explícito
    first_step=dt_initial,       # Paso inicial conservador para el transitorio rápido
    max_step=dt_max,             # Cota superior para el régimen lento
    rtol=1e-5,                   # Tolerancia relativa
    atol=1e-8,                   # Tolerancia absoluta
    dense_output=True            # Permite interpolación continua si se requiere
)

# --- Impresión de diagnóstico ---
print(f"Éxito: {sol.success}")
print(f"Mensaje del solver: {sol.message}")
print(f"Número total de pasos temporales tomados: {len(sol.t)}")
print(f"Evaluaciones del sistema (f): {sol.nfev}")
print(f"Evaluaciones del Jacobiano (J): {sol.njev}")

# Visualización de la adaptación del paso
dts = np.diff(sol.t)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)

# Evolución de los estados
for i in range(len(taus)):
    ax1.plot(sol.t, sol.y[i], label=f'$\\tau_{{{i+1}}} = {taus[i]}$ s')
ax1.set_ylabel('Estado $y_i(t)$')
ax1.set_yscale('symlog', linthresh=1e-4)
ax1.grid(True, which='both', linestyle='--', alpha=0.5)
ax1.legend(loc='upper right', fontsize='small')
ax1.set_title('Evolución temporal del sistema acoplado')

# Adaptatividad del paso temporal dt
ax2.plot(sol.t[:-1], dts, 'o-', color='crimson', markersize=3, linewidth=1)
ax2.set_xlabel('Tiempo $t$ [s]')
ax2.set_ylabel('Paso temporal $\\Delta t$ [s]')
ax2.set_yscale('log')
ax2.grid(True, which='both', linestyle='--', alpha=0.5)
ax2.set_title('Adaptación del paso temporal por Radau')

plt.tight_layout()
plt.show()
