Se presenta un códifgo para simular la evolución temporal de la población de neutrones en un reactor nuclear. Para ello se emplean **Ecuaciones de Cinética Puntual**.

Este modelo asume que la distribución espacial del flujo de neutrones se mantiene constante.

El comportamiento del reactor está gobernado por un sistema de ecuaciones diferenciales acopladas que separan a los neutrones en dos categorías críticas: los **neutrones inmediatos** (*prompt*), que se liberan instantáneamente en la fisión, y los **neutrones retardados** (*delayed*), que son emitidos segundos o minutos después por el decaimiento de los productos de fisión (llamados precursores):

$$\frac{dn(t)}{dt} = \frac{\rho(t) - \beta}{\Lambda} n(t) + \sum_{i=1}^{6} \lambda_i C_i(t)$$

$$\frac{dC_i(t)}{dt} = \frac{\beta_i}{\Lambda} n(t) - \lambda_i C_i(t) \quad \text{para } i = 1, 2, \dots, 6$$

Donde:

* **$n(t)$**: Densidad de neutrones en el núcleo en el instante $t$. Es directamente proporcional a la potencia térmica del reactor.
* **$\rho(t)$**: **Reactividad** del reactor. Es una medida de la desviación del estado crítico ($\rho = 0$). Si $\rho > 0$ el reactor es supercrítico (la potencia sube), y si $\rho < 0$ es subcrítico (la potencia baja).
* **$\beta_i$**: Fracción de neutrones retardados pertenecientes al grupo $i$.
* **$\beta$**: Fracción total de neutrones retardados ($\beta = \sum_{i=1}^{6} \beta_i$). Aunque es un valor pequeño (típicamente entre $0.003$ y $0.007$ dependiendo del combustible como U-235 o Pu-239), es lo que hace que el reactor sea controlable mecánicamente.
* **$\Lambda$**: Tiempo de generación de neutrones inmediatos. Es el tiempo promedio que transcurre desde que nace un neutrón hasta que produce una nueva fisión. Su valor es extremadamente corto (del orden de $10^{-4}$ a $10^{-7}$ segundos).
* **$C_i(t)$**: Concentración del grupo $i$ de núcleos precursores de neutrones retardados.
* **$\lambda_i$**: Constante de decaimiento del grupo de precursores $i$ (inversa del tiempo de vida medio del grupo).

En este modelo se trabaja con 6 grupos de neutrones.

Aclaraciones:
1. **El término inmediato $\left(\frac{\rho - \beta}{\Lambda}\right)n(t)$**: Si la reactividad $\rho$ alcanza o supera a $\beta$ ($\rho \ge \beta$), el reactor se vuelve **crítico por neutrones inmediatos** (*prompt critical*). En este escenario, la población de neutrones crece de forma exponencial con una constante de tiempo basada en $\Lambda$ (microsegundos), provocando un transitorio violento e incontrolable. En operación normal, siempre se opera con $\rho < \beta$.
2. **El término retardado $\sum \lambda_i C_i(t)$**: Al mantener $\rho < \beta$, el balance para que el reactor siga funcionando depende enteramente del decaimiento de los precursores. Esto estira el tiempo de respuesta del reactor a una escala de segundos o minutos, permitiendo que los sistemas de control mecánicos (barras de control) actúen a tiempo.
