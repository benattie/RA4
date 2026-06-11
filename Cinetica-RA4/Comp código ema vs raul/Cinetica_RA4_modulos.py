#Módulos de python
import multiprocessing as mtp
import time as tm


class CineticaPuntual(object):
    '''
    Simula el núcleo de un reactor utilizando las ecuaciones de la cinética puntual con un grupo de energía de neutrones y 6 grupos de neutrones retardados.
    Parámetros:
        -LAM: tiempo entre reproducciones [s]
        -beta_eff: beta efectivo del núcleo
        -lam_i: lista con las constantes de desintegración de cada grupo de precursores [1/s]
        -frac_i: lista con las fracciones (rendimientos) de cada grupo de neutrones retardados
        -deltaT: salto de tiempo entre los pasos de la simulación
        -rho_ini: reactividad inicial del núcleo
        -S_ini: valor inicial de la fuente de neutrones
        -n_ini: valor inicial del flujo de neutrones
        -C_ini: lista con los valores iniciales de concentraciones de cada grupo de precursores
    '''
    def __init__(
            self,
            LAM: float,
            beta_eff: float,
            lam_i: list,
            frac_i: list,
            deltaT: float,
            rho_ini: float,
            S_ini: float,
            n_ini: float,
            C_ini: list
            ):
        #Parámetros del reactor
        self.LAM = LAM
        self.beta_eff = beta_eff
        self.lam_i = lam_i[:]
        self.frac_i = frac_i[:]
        self.beta_i = []
        for i in range(len(self.frac_i)):
            self.beta_i.append(self.frac_i[i]*self.beta_eff)

        self.deltaT = deltaT

        #Valores iniciales
        self.rho = rho_ini #Lo hago de esta manera para distinguir el valor inicial del valor usado
        self.S = S_ini     #así no tengo dos variables para cada uno al mismo tiempo (rho y rho_i por ej)
        self.n = n_ini
        self.C_i = C_ini[:]

        #Espacios comunes en memoria
        self.n_mem = mtp.Value('f', self.n)
        self.rho_mem = mtp.Value('f', self.rho)
        self.S_mem = mtp.Value('f', self.S)

        #Para el "while True" del proceso secundario
        self.stop_event = mtp.Event()

        #Proceso secundario
        self.proc_sist_fis = mtp.Process(
            target=self.proceso_secundario,
            args=(
                self.n_mem,
                self.rho_mem,
                self.S_mem,
                self.C_i,
                self.beta_eff,
                self.LAM,
                self.lam_i,
                self.beta_i,
                self.deltaT,
                self.stop_event
            )
        )
        self.proc_sist_fis.start()
   
    def proceso_secundario(self, n_mem, rho_mem, S_mem, C_ini, beta_eff, LAM, lam_i, beta_i, deltaT, stop_event):
        '''
        Función para el proceso secundario que se encarga de los cálculos para el núcleo.
        Los parámetros n_mem, rho_mem y S_mem son espacios comunes en memoria
        '''
        C = C_ini[:]
        t_ref = tm.time()
        while not stop_event.is_set():
            if (tm.time() - t_ref) > deltaT:
                #print(f"Tiempo entre cálculos: {tm.time() - t_ref}") #Para ver la regularidad del tiempo entre pasos
                t_ref = tm.time()
                dn = (rho_mem.value - beta_eff)/LAM * n_mem.value
                for i in range(len(C)):
                    dn += lam_i[i]*C[i]
                dn += S_mem.value
                n_mem.value += dn*deltaT
                for i in range(len(C)):
                    C[i] += (((beta_i[i]/LAM)*n_mem.value) - (lam_i[i]*C[i]))*deltaT
                #print(f"     Tiempo de cálculo: {tm.time()-t_ref}")
                #print(f"{n_mem.value} - {C}")

    def set_rho(self, r):
        '''
        Actualiza el valor de reactividad usado por el modelo en función de los movimientos que se hagan con los sistemas del reactor
        '''
        self.rho_mem.value = r

    def set_S(self, s):
        '''
        Actualiza el valor de reactividad usado por el modelo en función de los movimientos que se hagan con los sistemas del reactor
        '''
        self.S_mem.value = s

    def get_n(self):
        '''
        Devuelve el valor actual del flujo de neutrones
        '''
        return self.n_mem.value

    def __str__(self):
        return f"Modelo de cinética puntual:\n - Tiempo entre reproducciones: {self.LAM} s\n - Beta efectivo: {self.beta_eff}\n - Precursores:\n    - Grupos: {len(self.lam_i)}\n    - Constantes de desintegración: {self.lam_i}\n    - Fracciones de cada grupo: {self.frac_i}"
