# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import *
from ctypes.wintypes import *
from datetime import datetime, timedelta
from matplotlib import pyplot as plt
from scipy import signal
from threading import Thread
import pycwt
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
LONGDOUBLE = c_longdouble
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
MEMORY_BUFFER = 0
CHANNELS = 0
CHANNELTOSHOW = 1
gausssig = signal.gaussian(20000, std=10)
GAUSS_FILTER = gausssig/sum(gausssig)
EST_WAVELET = wavelet._check_parameter_wavelet(wavelet.Morlet(6.)) #Morlet wavelet with ω0=6
DJ = 1/12 #Twelve sub-octaves per octaves

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

def readMem(bts, svpos, bytesout=False, datetimedouble=False):
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
    elif datetimedouble:
        return np.array(datetime_fromdelphi(float(bts_n.view(dtype=bts))).timestamp(), dtype=bts)
    else:
        return bts(bts_n.view(dtype=bts)).value

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
class CWT(Thread):
    def __init__(self, wvlt, Datalen, Frequency=FLOAT(1000),
                 Channels=INT64(22), ChannelToShow=INT(1), dj=FLOAT(1/12),
                 gauss_filter=np.array((signal.gaussian(1000, std=10)/
                                        sum(signal.gaussian(1000, std=10))), dtype=FLOAT),
                 Cut=INT64(0), Break=False, Flow=False):
        Thread.__init__(self)
        self.Break = Break
        self.Cut = Cut
        self.Flow = Flow
        self.Channels=Channels
        self.ChannelToShow=ChannelToShow
        self.Frequency=Frequency
        self.DataMV=[list()]*self.Channels.value
        self.CwtT=list()
        self.wvlt=wvlt
        self.gauss_filter=gauss_filter
        self.CwtDT=DOUBLE()
        self.s0=FLOAT()
        self.j=INT()
        self.dj=dj
        self.sj_col=np.empty((0,0), dtype=DOUBLE)
        self.Datalen=FLOAT(Datalen)
    
    def run(self):
        CwtD = [np.empty(0, dtype=DOUBLE)]*self.Channels.value
        WA = np.empty((0,0), dtype=DOUBLE)
        Cut = self.Cut
        FlushCwt = True
        def _getCwt(data):
            """
            data_ft = np.fft.fft(data, n=int(self.Datalen.value))
            N = INT(len(data_ft))
            ftfreqs = np.array(2 * np.pi * np.fft.fftfreq(N.value, self.CwtDT.value), dtype=DOUBLE)
            psi_ft_bar = np.array((self.sj_col * ftfreqs[1] * N.value) ** .5 *
                                  np.conjugate(self.wvlt.psi_ft(self.sj_col * ftfreqs)),
                                  dtype=LONGDOUBLE)
            wave = np.fft.ifft(data_ft * psi_ft_bar, axis=1,
                            n=N.value)
            sel = np.invert(np.isnan(wave).all(axis=1))
            if np.any(sel):
                sj = sj[sel]
                freqs = freqs[sel]
                wave = wave[sel, :]
            """
            wave, scales, freqs, coi, fft, fftfreqs = wavelet.cwt(data[:int(self.Datalen.value)],
                                                               self.CwtDT.value,
                                                               self.dj.value,
                                                               self.s0.value,
                                                               self.j.value,
                                                               self.wvlt)
            
            Power = np.array(np.abs(wave)**2, dtype=DOUBLE)
            #Power = np.array(np.abs(wave[:,:int(self.Datalen.value)])**2, dtype=DOUBLE)
            #return Power#[21:32]
            #return np.array(np.transpose(np.mean(Power, axis = 0)), dtype=DOUBLE)
            return np.convolve(np.transpose(np.average(Power[21:32], axis = 0, weights=scales[21:32])),
            #return np.convolve(np.transpose(np.mean(Power, axis = 0)),
                                        self.gauss_filter, 'same')
        try:
            while not self.Break:
                oldCut = Cut
                Cut = self.Cut
                if oldCut.value == Cut.value-1:
                    if self.Flow:
                        self.Flow = False
                        self.CwtDT = DOUBLE(np.diff(self.CwtT).mean())
                        #self.CwtDT = DOUBLE(1/self.Frequency.value)
                        self.s0 = FLOAT(2 * self.CwtDT.value / self.wvlt.flambda())
                        self.j = INT(np.int(np.round(
                            np.log2(self.Datalen.value * self.CwtDT.value /
                                    self.s0.value) / self.dj.value)))
                        self.sj_col = np.array((self.s0 * 2
                                                ** (np.arange(0, self.j.value + 1)
                                                    *self.dj.value))[:, np.newaxis], dtype=DOUBLE)
                        startTime = datetime.now()
                        CwtD = list(map(_getCwt, self.DataMV))
                        endTime = datetime.now() 
                        print("Сечение:", Cut.value, "Время выполнения расчета для всех каналов: "
                              , endTime-startTime, '\n')
                        if FlushCwt:
                            WA = CwtD[self.ChannelToShow.value - 1]
                            FlushCwt = False
                        else:
                            #WA = signal.correlate(WA, CwtD[self.ChannelToShow.value - 1], mode='same')
                            #self.Break = True
                            #WA = np.concatenate((WA, CwtD[self.ChannelToShow.value - 1]), axis = 0)
                            WA = np.append(WA, CwtD[self.ChannelToShow.value - 1], axis = 0)
                else:
                    continue
        finally:
            #WA = np.convolve(np.transpose(np.mean(WA, axis = 0)), GAUSS_FILTER, 'same')
            print('\n---------------------------------------------------------------\nSaving!\n')
            #WA = np.convolve(WA, self.gauss_filter, 'same')
            plt.plot(WA, linewidth=0.2)
            #np.savetxt('bio.csv', WA, delimiter=",", fmt='%.10f')
            #plt.matshow(WA)
            plt.savefig('bio.svg')
            print('Saved!\n')

