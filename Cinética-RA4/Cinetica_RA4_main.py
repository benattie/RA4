#Módulos de python
import tkinter as tk
import multiprocessing as mtp
import threading as thr
import time as tm
import os

from Cinetica_RA4_modulos import CineticaPuntual

deltaT = 0.001 #[s]

if __name__ == '__main__':
    mtp.freeze_support()

    #Parámetros físicos
    #Parámetros del RA4
    LAM = 4.7e-5 #[s]
    beta_eff = 730e-5

    #Valores iniciales
    rho_nuc = -5*beta_eff
    rho_BC1 = -0.6*beta_eff
    rho_BC2 = -0.6*beta_eff
    rho_max = 0.3*beta_eff
    rho = rho_max + rho_nuc + rho_BC1 + rho_BC2
    S = 1e6

    #Tuttle (constantes de los grupos de neutrones retardados)
    # lam = trc.tensor([0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87], device=gpu) #[1/s] ctes. de desintegración, del grupo 1 al 6
    # frac_i = trc.tensor([0.038, 0.213, 0.188, 0.407, 0.128, 0.026], device=gpu) #[%] fracciones de cada grupo, del 1 al 6
    lam = [0.0127, 0.0317, 0.1150, 0.3110, 1.4, 3.87] #[1/s] ctes. de desintegración, del grupo 1 al 6
    frac_i = [0.038, 0.213, 0.188, 0.407, 0.128, 0.026] #[%] fracciones de cada grupo, del 1 al 6
    beta_i = [] #frac_i*beta_eff
    for i in range(len(lam)):
        beta_i.append(frac_i[i]*beta_eff)

    #Otros valores del RA4
    rec_nuc = 50 #[mm]
    rec_bc = 250 #[mm]

    #Vector de variables. El primero es el flujo, las restantes son los precursores, de C1 a C6
    n_0 = 1091.246826171875     #1.2877e3
    C_0 = [
        507140.0060000771,
        1138854.7486543525,
        277081.8028195465,
        221810.4566764686,
        15496.368303572082,
        1138.7027742450227
    ]

    nucleo = CineticaPuntual(LAM, beta_eff, lam, frac_i, deltaT, rho, S, n_0, C_0)
    print(nucleo)

    def set_rho(e1):
        rho = rho_max + ((100 - pos_nuc.get())/100) * rho_nuc + ((100 - pos_BC1.get())/100) * rho_BC1 + ((100 - pos_BC2.get())/100) * rho_BC2
        nucleo.set_rho(rho)
        etiq_rho.config(text=round(rho*1e5, 2))
    
    def set_S(e2):
        s = ((fte.get()/100)*0.75 + 0.25)*S
        nucleo.set_S(s)


    #----------Arranca la GUI----------
    ventana = tk.Tk()
    ventana.title("Cinética puntual - 6 grupos")
    ventana.geometry("330x380")
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
    pos_nuc = tk.Scale(marco_nuc, from_=100, to=0, orient=tk.VERTICAL, command=set_rho)
    pos_nuc.set(0)

    #Mov BC1:
    #pos_BC1_etiq = tk.Label(ventana, text="% rec. BC1.")
    pos_BC1 = tk.Scale(marco_BC1, from_=100, to=0, orient=tk.VERTICAL, command=set_rho)
    pos_BC1.set(0)

    #Mov BC2:
    #pos_BC2_etiq = tk.Label(ventana, text="% rec. BC2.")
    pos_BC2 = tk.Scale(marco_BC2, from_=100, to=0, orient=tk.VERTICAL, command=set_rho)
    pos_BC2.set(0)

    #Fuente de neutrones:
    fte_etiq = tk.Label(ventana, text="Pos fte. n %")
    fte = tk.Scale(marco_fte, from_=0, to=100, orient=tk.HORIZONTAL, command=set_S, digits=0)
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

    # E = [None, None, None, None, None, None, None]
    # for i in range(7):
    #     E[i] = tk.Label(marco_var, text=f"var {i}", width=10)
    para_n = tk.Label(marco_var, text=f"n", width=10)

    def funcbot():
        para_n.config(text=round(nucleo.get_n(),2))
    
    bot = tk.Button(marco_var, text="Veamos...", command=funcbot)

    def verproc():
        for proc in mtp.active_children():
            print(proc)
    
    bot2 = tk.Button(marco_var, text="Veamos......", command=verproc)

    #---Ubicación widgets
    tk.Grid.rowconfigure(ventana,0,weight=1)
    tk.Grid.rowconfigure(ventana,1,weight=1)
    #tk.Grid.rowconfigure(ventana,2,weight=1)
    tk.Grid.columnconfigure(ventana,0,weight=1)
    tk.Grid.columnconfigure(ventana,1,weight=1)
    tk.Grid.columnconfigure(ventana,2,weight=1)


    #Posición del núcleo
    marco_nuc.grid(row=0, column=0, sticky=tk.NSEW)
    marco_nuc.rowconfigure(0,weight=1)
    marco_nuc.columnconfigure(0,weight=1)

    pos_nuc.grid(row=0, column=0, sticky=tk.NS)

    #Posición de BC1
    marco_BC1.grid(row=0, column=1, sticky=tk.NSEW)
    marco_BC1.rowconfigure(0,weight=1)
    marco_BC1.columnconfigure(0,weight=1)

    pos_BC1.grid(row=0, column=0, sticky=tk.NS)

    #Posición de BC2
    marco_BC2.grid(row=0, column=2, sticky=tk.NSEW)
    marco_BC2.rowconfigure(0,weight=1)
    marco_BC2.columnconfigure(0,weight=1)

    pos_BC2.grid(row=0, column=0, sticky=tk.NS)

    #Variables
    marco_var.grid(row=1, column=0, columnspan=3, sticky=tk.NSEW)
    marco_var.rowconfigure(0,weight=1)
    marco_var.rowconfigure(1,weight=1)
    marco_var.rowconfigure(2,weight=1)
    marco_var.rowconfigure(3,weight=1)
    marco_var.columnconfigure(0,weight=1)
    marco_var.columnconfigure(1,weight=20)
    marco_var.columnconfigure(2,weight=1)
    marco_var.columnconfigure(3,weight=20)

    etiq_r.grid(row=0, column=0, padx=5, pady=5)
    etiq_rho.grid(row=0, column=1, padx=5, pady=5)
    etiq_n.grid(row=0, column=2, padx=5, pady=5)
    para_n.grid(row=0, column=3, padx=5, pady=5)
    bot.grid(row=1, column=0)
    bot2.grid(row=2, column=0)

    marco_fte.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW)
    fte.pack()

    #ventana.protocol("WM_DELETE_WINDOW", cerrar)
    ventana.mainloop()

    for proc in mtp.active_children():
        proc.terminate()
    os.kill(os.getpid(), 9)
