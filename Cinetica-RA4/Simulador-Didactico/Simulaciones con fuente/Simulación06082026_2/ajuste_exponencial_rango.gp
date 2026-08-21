datafile = "simulacion_RA4_tf1062.14_dt_5ms.csv"
set datafile separator ","
stats datafile using 1 nooutput
N = STATS_records
print sprintf("Total de puntos detectados en el archivo: %d", N)

# Función exponencial con offset: f(t) = A * exp(t/tau)
f(t) = A * exp(t/tau)

# Valores iniciales recomendados para el algoritmo de Levenberg-Marquardt
A = 20000
tau = 16.35
ti = 20

idx_max=212428*p/100
idx_min=idx_max-20000

# Ajuste filtrando únicamente las filas correspondientes al porcentaje actual ($0 es 'every' / número de fila)
fit f(x) datafile using 1:2 every ::idx_min::idx_max via A, tau

# --- CONFIGURACIÓN DEL GRÁFICO ---
set xlabel "Tiempo (t)"
set ylabel "n"
set logscale y
set grid
set key top right box title "Ajustes (% datos)"

# Definir estilo de los puntos de datos
set style data points
set pointsize 0.6

plot datafile using 1:2 title "Datos CSV" with points pt 7 lc rgb "#888888", A  * exp(x/tau)  title "ajuste"   lw 2 lc rgb "#e41a1c"
