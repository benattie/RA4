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
        rho = rho_max + ((100 - pos_nucleo)/100) * rho_nuc + ((100 - pos_BC1)/100) * rho_BC1 + ((100 - pos_BC2)/100) * rho_BC2

        return rho


def cinetica_puntual(t, y, beta_eff, LAMBDA, lambda_i, fracciones_i, pos_nucleo, pos_BC1, pos_BC2, pos_fuente):
        """
        y[0] = n(t) (Densidad/Potencia de neutrones)
        y[1:7] = C_i(t) (Concentración de los 6 grupos de precursores)
        """
        n = y[0]
        C = y[1:]

        # Concentración de neutrones aportada por la fuente
        S_0 = 1e6
        S = (0.25 + 0.75 * pos_fuente / 100) * S_0

        # Obtengo la reactividad del núcleo
        rho = obtener_reactividad(beta_eff, pos_nucleo, pos_BC1, pos_BC2)

        # Ecuación para la densidad de neutrones dn/dt
        dn_dt = ((rho - beta_eff) / LAMBDA) * n + np.sum(lambda_i * C) + S
        # Ecuaciones para los 6 grupos de precursores dC_i/dt
        beta_i = beta_eff * fracciones_i
        dC_dt = (beta_i / LAMBDA) * n - lambda_i * C

        # Devolvemos un único arreglo con todas las derivadas
        return np.concatenate(([dn_dt], dC_dt))


# --- FUNCIONES AUXILIARES (ver si las dejo acá o las mando para otro lado) ---
def get_current_decade(val, thresh):
    if val == 0:
        return 0
    # Determine base-10 decade bounds
    magnitude = np.floor(np.log10(np.abs(val)))
    decade_bound = 10 ** (magnitude)

    # Preserve the sign and return appropriate boundary
    bound = decade_bound if val > 0 else -decade_bound
    return max(bound, thresh) if val > 0 else min(bound, -thresh)
