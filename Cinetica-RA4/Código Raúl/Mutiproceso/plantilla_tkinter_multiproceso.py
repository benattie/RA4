#Módulos de python
import tkinter as tk
import time as tm
import multiprocessing as mtp

#----------Inicialización----------

def f1():
    while True:
        print("Estoy haciendo una cosa")
        tm.sleep(2.0)
  
def f2():
    while True:
        print("Estoy haciendo otra cosa más lenta...")
        tm.sleep(5.0)

def f3():
    while True:
        print("Esto es lo más lento!")
        tm.sleep(10.0)

p1 = mtp.Process(target=f1)
p2 = mtp.Process(target=f2)
p3 = mtp.Process(target=f3)

def main():
    p1.start()
    p2.start()
    p3.start()

def cerrar():
    p1.terminate()
    p2.terminate()
    p3.terminate()
    ventana.destroy()


if __name__ == '__main__':
    ventana = tk.Tk()
    main()

    def cerrar():
        p1.terminate()
        p2.terminate()
        p3.terminate()
        ventana.destroy()

    ventana.protocol("WM_DELETE_WINDOW", cerrar)
    ventana.mainloop()


