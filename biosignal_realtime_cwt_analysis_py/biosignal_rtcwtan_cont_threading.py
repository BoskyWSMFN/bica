# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import *
from ctypes.wintypes import *
from datetime import datetime, timedelta
from matplotlib import pyplot as plt
from scipy import signal
from threading import Thread
from numba import jit
import pycwt.wavelet as wavelet
import numpy as np

#clibptr = cdll.LoadLibrary("libpointers.so")
#clibptr = cdll.msvcrt
kernel32 = WinDLL('kernel32', use_last_error=True)
###
FILE_MAP_COPY       = 0x0001
FILE_MAP_WRITE      = 0x0002
FILE_MAP_READ       = 0x0004
FILE_MAP_ALL_ACCESS = 0x001f
FILE_MAP_EXECUTE    = 0x0020
PAGE_READWRITE      = 0x04
###
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
MAXDWORD = DWORD(0xffffffff) #From Delphi
INVALID_HANDLE_VALUE = HANDLE(-1)
DELPHI_EPOCH = datetime(1899, 12, 30) #From Delphi
###
NameExpectedLength = 512
Int64Size = sizeof(INT64)
DateTimeSize = sizeof(DOUBLE)
IntegerSize = sizeof(INT)
SingleSize = sizeof(FLOAT)
AnsiCharSize = sizeof(CHAR) #Name written in chars
ExpectedChannels = 22 #quantity
MaxData=10000
SA = None
EXPECTED_SIZE = Int64Size*5 + IntegerSize*ExpectedChannels*2 + NameExpectedLength*AnsiCharSize + (DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*MaxData
"""
Data model code in Delphi:
    nkdVersion: int64;
    nkdReady : int64;
    nkdCut: int64; // Actual cut. If equals -1 do nothing
    nkdFrequency: int64;
    nkdChannels:  int64; // ExpectedChannels
    nkdLeadsAct: array[1..22] of integer; 
    nkdLeadsPas: array[1..22] of integer;
    nkdName: array[1..512] of AnsiChar;
    nkdDATA_MV: array [0..nkMaxData] of
     record
      nkdAstrTime: tDateTime;
      nkdCutCnt: int64; //Cut counter
      nkdData:array[1..22] of single; // μV values
"""
TAGNAME = LPCWSTR('NeuroKMData') #Expected filename
###
POSITION = 0
CUT = 0
MEMORY_BUFFER = 0
CHANNELS = 0
CHANNELTOSHOW = 3
DATA_MV = [list()]*ExpectedChannels
CWT_T = np.empty(0, dtype=float)
CWT_DT = np.empty(0, dtype=float) #dt
GAUSS_FILTER = signal.gaussian(20000, std=10)/sum(signal.gaussian(20000, std=10))
EST_WAVELET = wavelet._check_parameter_wavelet(wavelet.Morlet(6.)) #Morlet wavelet with ω0=6
DJ = 1/12 #Twelve sub-octaves per octaves
J = np.empty(0, dtype=float)
S0 = np.empty(0, dtype=float)
SJ_COL = np.empty(0, dtype=float)
WA = np.empty(0, dtype=float)
DATALEN = 0
CONCATSTART = False
FLOW = False
N_FFT = 0

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

#H_MAP = kernel32.CreateFileMappingW(INVALID_HANDLE_VALUE, SA, PAGE_READWRITE, 0, EXPECTED_SIZE, TAGNAME)
H_MAP = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, TAGNAME)
MEMORY_BUFFER = kernel32.MapViewOfFile(H_MAP, FILE_MAP_ALL_ACCESS, 0, 0, EXPECTED_SIZE)

def pBufMod(pBuf):
    global MEMORY_BUFFER
    MEMORY_BUFFER = pBuf

def dtMod(dt):
    global CWT_DT
    CWT_DT = dt

def posMod(pos):
    global POSITION
    POSITION = pos

def getCurPos():
    global POSITION
    return POSITION

def datetime_fromdelphi(dvalue):
    return DELPHI_EPOCH + timedelta(days=dvalue)

def readMem(bts, svpos, bytesout=False):
    global POSITION
    global MEMORY_BUFFER
    size = sizeof(bts)
    bts_s = create_string_buffer(size)
    source = MEMORY_BUFFER + POSITION
    length = SIZE_T(size)
    RtlMoveMemory(bts_s, source, length)
    bts_n = np.array(bts_s)
    if svpos:
        POSITION += size
        posMod(POSITION)
    if bytesout:
        return bts_n.view(dtype=bts)
    else:
        return bts(bts_n.view(dtype=bts)).value

