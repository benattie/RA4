#Módulos de python
import tkinter as tk
import torch as trc
import threading as thr
import time as tm
import os

gpu = None

ejec = True

deltaT = 0.01 #[s] 

#Parámetros físicos
#Parámetros del RA4
LAM = 47e-5 #[s]
beta_eff = 730e-5

#Valores iniciales
rho_nuc = -5*beta_eff
rho_BC1 = -0.6*beta_eff
rho_BC2 = -0.6*beta_eff
rho_max = 0.3*beta_eff
rho = rho_max + rho_nuc + rho_BC1 + rho_BC2
S = 1e5

#Tuttle (constantes de los grupos de neutrones retardados)
lam = trc.tensor([0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87], device=gpu) #[1/s] ctes. de desintegración, del grupo 1 al 6
frac_i = trc.tensor([0.038, 0.213, 0.188, 0.407, 0.128, 0.026], device=gpu) #[%] fracciones de cada grupo, del 1 al 6
beta_i = frac_i*beta_eff

#Otros valores del RA4
rec_nuc = 50 #[mm]
rec_bc = 250 #[mm]


#Vector de variables. El primero es el flujo, las restantes son los precursores, de C1 a C6
var = trc.zeros(7, device=gpu)
var[0] = 1.2877e3
var[1] = 5.9859e4
var[2] = 1.3441e5
var[3] = 3.2697e4
var[4] = 2.6174e4
var[5] = 1.8286e3
var[6] = 1.3437e2



#Probemos con el modelo de PyTorch
class FisicaRA4(trc.nn.Module):
    def __init__(self, deltaT, device=None):
        super(FisicaRA4, self).__init__()
        self.lin1 = trc.nn.Linear(7, 7, device=device)
        self.deltaT = deltaT
    
    def forward(self, x):
        dif = self.lin1(x)
        x += dif * self.deltaT
        return x

SistRA4 = FisicaRA4(deltaT, device=gpu)
SistRA4.state_dict()['lin1.weight'][:,:] = trc.zeros(7,7)
SistRA4.state_dict()['lin1.weight'][0,0] = ((-5*730*1e-5) - beta_eff) / LAM
SistRA4.state_dict()['lin1.weight'][0, 1:] = lam
SistRA4.state_dict()['lin1.weight'][1:, 1:] = trc.diag(-lam)
SistRA4.state_dict()['lin1.weight'][1:, 0] = beta_i/LAM
SistRA4.state_dict()['lin1.bias'][:] = trc.zeros(7)
SistRA4.state_dict()['lin1.bias'][0] = S



#Funciones
#Cálculo de la evolución del sistema con el modelo en PyTorch
def sist_fis(x):
    x = SistRA4(x)
    return x

def f1():
    global var
    while ejec:
        var = sist_fis(var)
        for i in range(7):
            E[i].config(text=round(var[i].item(),2))
        tm.sleep(deltaT)

def cerrar():
    global ejec
    global var
    ejec = False
    ventana.destroy()

t1 = thr.Thread(target=f1)

def hilos():
    t1.start()

#Funciones para actualizar los parámetros del modelo en caso que haya algún movimiento de fuente o reactividad
def get_rho(e1):
    rho = rho_max + ((100 - pos_nuc.get())/100) * rho_nuc + ((100 - pos_BC1.get())/100) * rho_BC1 + ((100 - pos_BC2.get())/100) * rho_BC2
    SistRA4.state_dict()['lin1.weight'][0,0] = ((rho) - beta_eff) / LAM
    etiq_rho.config(text=round(rho*1e5, 2))

def get_fte(e2):
    SistRA4.state_dict()['lin1.bias'][0] = ((fte.get()/100)*0.75 + 0.25)*S



#----------Arranca la GUI----------

ventana = tk.Tk()
ventana.title("Cinética puntual - 6 grupos")
ventana.geometry("290x350")
ventana.resizable(False, False)

