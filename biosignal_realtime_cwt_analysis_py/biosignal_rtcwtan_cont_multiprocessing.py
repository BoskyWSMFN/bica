# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import *
from ctypes.wintypes import *
from datetime import datetime, timedelta
from matplotlib import pyplot as plt
from scipy import signal
from multiprocessing import Process, Queue, Pool
import socket
import sys
import pycwt.wavelet as wavelet
import numpy as np
import win32api, win32process, win32con

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
DELPHI_EPOCH = datetime(1899, 12, 30) #Поправка на формат времени в Delphi
###
NameExpectedLength = 512 # Ожидаемый размер имени
Int64Size = sizeof(INT64)
DateTimeSize = sizeof(DOUBLE)
IntegerSize = sizeof(INT)
SingleSize = sizeof(FLOAT)
AnsiCharSize = sizeof(CHAR) #Имя записано посимвольно
ExpectedChannels = 22 # Ожидаемое количество каналов
MaxData=10000 # Максимальный размер буфера данны в общей памяти
STOPIT = False
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
TAGNAME = LPCWSTR('NeuroKMData') #Ожидаемое наименование файла в общей памяти
###
HOST = '127.0.0.1' # Локалхост
PORT = 50 # Порт. Незабитые - >1023
###
MEMORY_BUFFER = 0
POSITION = 0
CHANNELTOSHOW = 1
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

def datetime_fromdelphi(dvalue):
    return DELPHI_EPOCH + timedelta(days=dvalue)

def readMem(bts, svpos, bytesout=False, datetimedouble=False):
    global POSITION
    size = sizeof(bts)
    bts_s = create_string_buffer(size)
    source = MEMORY_BUFFER + POSITION
    length = SIZE_T(size)
    RtlMoveMemory(bts_s, source, length)
    bts_n = np.array(bts_s)
    if svpos:
        POSITION += size
    if bytesout:
        return bts_n.view(dtype=bts)
    elif datetimedouble:
        return np.array(datetime_fromdelphi(float(bts_n.view(dtype=bts))).timestamp(), dtype=bts)
    else:
        return bts(bts_n.view(dtype=bts)).value

def setpriority(pid=None,priority=1):
    """ Set The Priority of a Windows Process.  Priority is a value between 0-5 where
        2 is normal priority.  Default sets the priority of the current
        python process but can take any valid process ID. """
    
    priorityclasses = [win32process.IDLE_PRIORITY_CLASS,
                       win32process.BELOW_NORMAL_PRIORITY_CLASS,
                       win32process.NORMAL_PRIORITY_CLASS,
                       win32process.ABOVE_NORMAL_PRIORITY_CLASS,
                       win32process.HIGH_PRIORITY_CLASS,
                       win32process.REALTIME_PRIORITY_CLASS]
    if pid == None:
        pid = win32api.GetCurrentProcessId()
    handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
    win32process.SetPriorityClass(handle, priorityclasses[priority])


#-Непрерывное вейвлет-преобразование, обрезка и сглаживание-------------------

def analysis(dataq):
    
    def npa2s(a):
        return np.array2string(a, separator=',')
    
    def _getCwt(data, dt, s0, j):
        def _cwt(data):
            """
            datalen = len(data)
            data_ft = np.fft.fft(data, n=int(datalen))
            N = len(data_ft)
            ftfreqs = 2 * np.pi * np.fft.fftfreq(N, dt)
            psi_ft_bar = (self.sj_col * ftfreqs[1] * N) ** .5 *
                                  np.conjugate(EST_WAVELET.psi_ft(self.sj_col * ftfreqs))
            wave = np.fft.ifft(data_ft * psi_ft_bar, axis=1,
                            n=N)
            sel = np.invert(np.isnan(wave).all(axis=1))
            if np.any(sel):
                sj = sj[sel]
                freqs = freqs[sel]
                wave = wave[sel, :]
            """
            wave, scales, freqs, coi, fft, fftfreqs = wavelet.cwt(data,
                                                               dt,
                                                               DJ,
                                                               s0,
                                                               j,
                                                               EST_WAVELET) # Выше указан алгоритм произведения анализа
            
            Power = np.abs(wave)**2 # Мощность по модулю в квадрате
            tmean = np.transpose(np.mean(Power[21:32], axis = 0)) # Обрезка по диапазону [21:32], вычисление среднего и транспонирование получившейся 2D-матрицы, производится для совмещения "сырого" и обработанного сигнала по длительности.
            gauss_filter = signal.gaussian(len(tmean), std=10)
            gauss_filter = gauss_filter/sum(gauss_filter) # Создание сглаживающей гаусианны с длиной, равной размеру окна, для дальнейшей свертки.
            #return tmean
            return signal.convolve(tmean, gauss_filter, 'same') # Свертка с фильтром
            #return Power
            #return data
        
        return list(map(_cwt, data))
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    
    WA = list()
    try:
        FlushCwt = True
        while True:
            # Чтение данных из очереди
            Cut = dataq.get()
            if Cut.value == -1:
                break
            Channels = dataq.get()
            Datalen = dataq.get()
            CwtT = dataq.get()
            DataOP = dataq.get()
            #
            
            # Отправка данных на анализ и преобразование
            #startTime = datetime.now()
            CwtDT = np.diff(CwtT).mean() # Вычисление интервала между точками
            s0 = 2 * CwtDT / EST_WAVELET.flambda()
            j = np.int(np.round(np.log2(Datalen * CwtDT / s0) / DJ))
            CwtD = _getCwt(DataOP, CwtDT, s0, j)
            #endTime = datetime.now()
            #
            message = str(Cut.value)+','+str(Channels)+','+str(Datalen)+','+str(datetime.now().timestamp())+','+str(CwtDT)+','+','.join(map(npa2s, CwtD))
            sock.sendall(bytes(message, 'ascii'))
            #
            if FlushCwt:
                WA = CwtD[CHANNELTOSHOW - 1]
                FlushCwt = False
            else:
                WA = np.append(WA, CwtD[CHANNELTOSHOW - 1], axis = 0)
            #
            
    finally:
        dataq.put(WA)
        #sock.close()

