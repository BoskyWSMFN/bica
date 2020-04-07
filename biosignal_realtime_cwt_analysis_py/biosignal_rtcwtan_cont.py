# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import *
from ctypes.wintypes import *
from datetime import datetime, timedelta
from mpl_toolkits import mplot3d
from matplotlib import pyplot as plt
from scipy import signal
from pycwt.helpers import fft_kwargs
from scipy.fftpack import fft, ifft, fftfreq
import pycwt.wavelet as wavelet
import numpy as np

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
CWT_T = np.empty(0, dtype=float) #dt
GAUSS_FILTER = signal.gaussian(20000, std=10)/sum(signal.gaussian(20000, std=10))
EST_WAVELET = wavelet._check_parameter_wavelet(wavelet.Morlet(6.)) #Morlet wavelet with ω0=6
DJ = 1/12 #Twelve sub-octaves per octaves
J = np.empty(0, dtype=float)
S0 = np.empty(0, dtype=float)
SJ_COL = np.empty(0, dtype=float)
DATALEN = 0


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

def createMVData(data):
    global MEMORY_BUFFER
    return np.array(readMem(FLOAT, MEMORY_BUFFER, True))

def getMVData(data):
    global MEMORY_BUFFER
    data = np.asanyarray(data)
    if data.ndim != 1:
        data = data.ravel()
    return np.concatenate((data, np.ravel(readMem(FLOAT, MEMORY_BUFFER, True))), axis = data.ndim-1)

def deleteData(data):
    return np.delete(data, 0, axis = 0)

#-CWT part--------------------------------------------------------------------
"""
Uses ndarray of μV values, requires map() to use.
"""

def getCwt(data):
    global CWT_T
    global EST_WAVELET
    global SJ_COL
    global DATALEN
    data_ft = fft(data, **fft_kwargs(data))
    N = len(data_ft)
    ftfreqs = 2 * np.pi * fftfreq(N, CWT_T)
    psi_ft_bar = ((SJ_COL * ftfreqs[1] * N) ** .5 * np.conjugate(EST_WAVELET.psi_ft(SJ_COL * ftfreqs)))
    W = ifft(data_ft * psi_ft_bar, axis=1, **fft_kwargs(data_ft, overwrite_x=True))
    Power = np.abs(W[:, :DATALEN])**2
    return np.transpose(np.mean(Power[21:32], axis=0))

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
    ConcatSize = Freq*6
    CwtFreq = Freq/5
    ChannelToShow = 1
    print(Freq)
    Channels = readMem(INT64, pBuf, True)
    Channels = 1
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
    cnt = Cut
    Flow = False
    FlushCwt = True
    FlushTime = True
    FlushMVData = True
    ConcatStart = False
    DATALEN = ConcatSize
    try:
        while Cut-cnt < Freq*1000:
            if not Flow:
                ConcatCut = Cut
                cwtCut = Cut
                cnt = Cut
            oldCut = Cut
            POSITION = Int64Size*2
            Cut = readMem(INT64, pBuf, False)
            
            if oldCut == Cut-1:
                if not Flow:
                    Flow = True
                    print("Job started...\n")
                if Cut-ConcatCut > ConcatSize and not ConcatStart:
                    ConcatStart = True

                POSITION = ((Int64Size*5 + IntegerSize*ExpectedChannels*2 + NameExpectedLength*AnsiCharSize) + 
                       ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*(divmod(Cut, MaxData)[1])))
                AstrTime = datetime_fromdelphi(readMem(DOUBLE, pBuf, True)).timestamp()
                #AstrTime = readMem(DOUBLE, pBuf, True)
                POSITION = (POSITION+Int64Size)
                #MV Data concaternation
                if FlushMVData:
                    DataMV = list(map(createMVData, DataMV))
                    FlushMVData = False
                else:
                    DataMV = list(map(getMVData, DataMV))
                    #
                    if ConcatStart:
                        DataMV = list(map(deleteData, DataMV))
                    #
                # Datetime concaternation
                if FlushTime:
                    CwtT = np.array(AstrTime)
                    FlushTime = False
                else:
                    #CwtT = np.array(AstrTime)
                    CwtT = np.append(CwtT, AstrTime)
                    #
                    if ConcatStart:
                        CwtT = np.delete(CwtT, 0, axis = 0)
                    #

                #"""
                if Cut-cwtCut > CwtFreq and ConcatStart:
                    cwtCut = Cut
                    CWT_T = np.diff(CwtT).mean(axis=0)
                    #CWT_T = 1/Freq
                    S0 = 2 * CWT_T / EST_WAVELET.flambda()
                    J = np.int(np.round(np.log2(DATALEN * CWT_T / S0) / DJ))
                    SJ_COL = (S0 * 2 ** (np.arange(0, J + 1) * DJ))[:, np.newaxis]
                    CwtD = list(map(getCwt, DataMV))
                    #print(ConcatSize)
                    #print(len(DataMV[ChannelToShow-1]))
                    print(datetime.fromtimestamp(AstrTime), Cut, '\n')
                    if FlushCwt:
                        WA = np.asanyarray(CwtD[ChannelToShow - 1])
                        FlushCwt = False
                    else:
                        WA = np.append(WA, np.asanyarray(CwtD[ChannelToShow - 1]))
                        #WA = np.append(WA, np.asanyarray(CwtD[ChannelToShow - 1]), axis = 0)
                        #print(WA.shape)
                        
                #"""

            else:
                continue
    finally:
        print('\n---------------------------------------------------------------\nJob done! Saving...\n')
        kernel32.CloseHandle(hMap)
        kernel32.UnmapViewOfFile(pBuf)
        #xi = np.argsort(WA, axis = 0)
        #yi = np.argsort(WA, axis = 1)
        #X = np.take_along_axis(WA, xi, axis = 0)
        #Y = np.take_along_axis(WA, yi, axis = 1)
        #print(X,'\n', Y, '\n')
        #X, Y = np.meshgrid(X, Y)
        """
        Z = np.sqrt(WA)
        fig = plt.figure()
        ax = plt.axes(projection='3d')
        ax.contour3D(X, Y, Z, 50, cmap='viridis')
        """
        #np.savetxt('bio.csv', np.convolve(WA, GAUSS_FILTER, 'same'), delimiter=",", fmt='%.10f')
        plt.plot(WA, linewidth=0.2)
        #np.savetxt('bio.csv', WA, delimiter=",", fmt='%.10f')
        #pyplot.plot(np.convolve(np.transpose(np.mean(WA[21:32], axis=0)), GAUSS_FILTER, 'same'), linewidth=0.2)
        #pyplot.show()
        #plt.imshow(WA)
        plt.savefig('bio.svg')
        print('Saved!\n')
        