#---Marcos
marco_nuc = tk.LabelFrame(ventana, text='% mov. nuc.')
marco_BC1 = tk.LabelFrame(ventana, text='% mov. BC1.')
marco_BC2 = tk.LabelFrame(ventana, text='% mov. BC2.')
marco_fte = tk.LabelFrame(ventana, text='Pos. fte.')
marco_var = tk.LabelFrame(ventana, text='Variables')

#---Widgets
#Mov núcleo:
#pos_nuc_etiq = tk.Label(ventana, text="% rec. nuc.")
pos_nuc = tk.Scale(marco_nuc, from_=100, to=0, orient=tk.VERTICAL, command=get_rho)
pos_nuc.set(0)

#Mov BC1:
#pos_BC1_etiq = tk.Label(ventana, text="% rec. BC1.")
pos_BC1 = tk.Scale(marco_BC1, from_=100, to=0, orient=tk.VERTICAL, command=get_rho)
pos_BC1.set(0)

#Mov BC2:
#pos_BC2_etiq = tk.Label(ventana, text="% rec. BC2.")
pos_BC2 = tk.Scale(marco_BC2, from_=100, to=0, orient=tk.VERTICAL, command=get_rho)
pos_BC2.set(0)

#Fuente de neutrones:
fte_etiq = tk.Label(ventana, text="Pos fte. n %")
fte = tk.Scale(marco_fte, from_=0, to=100, orient=tk.HORIZONTAL, command=get_fte, digits=0)
fte.set(100)

#Etiquetas para variables
etiq_r = tk.Label(marco_var, text="react.:")
etiq_n = tk.Label(marco_var, text="n(t):")
etiq_C1 = tk.Label(marco_var, text="C1(t):")
etiq_C2 = tk.Label(marco_var, text="C2(t):")
etiq_C3 = tk.Label(marco_var, text="C3(t):")
etiq_C4 = tk.Label(marco_var, text="C4(t):")
etiq_C5 = tk.Label(marco_var, text="C5(t):")
etiq_C6 = tk.Label(marco_var, text="C6(t):")


#Etiqueta para valores de variables
etiq_rho = tk.Label(marco_var, text=rho*1e5, width=10)

E = [None, None, None, None, None, None, None]
for i in range(7):
    E[i] = tk.Label(marco_var, text=f"var {i}", width=10)


#---Ubicación widgets
#Posición del núcleo
marco_nuc.grid(row=0, column=0)
pos_nuc.pack()

#Posición de BC1
marco_BC1.grid(row=0, column=1)
pos_BC1.pack()

#Posición de BC2
marco_BC2.grid(row=0, column=2)
pos_BC2.pack()

#Variables
marco_var.grid(row=1, column=0, columnspan=3)

etiq_r.grid(row=0, column=0, padx=5, pady=5)
etiq_rho.grid(row=0, column=1, padx=5, pady=5)
etiq_n.grid(row=0, column=2, padx=5, pady=5)
E[0].grid(row=0, column=3, padx=5, pady=5)

etiq_C1.grid(row=1, column=0, padx=5, pady=5)
E[1].grid(row=1, column=1, padx=5, pady=5)
etiq_C2.grid(row=1, column=2, padx=5, pady=5)
E[2].grid(row=1, column=3, padx=5, pady=5)

etiq_C3.grid(row=2, column=0, padx=5, pady=5)
E[3].grid(row=2, column=1, padx=5, pady=5)
etiq_C4.grid(row=2, column=2, padx=5, pady=5)
E[4].grid(row=2, column=3, padx=5, pady=5)

etiq_C5.grid(row=3, column=0, padx=5, pady=5)
E[5].grid(row=3, column=1, padx=5, pady=5)
etiq_C6.grid(row=3, column=2, padx=5, pady=5)
E[6].grid(row=3, column=3, padx=5, pady=5)

marco_fte.grid(row=2, column=0, columnspan=3)
fte.pack()


hilos()

ventana.protocol("WM_DELETE_WINDOW", cerrar)
ventana.mainloop()
os.kill(os.getpid(), 9)