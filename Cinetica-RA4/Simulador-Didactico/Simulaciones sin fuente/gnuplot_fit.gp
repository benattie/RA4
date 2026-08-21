# =========================================================
# CONFIGURACIÓN DE ARCHIVOS Y PARÁMETROS
# =========================================================
set datafile separator ","
archivo_datos = 'simulacion_RA4_0p31.csv'
archivo_salida = 'evolucion_tau_ventana_0p31.dat'

f(x) = A * exp(x / tau)

A = 2
tau = 20.0

set fit quiet logfile 'fit_0p31.log'

# =========================================================
# PARÁMETROS DE LA VENTANA
# =========================================================
ancho_ventana = 25.0   # Tamaño W de la ventana en segundos
t_inicio = 25.0        # t_max inicial (debe ser >= ancho_ventana)
t_final = 250.0        # Tiempo total de tus datos
paso = 2.0             # Incremento de tiempo por iteración

# =========================================================
# BUCLE CON AMBAS COTAS EVOLUTIVAS
# =========================================================
set print archivo_salida
print "# t_min t_max tau A"

do for [t_max = t_inicio : t_final : paso] {
    
    # Calcular la cota inferior para esta iteración
    t_min = t_max - ancho_ventana
    
    # Filtro doble: t_min <= t <= t_max
    fit f(x) archivo_datos using 1:($1 >= t_min && $1 <= t_max ? $2 : 1/0) via A, tau
    
    # Guardar: t_min, t_max, tau y A
    print sprintf("%.2f %.2f %.6f %.6f", t_min, t_max, tau, A)
}

set print

# =========================================================
# GRAFICAR LA EVOLUCIÓN
# =========================================================
#set terminal pngcairo size 800,600 enhanced font 'sans,12'
#set output 'evolucion_tau_ventana.png'

#set title sprintf("Evolución de {/Symbol t}(t) - Ventana móvil de %.0f s", ancho_ventana)
#set xlabel "Tiempo final de la ventana t_{max} (s)"
#set ylabel "Tiempo característico {/Symbol t} (s)"
#set grid

# Usamos la columna 2 (t_max) vs columna 3 (tau)
#plot archivo_salida using 2:3 with linespoints lw 2 pt 7 ps 0.6 title "{/Symbol t} local"
#plot 'evolucion_tau_ventana_0p31.dat' u 2:3 w lp lw 2 pt 7 ps 0.6 title '$0,31', 'evolucion_tau_ventana_0p275.dat' u 2:3 w lp lw 2 pt 7 ps 0.6 t '$0,275', 'evolucion_tau_ventana_0p25.dat' u 2:3 w lp lw 2 pt 7 ps 0.6 t '$0,25'
