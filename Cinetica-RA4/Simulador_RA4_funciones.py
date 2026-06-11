import numpy as np

# --- SISTEMA FÍSICO (Ecuación Diferencial) ---
def obtener_reactividad(beta_eff, pos_nucleo, pos_BC1, pos_BC2):
        """
        Define la reactividad en función del tiempo.
        """
        rho_nuc = -5*beta_eff
        rho_BC1 = -0.6*beta_eff
        rho_BC2 = -0.6*beta_eff
        rho_max = 0.3*beta_eff
        S = 1e6
        rho = rho_max + ((100 - pos_nucleo)/100) * rho_nuc + ((100 - pos_BC1)/100) * rho_BC1 + ((100 - pos_BC2)/100) * rho_BC2

        return rho


def cinetica_puntual(t, y, beta_eff, LAMBDA, lambda_i, fracciones_i, pos_nucleo, pos_BC1, pos_BC2):
        """
        y[0] = n(t) (Densidad/Potencia de neutrones)
        y[1:7] = C_i(t) (Concentración de los 6 grupos de precursores)
        """
        n = y[0]
        C = y[1:]

        # Obtengo la reactividad del núcleo
        rho = obtener_reactividad(beta_eff, pos_nucleo, pos_BC1, pos_BC2)

        # Ecuación para la densidad de neutrones dn/dt
        dn_dt = ((rho - beta_eff) / LAMBDA) * n + np.sum(lambda_i * C)
        # Ecuaciones para los 6 grupos de precursores dC_i/dt
        beta_i = beta_eff * fracciones_i
        dC_dt = (beta_i / LAMBDA) * n - lambda_i * C

        # Devolvemos un único arreglo con todas las derivadas
        return np.concatenate(([dn_dt], dC_dt))