#-----------------------------------------------------------------------------
        
#-Чтение из общей памяти, отправка данных в очередь---------------------------

def file_mapping(dataq, Analysis):
    
    global POSITION

    def _createMVData(data):
        return np.ndarray((1,), buffer=readMem(FLOAT, True, bytesout=True),
                          dtype=FLOAT, order='C')

    def _getMVData(data):
        return np.concatenate((data, np.ndarray((1,), buffer=readMem(FLOAT,
                                                                     True,
                                                                     bytesout=True),
                                                dtype=FLOAT, order='C')), axis = 0)
    
    def _OPret(data, datalen):
        def _mapret(data):
            return data[-(datalen):,]
        return list(map(_mapret, data)) # Выделение из общего массива считанных данных окна, равного CwtFreq
    
    POSITION = Int64Size*3
    Freq = readMem(INT64, True) # Частота оцифровки
    CwtFreq = int(Freq/4) # Частота преобразования и отправки данных и длина окна
    print('Частота оцифровки: ', Freq, 'Гц')
    Channels = readMem(INT64, True) #Фактическое количество используемых каналов
    print('Количество каналов: ', Channels)
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
    print('Отведения: ', Leads)
    POSITION = Int64Size*2
    Cut = INT64(readMem(INT64, True, bytesout=True))
    FlushTime = True
    FlushMVData = True
    Flow = False
    try:
        setpriority(priority=5) # Задание процессу чтения из общей памяти приоритета реального времени
        Datalen = 0
        DataMV = [list()]*Channels
        while True:
            oldCut = Cut
            POSITION = Int64Size*2
            Cut = INT64(readMem(INT64, False, bytesout=True))
            if not Flow:
                CwtCut = Cut
                ConcatCut = Cut
            
            if oldCut.value == Cut.value-1:
                Datalen += 1
                if not Flow:
                    Flow = True
                    print("Анализ...\n")
                
                POSITION = ((Int64Size*5 + IntegerSize*ExpectedChannels*2 +
                             NameExpectedLength*AnsiCharSize) +
                            ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*
                             (divmod(Cut.value, MaxData)[1])))

                AstrTime = readMem(DOUBLE, True, datetimedouble=True) # Чтение момента регистрации сигналов из общей памяти
                POSITION = (POSITION+Int64Size)
                
                # Чтение данных из общей памяти и конкатенация биосигнала в мкВ в массив типа Float
                if FlushMVData:
                    DataMV = list(map(_createMVData, DataMV))
                    FlushMVData = False
                else:
                    DataMV = list(map(_getMVData, DataMV))
                #

                # Конкатенация времени в массив типа Double
                if FlushTime:
                    CwtT = np.ndarray((1,), buffer=AstrTime, dtype=DOUBLE, order='C')
                    FlushTime = False
                else:
                    CwtT = np.concatenate((CwtT,
                                                  np.ndarray((1,),
                                                             buffer=AstrTime,
                                                             dtype=DOUBLE, order='C')),
                                                 axis = 0)

                #
                
                # Отправка массива данных в очередь для дальнейшей обработки с окном, равным CwtFreq
                if Cut.value-CwtCut.value >= CwtFreq:
                    CwtCut = Cut
                    dataq.put(Cut)
                    dataq.put(Channels)
                    dataq.put(Datalen)
                    dataq.put(CwtT[-(Datalen):,])
                    dataq.put(_OPret(DataMV, Datalen))
                    print('Длина окна: ', Datalen)
                    Datalen = 0

    finally:
        dataq.put(INT64(-1))
        kernel32.CloseHandle(H_MAP)
        kernel32.UnmapViewOfFile(MEMORY_BUFFER)
        WA = dataq.get()
        dataq.close()
        dataq.join_thread()
        #File_mapping.join()
        Analysis.join()
        print('\n---------------------------------------------------------------\nАнализ окончен.',
              'Сохранение результатов!\n')
        plt.plot(DataMV[CHANNELTOSHOW - 1], linewidth=0.4)
        plt.plot(WA, linewidth=0.2)
        plt.savefig('bio.svg')
        print('Сохранено в <working_directory>\bio.svg!\n')

if __name__ == '__main__':
    handle_nonzero_success(H_MAP)
    if H_MAP == INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(H_MAP)
        kernel32.UnmapViewOfFile(MEMORY_BUFFER)
        raise Exception("Ошибка создания Filemapping")
    dataq = Queue()
    #File_mapping = Process(target=file_mapping, args=(dataq,))
    Analysis = Process(target=analysis, args=(dataq,))
    #File_mapping.start()
    Analysis.start()
    file_mapping(dataq, Analysis)
        
    