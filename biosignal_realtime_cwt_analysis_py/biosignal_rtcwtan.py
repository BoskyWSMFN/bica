#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import division
from ctypes import *
from ctypes.wintypes import *
from datetime import datetime, timedelta
from matplotlib import pyplot
from pycwt.helpers import find
from scipy import signal
from scipy.ndimage import gaussian_filter
import pycwt as wavelet
import numpy as np
import sys
import struct

#clibptr = cdll.LoadLibrary("libpointers.so")
#clibptr = cdll.msvcrt
kernel32 = WinDLL('kernel32', use_last_error=True)

FILE_MAP_COPY       = 0x0001
FILE_MAP_WRITE      = 0x0002
FILE_MAP_READ       = 0x0004
FILE_MAP_ALL_ACCESS = 0x001f
FILE_MAP_EXECUTE    = 0x0020
PAGE_READWRITE      = 0x04

PVOID = LPVOID
SIZE_T = c_size_t
VOID_P = c_void_p
WCHAR_P = c_wchar_p
CHAR_P = c_char_p
WCHAR = c_wchar
CHAR = c_char
INT64 = c_int64
INT = c_int
FLOAT = c_float
DOUBLE = c_double
MAXDWORD = DWORD(0xffffffff)
INVALID_HANDLE_VALUE = HANDLE(-1)
DELPHI_EPOCH = datetime(1899, 12, 30)

"""
class EFFECT(Structure):
    _fields_ = (("j", c_int),
                ("_ptr", c_void_p))
    @property
    def ptr(self):
        offset = type(self)._ptr.offset
        return (c_void_p).from_buffer(self, offset)
"""

class SECURITY_ATTRIBUTES(Structure):
    """_fields_ = (('nLength', DWORD),
                ('lpSecurityDescriptor', LPVOID),
                ('bInheritHandle', BOOL))"""
    _fields_ = [
        ('nLength', DWORD),
        ('lpSecurityDescriptor', VOID_P),
        ('bInheritHandle', BOOL),
    ]

    def __init__(self, *args, **kwargs):
        super(SECURITY_ATTRIBUTES, self).__init__(*args, **kwargs)
        self.nLength = sizeof(SECURITY_ATTRIBUTES)

    @property
    def descriptor(self):
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value):
        self._descriptor = value
        self.lpSecurityDescriptor = addressof(value)
LPSECURITY_ATTRIBUTES = POINTER(SECURITY_ATTRIBUTES)

class MEMORY_BASIC_INFORMATION(Structure):
    _fields_ = (('BaseAddress',       PVOID),
                ('AllocationBase',    PVOID),
                ('AllocationProtect', DWORD),
                ('RegionSize',        SIZE_T),
                ('State',             DWORD),
                ('Protect',           DWORD),
                ('Type',              DWORD))
PMEMORY_BASIC_INFORMATION = POINTER(MEMORY_BASIC_INFORMATION)

def errcheck_bool(result, func, args):
    if not result:
        raise WinError(get_last_error())
    return args

def handle_nonzero_success(result):
    if result == 0:
        raise WindowsError()

kernel32.CreateFileMappingW.errcheck = errcheck_bool
kernel32.CreateFileMappingW.restype = HANDLE
kernel32.CreateFileMappingW.argtypes = (
    HANDLE, # _In_ hFileMappingObject
    LPSECURITY_ATTRIBUTES, # _In_ lpFileMappingAttributes
    DWORD, # _In_ dwDesiredAccess
    DWORD, # _In_ dwFileOffsetHigh
    DWORD, # _In_ dwFileOffsetLow
    LPCWSTR) # _In_ lpName

kernel32.VirtualQuery.errcheck = errcheck_bool
kernel32.VirtualQuery.restype = SIZE_T
kernel32.VirtualQuery.argtypes = (
    LPCVOID,                   # _In_opt_ lpAddress
    PMEMORY_BASIC_INFORMATION, # _Out_    lpBuffer
    SIZE_T)                    # _In_     dwLength

