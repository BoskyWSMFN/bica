# -*- coding: utf-8 -*-
import ctypes as c
import socket as sck
import sys
import time
import traceback
from ctypes import (c_int64, c_float, c_double)
from threading import Thread, Event

import numpy as np

import socketpayload as sp

###
INT64 = c_int64
FLOAT = c_float
DOUBLE = c_double
###
ExpectedChannels = 22
FirstMessageSize = 32
PreMessageSize = 16


###

class SRV(Thread):
    def __init__(self, shutdown_event, port: int):
        Thread.__init__(self)
        self.sock = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        self.shutdown_event = shutdown_event
        self.port = port
        self.scktmt = 0.1
        self.firstmes = sp.FirstMessagePayload()
        self.premes = sp.MessagePreload()
        self.mes = None
        self.nChannel = [np.array([0])] * ExpectedChannels

    def startup(self):
        # self.sock.setsockopt(sck.SOL_SOCKET, sck.SO_REUSEADDR, 1)
        self.sock.bind(('', self.port))
        self.sock.settimeout(self.scktmt)
        self.sock.listen(1)

    def shutdown(self, done=False):
        self.shutdown_event.set()
        if not done:
            time.sleep(1)
            self.sock.shutdown(sck.SHUT_RDWR)
            self.sock.close()

    def c2npcast(self, datalen, channels):
        size = 1
        shape = (datalen,)
        i = 0
        arlen = int(self.firstmes.Frequency / int(self.firstmes.Frequency /
                                                  self.firstmes.Cwt_Frequency))
        for s in shape:
            size *= s
        # noinspection PyProtectedMember
        for f in self.mes._fields_:
            if i == channels:
                break
            if f[1] == DOUBLE * arlen:
                self.nChannel[i] = np.ctypeslib.as_array(getattr(self.mes, f[0]), shape)
                i += 1

    def run(self):
        fm = True
        old_cut = 0

        while not self.shutdown_event.is_set():
            try:
                connection, address = self.sock.accept()
            except sck.timeout:
                continue
            except KeyboardInterrupt:
                self.shutdown_event.set()
                self.sock.close()

                return
            except WindowsError as w:
                print(w)
                print(traceback.format_exc())
                self.shutdown_event.set()
                self.sock.close()

                return

            print('\nСоединение: ', address)

            break

        try:
            while not self.shutdown_event.is_set():
                if fm:
                    try:
                        # noinspection PyUnboundLocalVariable
                        connection.recv_into(self.firstmes, FirstMessageSize)
                    except sck.timeout as t:
                        print(t)
                        self.shutdown()

                        break
                    except sck.herror as e:
                        print(e)
                        self.shutdown()

                        break

                    print('\nЧастота оцифровки: ', self.firstmes.Frequency, ' Гц')
                    print('Частота преобразования: ', int(self.firstmes.Frequency / self.firstmes.Cwt_Frequency), ' Гц')
                    print('Фактическое количество каналов: ', self.firstmes.Channels)
                    self.mes = sp.get_socket_payload(self.firstmes.Frequency)
                    fm = False
                else:
                    try:
                        connection.recv_into(self.premes, PreMessageSize)
                        connection.recv_into(self.mes, self.premes.Size)
                        self.c2npcast(self.firstmes.Cwt_Frequency, self.firstmes.Channels)
                    except sck.timeout as t:
                        print(t)
                        self.shutdown()

                        break
                    except sck.herror as e:
                        print(e)
                        self.shutdown()

                        break

                    if self.mes.Cut <= old_cut:
                        break

                    old_cut = self.mes.Cut

                    print('\nСечение: ', self.mes.Cut)
                    print('Канал 1, первые 10 значений: ', (self.nChannel[0])[:10])
        finally:
            self.shutdown(done=True)


def main():
    port = 1024
    while True:
        try:
            port = int(input('Введите номер порта (целое положительное число, >1023 не требует привилегий): '))
            if port < 0 or port > 65535:
                raise ValueError("Must be greater than zero!")

            break
        except ValueError:
            print('Должно быть целое число <=65535!')

            continue
    shutdown = Event()
    thread = SRV(shutdown, port)
    thread.daemon = True
    thread.startup()
    thread.start()

    try:
        shutdown.wait()
        raise SystemExit()
    except (KeyboardInterrupt, SystemExit, EOFError):
        thread.shutdown()
    finally:
        print('Работа окончена!')
        thread.join()
        sys.exit(0)


if __name__ == '__main__':
    main()
