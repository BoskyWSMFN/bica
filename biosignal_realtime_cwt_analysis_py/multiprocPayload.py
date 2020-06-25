# -*- coding: utf-8 -*-
from ctypes import (c_int64,c_double,c_float)
from appVar import *
import numpy as np

class DATACWT_PAYLOAD(object):
    
    def __init__(self,*args,**kwargs):
        super(DATACWT_PAYLOAD,self).__init__(*args,**kwargs)
        self.Cut = INT64()
        self.Data_Length = INT64()
        self.Timestamp = DOUBLE()
        self.Time_Interval = FLOAT()
        self.nChannel = [np.array([], dtype=DOUBLE, order='C')]*ExpectedChannels
        

class DATAMV_PAYLOAD(object):
    
    def __init__(self,*args,**kwargs):
        super(DATAMV_PAYLOAD,self).__init__(*args,**kwargs)
        self.Cut = INT64()
        self.Data_Length = INT64()
        self.nTimestamp = np.array([], dtype=DOUBLE, order='C')
        self.nChannel = [np.array([], dtype=FLOAT, order='C')]*ExpectedChannels
        self.nWA = [np.array([], dtype=DOUBLE, order='C')]*ExpectedChannels