kernel32.OpenFileMappingW.errcheck = errcheck_bool
kernel32.OpenFileMappingW.restype = HANDLE
kernel32.OpenFileMappingW.argtypes = (
    DWORD,   # _In_ dwDesiredAccess
    BOOL,    # _In_ bInheritHandle
    LPCWSTR) # _In_ lpName

kernel32.MapViewOfFile.errcheck = errcheck_bool
kernel32.MapViewOfFile.restype = LPVOID
kernel32.MapViewOfFile.argtypes = (
    HANDLE, # _In_ hFileMappingObject
    DWORD,  # _In_ dwDesiredAccess
    DWORD,  # _In_ dwFileOffsetHigh
    DWORD,  # _In_ dwFileOffsetLow
    SIZE_T) # _In_ dwNumberOfBytesToMap

kernel32.CloseHandle.errcheck = errcheck_bool
kernel32.CloseHandle.argtypes = (HANDLE,)

kernel32.UnmapViewOfFile.errcheck = errcheck_bool
kernel32.UnmapViewOfFile.argtypes = (LPVOID,)

RtlMoveMemory = kernel32.RtlMoveMemory
RtlMoveMemory.argtypes = (
    VOID_P,
    VOID_P,
    SIZE_T,)

POSITION = 0
MEMORY_BUFFER = 0
CWT_T = np.empty(0, dtype=float)
GAUSS_FILTER = signal.gaussian(20000, std=10)/sum(signal.gaussian(20000, std=10))

def pBufMod(pBuf):
    global MEMORY_BUFFER
    MEMORY_BUFFER = pBuf

def dtMod(dt):
    global CWT_T
    CWT_T = dt

def posMod(pos):
    global POSITION
    POSITION = pos

def getCurPos():
    global POSITION
    return POSITION

"""
def convertcat(char):  
    res = ""   
    for i in char: 
        res += i    
    return res
"""

def datetime_fromdelphi(dvalue):
    return DELPHI_EPOCH + timedelta(days=dvalue)

def readMem(bts, pBuf, svpos):
    global POSITION
    size = sizeof(bts)
    bts_s = create_string_buffer(size)
    source = pBuf + POSITION
    length = SIZE_T(size)
    RtlMoveMemory(bts_s, source, length)
    bts_n = np.array(bts_s)
    if svpos:
        POSITION += size
        posMod(POSITION)
    return bts(bts_n.view(dtype=bts)).value

def getMVData(data):
    global MEMORY_BUFFER
    return np.append(data, readMem(FLOAT, MEMORY_BUFFER, True))

#-CWT part--------------------------------------------------------------------
"""
Uses ndarray of μV values, requires map() to use.
"""

def getCwt(data):
    global CWT_T
    global GAUSS_FILTER
    coefs, scales, freqs, coi, fft, fftfreqs = wavelet.cwt(data, dt=CWT_T, wavelet=wavelet.Morlet(6.))#, freqs=np.full((100,), 1000, dtype=int))
    x1 = np.abs(coefs)**2
    z2_0 = np.transpose(np.mean(x1[21:32], axis=0))
    return np.average(np.convolve(z2_0, GAUSS_FILTER, 'same'))

#-----------------------------------------------------------------------------

def getEmpty(data):
    return np.empty(0, dtype=float)