#-----------------------------------------------------------------------------

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
    global INT64
    global INT
    global DOUBLE
    global EST_WAVELET
    global DJ
    #
    global GAUSS_FILTER
    
    POSITION = Int64Size*3
    Freq = readMem(INT64, True)
    ConcatSize = Freq*2
    CwtFreq = Freq/10
    #CwtFreq = ConcatSize
    #ConcatSize = CwtFreq
    print(Freq)
    Channels = readMem(INT64, True)
    #Channels = 1
    print(Channels)
    LeadsAct = [0]*Channels
    LeadsPas = [0]*Channels
    Leads = [(0,0)]*Channels
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
    Cut = INT64(readMem(INT64, True, bytesout=True))
    print(Cut.value)
    FlushTime = True
    FlushMVData = True
    Flow = False
    ConcatStart = False
    GAUSS_FILTER = signal.gaussian(CwtFreq, std=10)
    GAUSS_FILTER = GAUSS_FILTER/sum(GAUSS_FILTER)
    try:
        thread = CWT(EST_WAVELET, ConcatSize,
                     INT64(Freq), INT64(Channels), INT(CHANNELTOSHOW), FLOAT(DJ),
                     np.array(GAUSS_FILTER, dtype=FLOAT))
        thread.daemon = True
        thread.start()
        while True:
            oldCut = Cut
            if not Flow:
                CwtCut = Cut
                ConcatCut = Cut
                POSITION = Int64Size*2
                Cut = INT64(readMem(INT64, False, bytesout=True))
            else:
                POSITION = Int64Size*2
                Cut = INT64(readMem(INT64, False, bytesout=True))
                POSITION = (((Int64Size*5 + IntegerSize*ExpectedChannels*2 +
                              NameExpectedLength*AnsiCharSize) + 
                       ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)
                        *(divmod(Cut.value, MaxData)[1])))) + DateTimeSize
                Cut = INT64(readMem(INT64, False, bytesout=True))
                thread.Cut = Cut
            
            if oldCut.value == Cut.value-1:
                if not Flow:
                    Flow = True
                    print("Job started...\n")
                    POSITION = ((Int64Size*5 + IntegerSize*ExpectedChannels*2
                                 + NameExpectedLength*AnsiCharSize) + 
                       ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)
                        *(divmod(Cut.value, MaxData)[1])))
                else:
                    POSITION = (POSITION-DateTimeSize)
                
                if Cut.value-ConcatCut.value > ConcatSize and not ConcatStart:
                    ConcatStart = True
                
                if Cut.value-CwtCut.value > CwtFreq and ConcatStart:
                    CwtCut = Cut
                    thread.Flow = True

                AstrTime = readMem(DOUBLE, True, datetimedouble=True)
                POSITION = (POSITION+Int64Size)
                #MV Data concaternation
                if FlushMVData:
                    thread.DataMV = list(map(createMVData, thread.DataMV))
                    FlushMVData = False
                else:
                    thread.DataMV = list(map(getMVData, thread.DataMV))
                    #
                    if ConcatStart:
                        thread.DataMV = list(map(deleteData, thread.DataMV))
                    #
                # Datetime concaternation
                if FlushTime:
                    thread.CwtT = np.ndarray((1,), buffer=AstrTime, dtype=DOUBLE, order='C')
                    FlushTime = False
                else:
                    thread.CwtT = np.concatenate((thread.CwtT,
                                                  np.ndarray((1,),
                                                             buffer=AstrTime,
                                                             dtype=DOUBLE, order='C')),
                                                 axis = 0)
                    #
                    if ConcatStart:
                        thread.CwtT = np.delete(thread.CwtT, 0, axis = 0)
                    #

                #"""

            else:
                continue
    finally:
        #print('\n---------------------------------------------------------------\nJob done! Saving...\n')
        kernel32.CloseHandle(H_MAP)
        kernel32.UnmapViewOfFile(MEMORY_BUFFER)
        thread.Break = True
        thread.join(timeout=20)
        #thread.daemon = False
        #WA = np.convolve(np.transpose(np.mean(WA, axis = 0)), GAUSS_FILTER, 'same')
        print('\n---------------------------------------------------------------\nJob done!\n')

if __name__ == '__main__':
    handle_nonzero_success(H_MAP)
    if H_MAP == INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(H_MAP)
        kernel32.UnmapViewOfFile(MEMORY_BUFFER)
        raise Exception("Failed to create file mapping")
    main()