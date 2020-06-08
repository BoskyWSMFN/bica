# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import (Structure,POINTER,c_int64,c_float,c_double)
from threading import Thread, Event
import sys,time
import numpy as np
import socket as sck
import ctypes as C

###
INT64                = c_int64
FLOAT                = c_float
DOUBLE               = c_double
###
ExpectedChannels     = 22
FirstMessageSize     = 32
PreMessageSize       = 16
###
"""
Waiting for further experiments
"""
valA                 = 1
valB                 = 0
arousA               = 1
arousB               = 0
dominA               = 1
dominB               = 0
###

class FIRST_MESSAGE_PAYLOAD(Structure):
    _fields_ = (("Frequency", INT64),
                ("Cwt_Frequency", INT64),
                ("Channels", INT64),
                ("Timestamp", DOUBLE))

class MESSAGE_PRELOAD(Structure):
    _fields_ = (("Cut", INT64),
                ("Size", INT64))

class MESSAGE_PAYLOAD(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("Time_Interval", FLOAT),
                ("Channel_1", DOUBLE*250),
                ("Channel_2", DOUBLE*250),
                ("Channel_3", DOUBLE*250),
                ("Channel_4", DOUBLE*250),
                ("Channel_5", DOUBLE*250),
                ("Channel_6", DOUBLE*250),
                ("Channel_7", DOUBLE*250),
                ("Channel_8", DOUBLE*250),
                ("Channel_9", DOUBLE*250),
                ("Channel_10", DOUBLE*250),
                ("Channel_11", DOUBLE*250),
                ("Channel_12", DOUBLE*250),
                ("Channel_13", DOUBLE*250),
                ("Channel_14", DOUBLE*250),
                ("Channel_15", DOUBLE*250),
                ("Channel_16", DOUBLE*250),
                ("Channel_17", DOUBLE*250),
                ("Channel_18", DOUBLE*250),
                ("Channel_19", DOUBLE*250),
                ("Channel_20", DOUBLE*250),
                ("Channel_21", DOUBLE*250),
                ("Channel_22", DOUBLE*250))
    
    def c2npcast(self, datalen, channels):
        size = 1
        shape=(datalen,)
        i = 0
        for s in shape:
            size *= s
        for f in self._fields_:
            if i == channels:
                break
            if isinstance(f[1], POINTER(DOUBLE*250)):
                dbuffer = (DOUBLE * size).from_address(C.addressof(getattr(self, f[0]).contents))
                self.nChannel[i] = np.frombuffer(dbuffer, dtype=DOUBLE).reshape(shape)
                i+=1
            elif isinstance(f[1], DOUBLE*250):
                self.nChannel[i] = np.ctypeslib.as_array(getattr(self, f[0]),shape)
                i+=1
    
    def __init__(self,*args,**kwargs):
        super(MESSAGE_PAYLOAD,self).__init__(*args,**kwargs)
        self.nChannel = [np.array([0]*250, dtype=DOUBLE, order='C')]*ExpectedChannels
        
        i = 0
        for f in self._fields_:
            if f[1] == DOUBLE*250:
                setattr(self,f[0],np.ctypeslib.as_ctypes(self.nChannel[i]))
                i += 1

def 2valence(x):
    return valA*x+valB

def 2arousal(x):
    return arousA*x+arousB

def 2dominance(x):
    return dominA*x+dominB

class SRV(Thread):
    def __init__(self, shutdown_event, port):
        Thread.__init__(self)
        self.sock = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        self.shutdown_event = shutdown_event
        self.port = port
        self.scktmt = 0.1
        self.firstmes = FIRST_MESSAGE_PAYLOAD()
        self.premes = MESSAGE_PRELOAD()
        self.mes = MESSAGE_PAYLOAD()
    
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
        
    def run(self):
        fm = True
        try:
            print('Ожидание соединения...')
            while not self.shutdown_event.is_set():
                try:
                    connection, address = self.sock.accept()
                except sck.timeout:
                    continue
                print('Соединение: ', address)
                break
                
            while not self.shutdown_event.is_set():
                if fm:
                    try:
                        connection.recv_into(self.firstmes, FirstMessageSize)
                    except sck.timeout:
                        continue
                    print('\nЧастота оцифровки: ', self.firstmes.Frequency)
                    print('Частота преобразования: ', self.firstmes.Cwt_Frequency)
                    print('Фактическое количество каналов: ', self.firstmes.Channels)
                    fm = False
                else:
                    try:
                        connection.recv_into(self.premes, PreMessageSize)
                        connection.recv_into(self.mes, self.premes.Size)
                    except sck.timeout:
                        continue
                    print('\nСечение: ', self.mes.Cut)
                    self.mes.c2npcast(self.firstmes.Cwt_Frequency,self.firstmes.Channels)
                    
            
        finally:
            self.shutdown(done=True)




if __name__ == '__main__':
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