"""
def createMVData(data):
    return np.array(readMem(FLOAT, True))

def getMVData(data):
    data = np.asanyarray(data)
    if data.ndim != 1:
        data = data.ravel()
    return np.concatenate((data, np.ravel(readMem(FLOAT, True))), axis = data.ndim-1)
"""
def createMVData(data):
    return np.ndarray((1,), buffer=readMem(FLOAT, True, bytesout=True), dtype=FLOAT, order='C')


def getMVData(data):
    return np.concatenate((data, np.ndarray((1,), buffer=readMem(FLOAT, True, bytesout=True), dtype=FLOAT, order='C')), axis = 0)

def deleteData(data):
    return np.delete(data, 0, axis = 0)

#-CWT part--------------------------------------------------------------------
"""
Uses ndarray of μV values, requires map() to use.
"""
@jit(forceobj=True, target='cpu', parallel=True)
def getCwt(data):
    global CWT_DT
    global EST_WAVELET
    global SJ_COL
    global DATALEN
    global GAUSS_FILTER
    data_ft = np.fft.fft(data, n=N_FFT)
    N = len(data_ft)
    ftfreqs = 2 * np.pi * np.fft.fftfreq(N, CWT_DT)
    psi_ft_bar = ((SJ_COL * ftfreqs[1] * N) ** .5 * np.conjugate(EST_WAVELET.psi_ft(SJ_COL * ftfreqs)))
    W = np.fft.ifft(data_ft * psi_ft_bar, axis=1, n=np.int(2 ** np.ceil(np.log2(N))))
    Power = np.abs(W[:, :DATALEN])**2
    #return Power[21:32]
    return np.convolve(np.transpose(np.mean(Power[21:32], axis = 0)), GAUSS_FILTER, 'same')

#-----------------------------------------------------------------------------

class CWT(Thread):
    def __init__(self, CwtFreq, Break=False):
        Thread.__init__(self)
        self.CwtFreq = CwtFreq
        self.Break = Break
    
    def run(self):
        global EST_WAVELET
        global WA
        global CWT_T
        global CWT_DT
        global J
        global DJ
        global S0
        global SJ_COL
        global CUT
        global DATA_MV
        global CHANNELS
        global CHANNELTOSHOW
        global CONCATSTART
        global FLOW
        CwtD = [np.empty(0, dtype=float)]*CHANNELS
        Cut = CUT
        FlushCwt = True
        while not self.Break:
            oldCut = Cut
            Cut = CUT
            if not FLOW:
                cwtCut = Cut
            if oldCut == Cut-1:
                if Cut-cwtCut > self.CwtFreq and CONCATSTART:
                    cwtCut = Cut
                    CWT_DT = np.diff(CWT_T).mean(axis=0)
                    #CWT_DT = 1/Freq
                    S0 = 2 * CWT_DT / EST_WAVELET.flambda()
                    J = np.int(np.round(np.log2(DATALEN * CWT_DT / S0) / DJ))
                    SJ_COL = (S0 * 2 ** (np.arange(0, J + 1) * DJ))[:, np.newaxis]
                    CwtD = list(map(getCwt, DATA_MV))
                    print(CUT, CWT_DT, '\n')
                    if FlushCwt:
                        WA = CwtD[CHANNELTOSHOW - 1]
                        FlushCwt = False
                    else:
                        WA = np.concatenate((WA, CwtD[CHANNELTOSHOW - 1]), axis = 0)
            else:
                continue

