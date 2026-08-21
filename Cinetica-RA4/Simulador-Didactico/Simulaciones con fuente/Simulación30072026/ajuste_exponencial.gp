# ==============================================================================
# SCRIPT DE GNUPLOT: Ajuste Exponencial por Porcentajes de Datos
# ==============================================================================

# --- CONFIGURACIÓN DE ENTRADA Y SALIDA ---
datafile = "simulacion_RA4_tf1062.14_dt_5ms.csv"          # Nombre de tu archivo CSV
output_png = "resultado_ajustes.png"
output_txt = "resultados_ajuste.txt"

# Separador de campos del CSV (si tu CSV usa comas; si usa punto y coma, cambia a ';')
set datafile separator ","

# --- DETERMINACIÓN DEL NÚMERO TOTAL DE PUNTOS ---
# Usamos 'stats' en la columna 1 para obtener N (número total de datos válidos)
stats datafile using 1 nooutput
N = STATS_records

print sprintf("Total de puntos detectados en el archivo: %d", N)

# --- MODELO DE AJUSTE ---
# Función exponencial: f(t) = A * exp(t/tau)
f(t) = A * exp(t/tau)

# Valores iniciales recomendados para el algoritmo de Levenberg-Marquardt
A = 40000
tau = 16.35

# --- LISTA DE PORCENTAJES Y ARCHIVOS TEMPORALES ---
porcentajes = "5 10 20 40 60 80 100"

# Archivo de texto para guardar los resultados finales
set print output_txt
print "================================================================================"
print "                RESULTADOS DEL AJUSTE EXPONENCIAL POR PORCENTAJE                "
print "================================================================================"
print sprintf("Archivo de datos: %s", datafile)
print sprintf("Total de registros (100%%): %d", N)
print "Modelo ajustado: f(t) = A * exp(t/tau)"
print "--------------------------------------------------------------------------------"
print sprintf("%-6s | %-8s | %-16s | %-16s | %-16s | %-12s | %-8s", "Porc %", "Puntos", "A +- dA", "tau +- dtau", "Chi^2 Red", "WSSR")
print "--------------------------------------------------------------------------------"
set print  # Restablece la salida por consola para la ejecución de los fits

# --- BUCLE DE AJUSTES ---
# Ajustamos secuencialmente y guardamos las funciones resultantes en variables o archivos
do for [p in porcentajes] {
    p_num = p + 0.0

    # Índice inicial (desde el final hacia el principio)
    # $0 en gnuplot es el índice de línea (0 a N - 1)
    min_idx = N - int(N * p_num / 100.0)
    if (min_idx < 0) { min_idx = 0 }

    # Reinicializamos parámetros de ajuste
    A = 40000
    tau = 16.35

    # Ajuste filtrando únicamente las filas correspondientes al porcentaje actual ($0 es 'every' / número de fila)
    fit f(x) datafile using 1:($0 >= min_idx ? $2 : 1/0) via A, tau

    # Criterios de bondad de ajuste de Gnuplot
    chi2_red = FIT_NDF > 0 ? FIT_STDFIT**2 : 1/0
    wssr = FIT_WSSR

    # Guardar resultados en el archivo de texto
    set print output_txt append
    print sprintf("%-6d | %-8d | %8.4e +- %-7.1e | %8.4e +- %-7.1e | %8.4e +- %-7.1e | %-12.4e | %-8.4e",p_num, min_idx, A, A_err, tau, tau_err, chi2_red, wssr)
    set print

    # Guardar los valores de los parámetros para graficarlos luego
    eval(sprintf("A_%d = %g; tau_%d = %g;", int(p_num), A, int(p_num), tau))
}

set print output_txt append
print "================================================================================"
set print

print sprintf("\n-> Los resultados textuales han sido guardados en '%s'.", output_txt)

# --- CONFIGURACIÓN DEL GRÁFICO ---
set title "Ajustes de Exponencial Decreciente según % de Datos"
set xlabel "Tiempo (t)"
set ylabel "n"
set logscale y
set grid
set key top right box title "Ajustes (% datos)"

# Definir estilo de los puntos de datos
set style data points
set pointsize 0.6

# --- SALIDA A ARCHIVO PNG ---
set terminal pngcairo size 1200,800 font "Sans,11" linewidth 1.5
set output output_png

plot datafile using 1:2 title "Datos CSV" with points pt 7 lc rgb "#888888", \
     A_5  * exp(x/tau_5)   title "5%"   lw 2 lc rgb "#e41a1c"

unset output
print sprintf("-> La gráfica ha sido guardada en '%s'.", output_png)

# --- SALIDA EN PANTALLA (INTERACTIVA) ---
# Se utiliza el terminal qt / wxt / x11 según esté disponible en tu sistema
set terminal qt title "Gráfica de Ajustes Exponenciales"
replot
