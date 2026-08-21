import numpy as np

# --- FUNCIONES AUXILIARES
# Chequea la decada para actualizar la gráfica
def get_current_decade(val, thresh):
    if val == 0:
        return 0
    # Determine base-10 decade bounds
    magnitude = np.floor(np.log10(np.abs(val)))
    decade_bound = 10 ** (magnitude)

    # Preserve the sign and return appropriate boundary
    bound = decade_bound if val > 0 else -decade_bound
    return max(bound, thresh) if val > 0 else min(bound, -thresh)
