# -*- coding: utf-8 -*-
from __future__ import division
from datetime import datetime
from appVar import *
import changePriority as cpr
import socketPayload as sp
import numpy as np
import ctypes as C
import queue,socket

def premessage(st, cut, size):
    st.Cut = cut
    st.Size = INT64(size)
    return st

def socket_client(DataS, ShutDown, Connection, LockQ):
    
    cpr.SetPriority(1)
    PreMessage = sp.MESSAGE_PRELOAD()
    while not ShutDown.is_set():
            
        try:
            CwtFreq = DataS.get(GETBLOCK, GETTIMEOUT)
            Message = sp.MessageReturn(CwtFreq.value*DB)
            ar_type = DOUBLE*CwtFreq.value
            break
        except queue.Empty:
            continue
        except EOFError:
            ShutDown.set()
            break
    
    i=0
    ch=0
    try:
        while not ShutDown.is_set():
            
            try:
                InputMessage = DataS.get(GETBLOCK, GETTIMEOUT)
            except queue.Empty:
                continue
            except EOFError:
                ShutDown.set()
                break
            
            Message.Cut = InputMessage.Cut
            Message.Timestamp = InputMessage.Timestamp
            Message.Time_Interval = InputMessage.Time_Interval
            for n in InputMessage.nChannel:
                ch+=1
            for f in Message._fields_:
                if i == ch:
                    break
                if f[1] == ar_type:
                    setattr(Message,f[0],np.ctypeslib.as_ctypes(InputMessage.nChannel[i]))
                    i += 1
            i=0
            ch=0
            try:
                Connection.sendall(premessage(PreMessage, Message.Cut, C.sizeof(Message)))
                Message.Timestamp = DOUBLE(datetime.utcnow().timestamp())
                Connection.sendall(Message)# Отправка преобразованных данных через протокол Sockets
            except socket.error as e:
                print(e)
                ShutDown.set()
    finally:
        Connection.close()