if __name__ == '__main__':
    
    NameExpectedLength = 512
    Int64Size = sizeof(INT64)
    DateTimeSize = sizeof(DOUBLE)
    IntegerSize = sizeof(INT)
    SingleSize = sizeof(FLOAT)
    AnsiCharSize = sizeof(CHAR)
    
    ExpectedChannels = 22
    MaxData=10000

    SA = None
    
    EXPECTED_SIZE = Int64Size*5 + IntegerSize*ExpectedChannels*2 + NameExpectedLength*AnsiCharSize + (DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*MaxData
    
    TAGNAME = LPCWSTR('NeuroKMData')
    
    #hMap = kernel32.CreateFileMappingW(INVALID_HANDLE_VALUE, SA, PAGE_READWRITE, 0, EXPECTED_SIZE, TAGNAME)
    hMap = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, TAGNAME)
    handle_nonzero_success(hMap)
    if hMap == INVALID_HANDLE_VALUE:
        raise Exception("Failed to create file mapping")
    pBuf = kernel32.MapViewOfFile(hMap, FILE_MAP_ALL_ACCESS, 0, 0, EXPECTED_SIZE)
    pBufMod(pBuf)
    POSITION = Int64Size*3
    Freq = readMem(INT64, pBuf, True)
    CwtFreq = Freq/10
    print(Freq)
    Channels = readMem(INT64, pBuf, True)
    print(Channels)
    LeadsAct = [0]*Channels
    LeadsPas = [0]*Channels
    Leads = [(0,0)]*Channels
    DataMV = [np.empty(0, dtype=float)]*Channels
    CwtD = [np.empty(0, dtype=float)]*Channels
    CwtT = np.empty(0, dtype=float)
    WA = np.empty(0, dtype=float)
    for i in range(0, Channels):
        LeadsAct[i] = readMem(INT, pBuf, True)
        cp = POSITION
        POSITION = (cp + IntegerSize*(ExpectedChannels - 1))
        LeadsPas[i] = readMem(INT, pBuf, False)
        POSITION = cp
        Leads[i] = (LeadsAct[i],LeadsPas[i])
    POSITION = (cp+IntegerSize*(ExpectedChannels)+NameExpectedLength)
    print(Leads)
    POSITION = Int64Size*2
    Cut = readMem(INT64, pBuf, True)
    print(Cut)
    cwtCut = Cut
    cnt = Cut
    try:
        while Cut-cnt < 20000:
            oldCut = Cut
            POSITION = Int64Size*2
            Cut = readMem(INT64, pBuf, False)
            
            if oldCut == Cut-1:

                POSITION = ((Int64Size*5 + IntegerSize*ExpectedChannels*2 + NameExpectedLength*AnsiCharSize) + 
                       ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*(divmod(Cut, MaxData)[1])))
                AstrTime = datetime_fromdelphi(readMem(DOUBLE, pBuf, True)).timestamp()
                POSITION = (POSITION+Int64Size)
                DataMV = list(map(getMVData, DataMV))
                CwtT = np.append(CwtT, AstrTime)
                if Cut-cwtCut >= CwtFreq:
                    cwtCut = Cut
                    if find(np.diff(CwtT)<=0).size > 0:
                        CwtT = np.linspace(start=np.min(CwtT), stop=np.max(CwtT), num=CwtT.size)
                    CwtT = CwtT-np.min(CwtT)
                    CWT_T = np.mean(np.diff(CwtT))
                    CwtD = list(map(getCwt, DataMV))
                    CwtT = np.empty(0, dtype=float)
                    DataMV = list(map(getEmpty, DataMV))
                    print(datetime.fromtimestamp(AstrTime), Cut, CwtD, '\n')
                    WA = np.append(WA, CwtD[0])
            else:
                continue
    finally:
        print('---------------------------------------------------------------\nJob done!\n')
        kernel32.CloseHandle(hMap)
        kernel32.UnmapViewOfFile(pBuf)
        #np.savetxt('D:\\bio.csv', np.convolve(WA, GAUSS_FILTER, 'same'), delimiter=",", fmt='%.10f')
        #pyplot.plot(np.convolve(WA, GAUSS_FILTER, 'same'), linewidth=0.2)
        np.savetxt('D:\\bio.csv', WA, delimiter=",", fmt='%.10f')
        pyplot.plot(WA, linewidth=0.2)
        pyplot.savefig('D:\\bio.svg')