def main():
    #
    global IntegerSize
    global Int64Size
    global AnsiCharSize
    global DateTimeSize
    global NameExpectedLength
    global ExpectedChannels
    global MaxData
    #
    global H_MAP
    global MEMORY_BUFFER
    global POSITION
    global CUT
    global CHANNELS
    global CONCATSTART
    global FLOW
    global INT64
    global INT
    global DOUBLE
    global DATA_MV
    global CWT_T
    global EST_WAVELET
    global DATALEN
    global N_FFT
    global CWT_DT
    global J
    global DJ
    global S0
    global SJ_COL
    #
    global WA
    global GAUSS_FILTER
    
    POSITION = Int64Size*3
    Freq = readMem(INT64, True)
    ConcatSize = Freq*6
    CwtFreq = Freq/10
    DATALEN = ConcatSize
    N_FFT = np.int(2 ** np.ceil(np.log2(DATALEN)))
    print(Freq)
    Channels = readMem(INT64, True)
    #Channels = 1
    CHANNELS = Channels
    print(Channels)
    LeadsAct = [0]*Channels
    LeadsPas = [0]*Channels
    Leads = [(0,0)]*Channels
    DATA_MV = [list()]*Channels
    for i in range(0, Channels):
        LeadsAct[i] = readMem(INT, True)
        cp = POSITION
        POSITION = (cp + IntegerSize*(ExpectedChannels - 1))
        LeadsPas[i] = readMem(INT, False)
        POSITION = cp
        Leads[i] = (LeadsAct[i],LeadsPas[i])
    POSITION = (cp+IntegerSize*(ExpectedChannels)+NameExpectedLength)
    print(Leads)
    POSITION = Int64Size*2
    Cut = readMem(INT64, True)
    print(Cut)
    FlushTime = True
    FlushMVData = True
    FLOW = False
    try:
        thread = CWT(CwtFreq)
        thread.daemon = True
        thread.start()
        while True:
            oldCut = Cut
            if not FLOW:
                ConcatCut = Cut
                POSITION = Int64Size*2
                Cut = readMem(INT64, False)
            else:
                POSITION = Int64Size*2
                Cut = readMem(INT64, False)
                POSITION = (((Int64Size*5 + IntegerSize*ExpectedChannels*2 + NameExpectedLength*AnsiCharSize) + 
                       ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*(divmod(Cut, MaxData)[1])))) + DateTimeSize
                Cut = readMem(INT64, False)
                CUT = Cut
            
            if oldCut == Cut-1:
                if not FLOW:
                    FLOW = True
                    print("Job started...\n")
                    POSITION = ((Int64Size*5 + IntegerSize*ExpectedChannels*2 + NameExpectedLength*AnsiCharSize) + 
                       ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*(divmod(Cut, MaxData)[1])))
                else:
                    POSITION = (POSITION-DateTimeSize)
                if Cut-ConcatCut > ConcatSize and not CONCATSTART:
                    CONCATSTART = True

                #AstrTime = datetime_fromdelphi(readMem(DOUBLE, True)).timestamp()
                AstrTime = readMem(DOUBLE, True, bytesout=True)
                POSITION = (POSITION+Int64Size)
                #MV Data concaternation
                if FlushMVData:
                    DATA_MV = list(map(createMVData, DATA_MV))
                    #print(DATA_MV)
                    FlushMVData = False
                else:
                    DATA_MV = list(map(getMVData, DATA_MV))
                    #print(DATA_MV)
                    #
                    if CONCATSTART:
                        DATA_MV = list(map(deleteData, DATA_MV))
                    #
                # Datetime concaternation
                if FlushTime:
                    CWT_T = np.ndarray((1,), buffer=AstrTime, dtype=DOUBLE, order='C')
                    FlushTime = False
                else:
                    CWT_T = np.concatenate((CWT_T, np.ndarray((1,), buffer=AstrTime, dtype=DOUBLE, order='C')), axis = 0)
                    #
                    if CONCATSTART:
                        CWT_T = np.delete(CWT_T, 0, axis = 0)
                    #

                #"""

            else:
                continue
    finally:
        #print('\n---------------------------------------------------------------\nJob done! Saving...\n')
        kernel32.CloseHandle(H_MAP)
        kernel32.UnmapViewOfFile(MEMORY_BUFFER)
        thread.Break = True
        thread.join(timeout=5)
        #thread.daemon = False
        #WA = np.convolve(np.transpose(np.mean(WA, axis = 0)), GAUSS_FILTER, 'same')
        print('\n---------------------------------------------------------------\nJob done! Saving...\n')
        plt.plot(WA, linewidth=0.2)
        #np.savetxt('bio.csv', WA, delimiter=",", fmt='%.10f')
        #plt.matshow(WA)
        plt.savefig('bio.svg')
        print('Saved!\n')

if __name__ == '__main__':
    handle_nonzero_success(H_MAP)
    if H_MAP == INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(H_MAP)
        kernel32.UnmapViewOfFile(MEMORY_BUFFER)
        raise Exception("Failed to create file mapping")
    main()