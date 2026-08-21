import numpy as np
from scipy.integrate import Radau

# modulos para trabajar mutiproceso
import time
import queue
import threading
from collections import deque
from PyQt6.QtCore import QThread, QTimer, Qt

# Hilo de la simulacion
class SimulationThread(QThread):
    def __init__(self, writer_queue, config_param_fisicos, config_cond_iniciales, config, parent=None):
        super().__init__(parent)
        self.writer_queue = writer_queue
        self.lock = threading.Lock()

        # Buffers acotados (Ring Buffers de tamaño 15 000) para evitar uso excesivo de memoria y pausas de GC
        self.t_data = deque(maxlen=15000)
        self.n_data = deque(maxlen=15000)

        self._running = False
        self.solver = None

        # Carga inicial de parámetros físicos y configuración mediante método dedicado
        self.load_from_config(config_param_fisicos or {}, config_cond_iniciales or {}, config or {})

    def load_from_config(self, config_param_fisicos, config_cond_iniciales, config):
        """Carga/actualiza parámetros físicos y condiciones iniciales desde otra fuente, función o clase."""
        with self.lock:
            # Parámetros físicos dinámicos. Posición del nucleo y de las barras de control (valores iniciales para los sliders)
            self.pos_nucleo = config["pos nucleo"]   # nucleo
            self.pos_fuente = config["pos fuente"]   # fuente
            self.pos_BC1 = config["pos BC1"]   # barra de control 1
            self.pos_BC2 = config["pos BC2"]   # barra de control 2

            # Parámetros físicos estáticos. Beta efectivo del reactor, tiempo de decaimiento de los neutrones prompt, y de los 6 grupos de reactores retardados
            self.beta_eff = config_param_fisicos["parámetros físicos RA4"]["Beta efectivo"]
            self.LAMBDA = config_param_fisicos["parámetros físicos RA4"]["Lambda [s]"]
            self.lambda_i = np.array(config_param_fisicos["parámetros físicos RA4"]["lambda_i [s^-1]"])
            self.fracciones_i = np.array(config_param_fisicos["parámetros físicos RA4"]["fracciones_i"])

            # Paso temporal máximo (al principio siempre voy a usar un paso chico
            self.dt = config_cond_iniciales["condiciones iniciales"]["paso temporal"]

            # Condiciones iniciales
            self.t = 0.0
            self.n = config_cond_iniciales["condiciones iniciales"]["densidad de neutrones"]
            self.Ci = np.array(config_cond_iniciales["condiciones iniciales"]["concentración grupo neutrones retardados"])
            self.y_actual = np.concatenate(([self.n], self.Ci))

            self.t_data.clear()
            self.n_data.clear()

    def _obtener_reactividad(self, beta_eff, pos_nucleo, pos_BC1, pos_BC2):
        """
        Define la reactividad en función del tiempo.
        """
        rho_nuc = -5*beta_eff
        rho_BC1 = -0.6*beta_eff
        rho_BC2 = -0.6*beta_eff
        rho_max = 0.31*beta_eff
        rho = (
            rho_max + ((100 - pos_nucleo)/100) * rho_nuc
            + ((100 - pos_BC1)/100) * rho_BC1 + ((100 - pos_BC2)/100) * rho_BC2
        )

        return rho

    def _cinetica_puntual(self, t, y, beta_eff, LAMBDA, lambda_i, fracciones_i, pos_nucleo, pos_BC1, pos_BC2, pos_fuente):
        """
        y[0] = n(t) (Densidad/Potencia de neutrones)
        y[1:7] = C_i(t) (Concentración de los 6 grupos de precursores)
        """
        n = y[0]
        C = y[1:]

        # Obtengo la reactividad del núcleo
        with self.lock:
            # Neutrones aportados por la fuente
            # S_0 = 1e6
            # S = (0.25 + 0.75 * self.pos_fuente / 100) * S_0
            rho = self._obtener_reactividad(beta_eff, pos_nucleo, pos_BC1, pos_BC2)

        S = 0.0
        # Ecuación para la densidad de neutrones dn/dt
        dn_dt = ((rho - beta_eff) / LAMBDA) * n + np.sum(lambda_i * C) + S
        # Ecuaciones para los 6 grupos de precursores dC_i/dt
        beta_i = beta_eff * fracciones_i
        dC_dt = (beta_i / LAMBDA) * n - lambda_i * C

        # Devolvemos un único arreglo con todas las derivadas
        return np.concatenate(([dn_dt], dC_dt))

    def _cinetica_puntual_jacobiano(self, t, y, beta_eff, LAMBDA, lambda_i, fracciones_i, pos_nucleo, pos_BC1, pos_BC2, pos_fuente):
        # No me queda claro si tengo que crear el jacobiano cada vez que llamo a la función
        jacobiano = np.zeros((7, 7))

        # Obtengo la reactividad del núcleo
        with self.lock:
            # Neutrones aportados por la fuente
            # S_0 = 1e6
            # S = (0.25 + 0.75 * self.pos_fuente / 100) * S_0
            rho = self._obtener_reactividad(beta_eff, pos_nucleo, pos_BC1, pos_BC2)

        S = 0.0
        # Primera fila: derivación respecto a n y a los C_i
        jacobiano[0, 0] = (rho - beta_eff) / LAMBDA
        jacobiano[0, 1:] = lambda_i

        # Primera columna (filas 1 a 6): d(dC_i/dt) / dn
        beta_i = beta_eff * fracciones_i
        jacobiano[1:, 0] = beta_i / LAMBDA

        # Diagonal secundaria (filas 1 a 6, cols 1 a 6): d(dC_i/dt) / dC_i
        np.fill_diagonal(jacobiano[1:, 1:], -lambda_i)

        return jacobiano

    def init_solver(self):
        with self.lock:
            y0 = self.y_actual.copy()
            t0 = self.t
            dt = self.dt

            cinetica_puntual_con_args = lambda t, y: self._cinetica_puntual(
                t, y,
                self.beta_eff, self.LAMBDA, self.lambda_i, self.fracciones_i,
                self.pos_nucleo, self.pos_BC1, self.pos_BC2, self.pos_fuente)

            jacobiano_con_args = lambda t, y: self._cinetica_puntual_jacobiano(
                t, y,
                self.beta_eff, self.LAMBDA, self.lambda_i, self.fracciones_i,
                self.pos_nucleo, self.pos_BC1, self.pos_BC2, self.pos_fuente)

        self.solver = Radau(
            cinetica_puntual_con_args,
            t0, y0,
            t_bound=np.inf,
            max_step=dt,
            rtol=1e-8, # Tolerancia mínima para hacer el paso siguiente de la simulación. Se calcula en relación al valor de la variable. Controla la cantidad de cifras significativas
            atol=1e-10, # Umbral fijo de tolerancia, se aplica sin importar el valor de la variable. Asegura convergencia si la variable es muy chica
            jac=jacobiano_con_args,
        )

    def update_params(self, pos_nucleo, pos_fuente, pos_BC1, pos_BC2):
        with self.lock:
            self.pos_nucleo, self.pos_fuente, self.pos_BC1, self.pos_BC2  = pos_nucleo, pos_fuente, pos_BC1, pos_BC2

    def set_config(self, config_param_fisicos):
        with self.lock:
            self.dt = config_param_fisicos.get("dt", 0.001)

    def reset_state(self, config_cond_iniciales, config_param_fisicos):
        with self.lock:
            # Paso temporal máximo (al principio siempre voy a usar un paso chico
            self.dt = config_cond_iniciales["condiciones iniciales"]["paso temporal"]

            # Condiciones iniciales
            self.t = 0.0
            self.n = config_cond_iniciales["condiciones iniciales"]["densidad de neutrones"]
            self.Ci = np.array(config_cond_iniciales["condiciones iniciales"]["concentración grupo neutrones retardados"])
            self.y_actual = np.concatenate(([self.n], self.Ci))

            self.t_data.clear()
            self.n_data.clear()
        self.init_solver()

    def get_plot_data(self):
        with self.lock:
            return (list(self.t_data), list(self.n_data), self.t, self.y_actual[0])

    def run(self):
        self._running = True
        if self.solver is None:
            self.init_solver()

        last_time = time.perf_counter()
        accumulator = 0.0

        while self._running:
            now = time.perf_counter()
            elapsed = now - last_time
            last_time = now

            if elapsed > 0.2:
                elapsed = 0.2 # Previene un "salto de tiempo gigante" si la PC se congela

            accumulator += elapsed

            with self.lock:
                dt = self.dt

            if accumulator >= dt:
                n_steps = int(accumulator // dt)
                if n_steps > 1000:
                    n_steps = 1000

                advance_time = n_steps * dt
                target_t = self.t + advance_time
                try:
                    # Avanzar el solver Radau hasta superar target_t
                    while self.solver.t < target_t:
                        self.solver.step()

                    # Evaluación Vectorizada de Alta Velocidad (1 sola llamada a dense_output)
                    sol = self.solver.dense_output()
                    t_eval = np.linspace(self.t + dt, target_t, n_steps)
                    y_eval = sol(t_eval)  # Matriz NumPy 6 x n_steps


                    # print(t_eval, y_eval)

                    self.t = target_t
                    self.y_actual = y_eval[:, -1]
                    accumulator -= advance_time

                    with self.lock:
                        pos_nucleo, pos_fuente, pos_BC1, pos_BC2 = self.pos_nucleo, self.pos_fuente, self.pos_BC1, self.pos_BC2

                    batch_samples = []
                    for i in range(n_steps):
                        t_i = float(t_eval[i])
                        n_i = y_eval[0, i]
                        batch_samples.append([
                            round(t_i, 6), round(n_i, 6),
                            pos_nucleo, pos_fuente,
                            pos_BC1, pos_BC2
                        ])
                        with self.lock:
                            self.t_data.append(t_i)
                            self.n_data.append(n_i)

                    self.writer_queue.put(batch_samples)
                except Exception:
                    pass

            time.sleep(0.001)

    def stop(self):
        self._running = False
        self.wait()
