from __future__ import division
from multiprocessing import (Process,Queue,Event,Lock)
import ctypes as C
import fileMapping as fm
import sigAnalysis as sigan
import socketClient as scl
import socket,time,sys

def main():
        
    SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            host = input('Введите адрес сервера (127.0.0.1/192.168.ххх.ххх/localhost): ')
            while True:
                try:
                    port = abs(int(input('Введите номер порта (целое положительное число, >1023 не требует привелегий): ')))
                    break
                except ValueError:
                    print('Должно быть целое число!')
                    continue
            SOCKET.connect((host,port))
            break
        except WindowsError:
            print(C.WinError(C.get_last_error()))
            input('Нажмите Enter, чтобы повторить попытку подключения...')
            continue
    
    flt = [0,0]
    while True:
        while True:
            try:
                flti = input("Нижняя граница фильтра, ГЦ (0 - без нижней границы): ")
                flt[0] = abs(int(flti))
                break
            except ValueError:
                print('Должно быть целое положительное число или 0!')
                continue
        while True:
            try:
                flti = input("Верхняя граница фильтра, ГЦ (0 - без верхней границы): ")
                flt[1] = abs(int(flti))
                break
            except ValueError:
                print('Должно быть целое положительное число или 0!')
                continue
        if flt[0] >= flt[1] and flt[0]+flt[1] != 0:
            print("Для получения полезного сигнала значение верхней границы фильтра должно быть больше значения нижней!")
            continue
        else:
            for i in range(2):
                if flt[i] == 0:
                    flt[i] = None
            break
    DataQ = Queue()
    DataS = Queue()
    LockQ = Lock()
    ShutDown = Event()
    Filemapping = Process(target=fm.file_mapping, args=(SOCKET, DataQ, DataS, ShutDown, LockQ))
    Analysis = Process(target=sigan.analysis, args=(DataQ, DataS, ShutDown, LockQ, flt,))
    SocketClient = Process(target=scl.socket_client, args=(DataS, ShutDown, SOCKET, LockQ,))
    Filemapping.daemon = True
    SocketClient.daemod = True
    Filemapping.start()
    Analysis.start()
    SocketClient.start()
    try:
        input('Для остановки нажмите Enter...')
        raise SystemExit()
    except (KeyboardInterrupt, SystemExit, EOFError):
        ShutDown.set()
        time.sleep(10)
    finally:
        DataQ.close()
        DataQ.join_thread()
        DataS.close()
        DataS.join_thread()
        print('Работа окончена!')
        time.sleep(2)
        Filemapping.join(2)
        Analysis.join(2)
        SocketClient.join(2)
        sys.exit(0)

if __name__ == '__main__':
    main()