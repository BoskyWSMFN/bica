# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import (c_int64,c_float,c_double)
from threading import Thread, Event
import sys,time
import numpy as np
import socket as sck
import socketPayload as sp

###
INT64                = c_int64
FLOAT                = c_float
DOUBLE               = c_double
###
ExpectedChannels     = 22
FirstMessageSize     = 32
PreMessageSize       = 16
###

class SRV(Thread):
    def __init__(self, shutdown_event, port):
        Thread.__init__(self)
        self.sock = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        self.shutdown_event = shutdown_event
        self.port = port
        self.scktmt = 0.1
        self.firstmes = sp.FIRST_MESSAGE_PAYLOAD()
        self.premes = sp.MESSAGE_PRELOAD()
        self.mes = None
        self.nChannel = [np.array([0])]*ExpectedChannels
    
    def startup(self):
        #self.sock.setsockopt(sck.SOL_SOCKET, sck.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', self.port))
        self.sock.settimeout(self.scktmt)
        self.sock.listen(1)

    def shutdown(self, done=False):
        self.shutdown_event.set()
        if not done:
            time.sleep(1)
            self.sock.close()
    
    def c2npcast(self, datalen, channels):
        size = 1
        shape=(datalen,)
        i = 0
        arlen = int(self.firstmes.Frequency/int(self.firstmes.Frequency/
                                             self.firstmes.Cwt_Frequency))
        for s in shape:
            size *= s
        for f in self.mes._fields_:
            if i == channels:
                break
            if f[1] == DOUBLE*arlen:
                self.nChannel[i] = np.ctypeslib.as_array(getattr(self.mes, f[0]),shape)
                i+=1
        
    def run(self):
        fm = True
        try:
            print('Ожидание соединения...')
            while not self.shutdown_event.is_set():
                try:
                    connection, address = self.sock.accept()
                except sck.timeout:
                    continue
                print('\nСоединение: ', address)
                break
                
            while not self.shutdown_event.is_set():
                if fm:
                    try:
                        connection.recv_into(self.firstmes, FirstMessageSize)
                    except sck.timeout:
                        continue
                    except sck.herror:
                        self.shutdown()
                        break
                    print('\nЧастота оцифровки: ', self.firstmes.Frequency, ' Гц')
                    print('Частота преобразования: ', int(self.firstmes.Frequency/self.firstmes.Cwt_Frequency), ' Гц')
                    print('Фактическое количество каналов: ', self.firstmes.Channels)
                    self.mes = sp.MessageReturn(self.firstmes.Frequency)
                    fm = False
                else:
                    try:
                        connection.recv_into(self.premes, PreMessageSize)
                        connection.recv_into(self.mes, self.premes.Size)
                        self.c2npcast(self.firstmes.Cwt_Frequency,self.firstmes.Channels)
                    except sck.timeout:
                        continue
                    except sck.herror:
                        self.shutdown()
                        break
                    print('\nСечение: ', self.mes.Cut)
                    print('Канал 1, первые 10 значений: ', (self.nChannel[0])[:10])
                    
            
        finally:
            self.shutdown(done=True)




def main():
    while True:
        try:
            port = abs(int(input('Введите номер порта (целое положительное число, >1023 не требует привелегий): ')))
            break
        except ValueError:
            print('Должно быть целое число!')
            continue
    shutdown = Event()
    thread = SRV(shutdown, port)
    thread.daemon = True
    thread.start()
    thread.startup()
    try:
        input('Для остановки нажмите Enter...')
        raise SystemExit()
    except (KeyboardInterrupt, SystemExit, EOFError):
        thread.shutdown()
        time.sleep(2)
    finally:
        print('Работа окончена!')
        thread.join(timeout=5)
        sys.exit(0)

if __name__ == '__main__':
    main()