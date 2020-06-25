# -*- coding: utf-8 -*-
from ctypes import (Structure,c_int64,c_float,c_double,POINTER)
from appVar import *
import ctypes as C

class FIRST_MESSAGE_PAYLOAD(Structure):
    _fields_ = (("Frequency", INT64),
                ("Cwt_Frequency", INT64),
                ("Channels", INT64),
                ("Timestamp", DOUBLE))

class MESSAGE_PRELOAD(Structure):
    _fields_ = (("Cut", INT64),
                ("Size", INT64))

class MESSAGE_PAYLOAD_200Hz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("Time_Interval", FLOAT),
                ("Channel_1", DOUBLE*50),
                ("Channel_2", DOUBLE*50),
                ("Channel_3", DOUBLE*50),
                ("Channel_4", DOUBLE*50),
                ("Channel_5", DOUBLE*50),
                ("Channel_6", DOUBLE*50),
                ("Channel_7", DOUBLE*50),
                ("Channel_8", DOUBLE*50),
                ("Channel_9", DOUBLE*50),
                ("Channel_10", DOUBLE*50),
                ("Channel_11", DOUBLE*50),
                ("Channel_12", DOUBLE*50),
                ("Channel_13", DOUBLE*50),
                ("Channel_14", DOUBLE*50),
                ("Channel_15", DOUBLE*50),
                ("Channel_16", DOUBLE*50),
                ("Channel_17", DOUBLE*50),
                ("Channel_18", DOUBLE*50),
                ("Channel_19", DOUBLE*50),
                ("Channel_20", DOUBLE*50),
                ("Channel_21", DOUBLE*50),
                ("Channel_22", DOUBLE*50))
    
    def Pack(self):
        return C.string_at(C.byref(self), C.sizeof(self))
    
    def Unpack(self, buf):
        return C.cast(C.pointer(C.create_string_buffer(buf)), POINTER(self)).contents
    
    def __init__(self,*args,**kwargs):
        super(MESSAGE_PAYLOAD_200Hz,self).__init__(*args,**kwargs)

class MESSAGE_PAYLOAD_250Hz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("Time_Interval", FLOAT),
                ("Channel_1", DOUBLE*62),
                ("Channel_2", DOUBLE*62),
                ("Channel_3", DOUBLE*62),
                ("Channel_4", DOUBLE*62),
                ("Channel_5", DOUBLE*62),
                ("Channel_6", DOUBLE*62),
                ("Channel_7", DOUBLE*62),
                ("Channel_8", DOUBLE*62),
                ("Channel_9", DOUBLE*62),
                ("Channel_10", DOUBLE*62),
                ("Channel_11", DOUBLE*62),
                ("Channel_12", DOUBLE*62),
                ("Channel_13", DOUBLE*62),
                ("Channel_14", DOUBLE*62),
                ("Channel_15", DOUBLE*62),
                ("Channel_16", DOUBLE*62),
                ("Channel_17", DOUBLE*62),
                ("Channel_18", DOUBLE*62),
                ("Channel_19", DOUBLE*62),
                ("Channel_20", DOUBLE*62),
                ("Channel_21", DOUBLE*62),
                ("Channel_22", DOUBLE*62))
    
    def Pack(self):
        return C.string_at(C.byref(self), C.sizeof(self))
    
    def Unpack(self, buf):
        return C.cast(C.pointer(C.create_string_buffer(buf)), POINTER(self)).contents
    
    def __init__(self,*args,**kwargs):
        super(MESSAGE_PAYLOAD_250Hz,self).__init__(*args,**kwargs)

class MESSAGE_PAYLOAD_500Hz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("Time_Interval", FLOAT),
                ("Channel_1", DOUBLE*125),
                ("Channel_2", DOUBLE*125),
                ("Channel_3", DOUBLE*125),
                ("Channel_4", DOUBLE*125),
                ("Channel_5", DOUBLE*125),
                ("Channel_6", DOUBLE*125),
                ("Channel_7", DOUBLE*125),
                ("Channel_8", DOUBLE*125),
                ("Channel_9", DOUBLE*125),
                ("Channel_10", DOUBLE*125),
                ("Channel_11", DOUBLE*125),
                ("Channel_12", DOUBLE*125),
                ("Channel_13", DOUBLE*125),
                ("Channel_14", DOUBLE*125),
                ("Channel_15", DOUBLE*125),
                ("Channel_16", DOUBLE*125),
                ("Channel_17", DOUBLE*125),
                ("Channel_18", DOUBLE*125),
                ("Channel_19", DOUBLE*125),
                ("Channel_20", DOUBLE*125),
                ("Channel_21", DOUBLE*125),
                ("Channel_22", DOUBLE*125))
    
    def Pack(self):
        return C.string_at(C.byref(self), C.sizeof(self))
    
    def Unpack(self, buf):
        return C.cast(C.pointer(C.create_string_buffer(buf)), POINTER(self)).contents
    
    def __init__(self,*args,**kwargs):
        super(MESSAGE_PAYLOAD_500Hz,self).__init__(*args,**kwargs)

class MESSAGE_PAYLOAD_1KHz(Structure):
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
    
    def Pack(self):
        return C.string_at(C.byref(self), C.sizeof(self))
    
    def Unpack(self, buf):
        return C.cast(C.pointer(C.create_string_buffer(buf)), POINTER(self)).contents
    
    def __init__(self,*args,**kwargs):
        super(MESSAGE_PAYLOAD_1KHz,self).__init__(*args,**kwargs)

def MessageReturn(Freq):
    if Freq == 200:
        return  MESSAGE_PAYLOAD_200Hz()
    elif Freq == 250:
        return MESSAGE_PAYLOAD_250Hz()
    elif Freq == 500:
        return MESSAGE_PAYLOAD_500Hz()
    elif Freq == 1000:
        return MESSAGE_PAYLOAD_1KHz()