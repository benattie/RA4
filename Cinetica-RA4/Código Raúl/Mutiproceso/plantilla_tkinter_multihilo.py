#Módulos de python
import tkinter as tk
import time as tm
import threading as thr

#----------Inicialización----------

ejec = True

def f1():
    while ejec:
        print("Estoy haciendo una cosa")
        tm.sleep(2.0)
  
def f2():
    while ejec:
        print("Estoy haciendo otra cosa más lenta...")
        tm.sleep(5.0)

def f3():
    while ejec:
        print("Esto es lo más lento!")
        tm.sleep(10.0)

t1 = thr.Thread(target=f1)
t2 = thr.Thread(target=f2)
t3 = thr.Thread(target=f3)

def main():
    t1.start()
    t2.start()
    t3.start()

def cerrar():
    global ejec
    ejec = False
    ventana.destroy()


#if __name__ == '__main__':
ventana = tk.Tk()
main()
ventana.protocol("WM_DELETE_WINDOW", cerrar)
ventana.mainloop()


