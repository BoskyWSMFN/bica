import ctypes as c
import logging
import multiprocessing
import socket
import sys
import time
from multiprocessing import (Process, Queue, Event, Lock)

import filemapping as fm
import signalanalysis as sig
import socketclient as scl


def main():
    loggermp = multiprocessing.get_logger()
    loggermp.setLevel(logging.DEBUG)

    sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            host = input('Введите адрес сервера (127.0.0.1/192.168.ххх.ххх/localhost): ')
            port = 1024

            while True:
                try:
                    port = abs(
                        int(input('Введите номер порта (целое положительное число,'
                                  '>1023 не требует привилегий): ')))

                    break
                except ValueError:
                    print('Должно быть целое число <=65535!')

                    continue

            sock_client.connect((host, port))

            break
        except WindowsError:
            print(c.WinError(c.get_last_error()))
            input('Нажмите Enter, чтобы повторить попытку подключения...')

            continue

    quasi_freq_filter = [0, 0]
    while True:
        while True:
            try:
                lower = input("Нижняя граница фильтра, ГЦ (0 - без нижней границы): ")
                quasi_freq_filter[0] = abs(int(lower))

                break
            except ValueError:
                print('Должно быть целое положительное число или 0!')

                continue

        while True:
            try:
                upper = input("Верхняя граница фильтра, ГЦ (0 - без верхней границы): ")
                quasi_freq_filter[1] = abs(int(upper))

                break
            except ValueError:
                print('Должно быть целое положительное число или 0!')

                continue

        if quasi_freq_filter[0] >= quasi_freq_filter[1] and quasi_freq_filter[0] + quasi_freq_filter[1] != 0:
            print(
                "Для получения полезного сигнала значение верхней"
                "границы фильтра должно быть больше значения нижней!")
            continue
        else:
            for i in range(2):
                if quasi_freq_filter[i] == 0:
                    quasi_freq_filter[i] = None
            break

    data_q = Queue()
    data_s = Queue()
    lock_q = Lock()
    shutdown_e = Event()
    file_mapping = Process(target=fm.file_mapping, args=(sock_client, data_q, shutdown_e, lock_q,))
    sig_analysis = Process(target=sig.signal_analysis, args=(data_q, data_s, shutdown_e, quasi_freq_filter,))
    socket_client = Process(target=scl.socket_client, args=(data_s, shutdown_e, sock_client, lock_q,))
    file_mapping.daemon = True
    socket_client.daemod = True

    try:
        file_mapping.start()
        sig_analysis.start()
        socket_client.start()

        shutdown_e.wait()

        raise SystemExit()
    except Exception as e:
        print(e)
        shutdown_e.set()
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit, EOFError):
        shutdown_e.set()
        time.sleep(10)
    finally:
        sock_client.shutdown(socket.SHUT_RDWR)
        sock_client.close()

        time.sleep(2)
        while data_s.qsize() != 0:
            data_s.get_nowait()
        while data_q.qsize() != 0:
            data_q.get_nowait()

        data_s.close()
        data_s.join_thread()
        data_q.close()
        data_q.join_thread()
        print('\nРабота окончена!')
        file_mapping.join()
        sig_analysis.join()
        socket_client.join()
        sys.exit(0)


if __name__ == '__main__':
    main()
