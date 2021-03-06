# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import (c_void_p,c_size_t,c_wchar_p,c_char_p,c_wchar,c_char,c_int64,
                    c_int,c_float,c_double,c_longdouble,c_ulong,sizeof,
                    POINTER,WinDLL,Structure)
from ctypes.wintypes import (BOOL,LPCVOID,LPVOID)
from datetime import (datetime,timedelta)
from multiprocessing import (Process,Queue,Pool,Event,Lock)
from scipy.signal import (gaussian,convolve)
from pycwt.wavelet import (cwt,Morlet)
from matplotlib import pyplot as plt
from functools import partial
import ctypes as C
import multiprocessing as mp
import numpy as np
import changePriority as cpr
import socketPayload as sp
import queue,socket,time,sys

kernel32 = WinDLL('kernel32', use_last_error=True)
###
FILE_MAP_COPY        = 0x0001
FILE_MAP_WRITE       = 0x0002
FILE_MAP_READ        = 0x0004
FILE_MAP_ALL_ACCESS  = 0x001f
FILE_MAP_EXECUTE     = 0x0020
PAGE_READWRITE       = 0x04
###
SIZE_T               = c_size_t
VOID_P               = c_void_p
WCHAR_P              = c_wchar_p
CHAR_P               = c_char_p
WCHAR                = c_wchar
CHAR                 = c_char
INT64                = c_int64
INT                  = c_int
FLOAT                = c_float
DOUBLE               = c_double
LONGDOUBLE           = c_longdouble
DWORD                = c_ulong
MAXDWORD             = DWORD(0xffffffff) #From Delphi
LPCWSTR              = WCHAR_P
INVALID_HANDLE_VALUE = VOID_P(-1)
DELPHI_EPOCH         = datetime(1899, 12, 30) #Поправка на формат времени в Delphi
###
NameExpectedLength   = 512 # Ожидаемый размер имени
Int64Size            = sizeof(INT64)
DateTimeSize         = sizeof(DOUBLE)
IntegerSize          = sizeof(INT)
SingleSize           = sizeof(FLOAT)
AnsiCharSize         = sizeof(CHAR) #Имя записано посимвольно
ExpectedChannels     = 22 # Ожидаемое количество каналов
MaxData              = 10000 # Максимальный размер буфера данных в общей памяти
SA                   = None
EXPECTED_SIZE        = (Int64Size*5 + IntegerSize*ExpectedChannels*2 +
                        NameExpectedLength*AnsiCharSize +
                        (DateTimeSize + Int64Size + SingleSize*ExpectedChannels)*MaxData)
"""
Data model code in Delphi:
nkdVersion  : int64; // Версия программы
nkdReady    : int64; // Просто некое число (Автор)
nkdCut      : int64; // Текущее сечение – счетчик записанных значений
nkdFrequency: int64; // Частота оцифровки
nkdChannels : int64; // Текущее количество каналов
nkdLeadsAct : array[1..22] of integer; 
nkdLeadsPas : array[1..22] of integer;
nkdName     : array[1..512] of AnsiChar;
nkdDATA_MV  : array[0..nkMaxData] of
  record
    nkdAstrTime: tDateTime;// Момент регистрации сигнала
    nkdCutCnt  : int64;// Сечение (значения счетчика) для текущего значения данных
    nkdData    : array[1..22] of single;// Данные по каналам в мкВ
  end;

"""
TAGNAME = LPCWSTR('NeuroKMData') #Ожидаемое наименование файла в общей памяти
###---------------------------------------------------------------------------
EST_WAVELET = Morlet(6.) # Morlet wavelet with ω0=6
DJ = 1/12 # Twelve sub-octaves per octaves
DB = 4 # Cwt Frequency = Frequency diveded by DB
SMOOTH = 300
SMOOTH_CUTRANGE = int(SMOOTH/2)
###---------------------------------------------------------------------------
POSITION = 0
GETBLOCK = True
GETTIMEOUT = 0.05
PUTBLOCK = False
PUTTIMEOUT = None

class TChannel:
    def __init__(self,*args,**kwargs):
        self.leads = ['Nul','O2','O1','P4','P3','C4','C3','F4','F3','FP2','FP1',
                      'T6','T5','T4','T3','F8','F7','Pz','Cz','Fz','A1','A2',
                      'AA','Crd','Any','Me','Oz','Fpz','Av1','Av2','Sd','m1',
                      'm2','MM','PG1','PG2','Earth','Undef','EOG','EMG','Respir',
                      'Pres','Micro','HF','SaO2','CPAP','GSR','PPG','PosCh',
                      'Ref','UnKnownEEG','UnKnown','InfoEP','af7','af3','afz',
                      'af4','af8','f5','f1','f2','f6','FT7','FC5','FC3','FC1',
                      'FCZ','FC2','FC4','FC6','FT8','C5','C1','C2','C6','TP7',
                      'CP5','CP3','CP1','CPZ','CP2','CP4','CP6','TP8','P5','P1',
                      'P2','P6','PO7','PO3','POZ','PO4','PO8']

class FIRST_MESSAGE_PAYLOAD(Structure):
    _fields_ = (("Frequency", INT64),
                ("Cwt_Frequency", INT64),
                ("Channels", INT64),
                ("Timestamp", DOUBLE))

def first_message(st, fr, cwtfr, ch):
    st.Frequency = INT64(fr)
    st.Cwt_Frequency = INT64(cwtfr)
    st.Channels = INT64(ch)
    st.Timestamp = DOUBLE(datetime.now().timestamp())
    return st

class MESSAGE_PRELOAD(Structure):
    _fields_ = (("Cut", INT64),
                ("Size", INT64))

def premessage(st, cut, size):
    st.Cut = cut
    st.Size = INT64(size)
    return st

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

class SECURITY_ATTRIBUTES(Structure):
    
    _fields_ = (('nLength', DWORD),
        ('lpSecurityDescriptor', VOID_P),
        ('bInheritHandle', BOOL))

    def __init__(self, *args, **kwargs):
        super(SECURITY_ATTRIBUTES, self).__init__(*args, **kwargs)
        self.nLength = sizeof(SECURITY_ATTRIBUTES)

    @property
    def descriptor(self):
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value):
        self._descriptor = value
        self.lpSecurityDescriptor = C.addressof(value)
LPSECURITY_ATTRIBUTES = POINTER(SECURITY_ATTRIBUTES)

def errcheck_bool(result, func, args):
    if not result:
        raise C.WinError(C.get_last_error())
    return args

def handle_nonzero_success(result):
    if result == 0:
        raise WindowsError()

kernel32.CreateFileMappingW.errcheck = errcheck_bool
kernel32.CreateFileMappingW.restype = VOID_P
kernel32.CreateFileMappingW.argtypes = (
    VOID_P, # _In_ hFileMappingObject
    LPSECURITY_ATTRIBUTES, # _In_ lpFileMappingAttributes
    DWORD, # _In_ dwDesiredAccess
    DWORD, # _In_ dwFileOffsetHigh
    DWORD, # _In_ dwFileOffsetLow
    LPCWSTR) # _In_ lpName

kernel32.OpenFileMappingW.errcheck = errcheck_bool
kernel32.OpenFileMappingW.restype = VOID_P
kernel32.OpenFileMappingW.argtypes = (
    DWORD,   # _In_ dwDesiredAccess
    BOOL,    # _In_ bInheritHandle
    LPCWSTR) # _In_ lpName

kernel32.MapViewOfFile.errcheck = errcheck_bool
kernel32.MapViewOfFile.restype = LPVOID
kernel32.MapViewOfFile.argtypes = (
    VOID_P, # _In_ hFileMappingObject
    DWORD,  # _In_ dwDesiredAccess
    DWORD,  # _In_ dwFileOffsetHigh
    DWORD,  # _In_ dwFileOffsetLow
    SIZE_T) # _In_ dwNumberOfBytesToMap

kernel32.CloseHandle.errcheck = errcheck_bool
kernel32.CloseHandle.argtypes = (VOID_P,)

kernel32.UnmapViewOfFile.errcheck = errcheck_bool
kernel32.UnmapViewOfFile.argtypes = (LPVOID,)

kernel32.RtlMoveMemory.errcheck  = errcheck_bool
kernel32.RtlMoveMemory.argtypes = (
    VOID_P,
    VOID_P,
    SIZE_T,)

def ar_elements(array):
    return array.ndim and array.size

#-Непрерывное вейвлет-преобразование, обрезка и сглаживание, отправка данных--

def socket_client(DataS, ShutDown, Connection, LockQ):
    
    cpr.SetPriority(1)
    PreMessage = MESSAGE_PRELOAD()
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
            #for nc in InputMessage.nChannel:
            #    Message.nChannel[i] = nc
            #    i+=1
            i=0
            ch=0
            try:
                Connection.sendall(premessage(PreMessage, Message.Cut, sizeof(Message)))
                Message.Timestamp = DOUBLE(datetime.utcnow().timestamp())
                Connection.sendall(Message)# Отправка преобразованных данных через протокол Sockets
            except socket.error as e:
                print(e)
                ShutDown.set()
    finally:
        Connection.close()

def mv2cwt(an_dt, an_s0, an_j, an_datalen, an_fltr, data):
    
    if ar_elements(data) == 0:
        return
            
    """
    datalen = len(data)
    data_ft = np.fft.fft(data, n=int(datalen))
    N = len(data_ft)
    ftfreqs = 2 * np.pi * np.fft.fftfreq(N, an_dt)
    sj_col = (an_s0 * 2 ** (np.arange(0, an_j + 1)*DJ))[:, np.newaxis]
    psi_ft_bar = (sj_col * ftfreqs[1] * N) ** .5 *
                  np.conjugate(EST_WAVELET.psi_ft(sj_col * ftfreqs))
    wave = np.fft.ifft(data_ft * psi_ft_bar, axis=1, n=N)
    sel = np.invert(np.isnan(wave).all(axis=1))
    if np.any(sel):
        sj = sj[sel]
        freqs = freqs[sel]
        wave = wave[sel, :]
    """
    wave, scales, freqs, coi, fft, fftfreqs = cwt(data,
                                                  an_dt,
                                                  DJ,
                                                  an_s0,
                                                  an_j,
                                                  EST_WAVELET) # Выше указан алгоритм произведения анализа
            
    Power = np.abs(wave) # Мощность по модулю в квадрате
    tmean = np.transpose(np.mean(Power[an_fltr[0]:an_fltr[1]], axis = 0)) # Обрезка по диапазону частот, вычисление среднего и транспонирование получившейся 2D-матрицы, производится для совмещения "сырого" и обработанного сигнала по длительности.
    gauss_filter = gaussian(len(tmean), std=10)
    gauss_filter = gauss_filter/np.sum(gauss_filter) # Создание сглаживающей гаусианны с длиной, равной размеру окна, для дальнейшей свертки.
    buff = convolve(tmean, gauss_filter, 'same') # Свертка с фильтром
    return (buff.astype(dtype=DOUBLE, order='C',
                        copy=False))[SMOOTH_CUTRANGE:an_datalen-SMOOTH_CUTRANGE]

def analysis(DataQ, DataS, ShutDown, LockQ, Fltr):
    
    def getCwt(pool, data, dt, datalen):

        s0 = 2 * dt / EST_WAVELET.flambda()
        j = np.int(np.round(np.log2((datalen) * dt / s0) / DJ))
        func = partial(mv2cwt, dt, s0, j, datalen, Fltr)
        return pool.map(func, data)
    
    Message = DATACWT_PAYLOAD()
    while not ShutDown.is_set():
        # Чтение данных из очереди
        try:
            Channels = DataQ.get(GETBLOCK, GETTIMEOUT)
            break
        except queue.Empty:
            continue
        except EOFError:
            ShutDown.set()
            break
        #
    pool = Pool(processes=Channels)
    DataPayload = None
    cpr.SetPriority(1)
    WA = list()
    CwtD = [np.array([], dtype=DOUBLE, order='C')]*ExpectedChannels
    CwtCut = 1
    FirstTime = True
    try:
        FlushCwt = True
        while not ShutDown.is_set():
            # Чтение данных из очереди
            try:
                DataPayload = DataQ.get(GETBLOCK, GETTIMEOUT)
            except queue.Empty:
                continue
            except EOFError:
                ShutDown.set()
                break
            #
            
            # Отправка данных на анализ и преобразование
            #start = datetime.now()
            CwtDT = np.diff(DataPayload.nTimestamp).mean() # Вычисление интервала между точками
            CwtD = getCwt(pool, DataPayload.nChannel, CwtDT,
                          DataPayload.Data_Length.value+SMOOTH)
            #print('Time spent '+str(datetime.now()-start))
            #
            
            #
            if FirstTime:
                FirstTime = False
                DataS.put(DataPayload.Data_Length, PUTBLOCK, PUTTIMEOUT)
            #
            
            # Отправка данных в очередь на формирование пакета Sockets
            Message.Cut = INT64(CwtCut)
            Message.Datalen = DataPayload.Data_Length
            Message.Time_Interval = FLOAT(CwtDT)
            Message.nChannel = CwtD
            DataS.put(Message, PUTBLOCK, PUTTIMEOUT)
            #
            
            #
            if FlushCwt:
                WA = CwtD
                FlushCwt = False
            else:
                WA = np.concatenate((WA,CwtD), axis=1)
            CwtCut += 1
            #
            
    finally:
        if DataPayload != None:
            DataPayload.nWA = WA
            DataQ.put(DataPayload, PUTBLOCK, PUTTIMEOUT)
        pool.close()
        pool.join()

#-----------------------------------------------------------------------------
        
#-Чтение из общей памяти, отправка данных в очередь---------------------------

def file_mapping(sock, DataQ, DataS, ShutDown, LockQ):
    
    def _2sec(dvalue):
        return dvalue.timestamp()
    
    def datetime_fromdelphi(dvalue):
        return DELPHI_EPOCH + timedelta(days=dvalue)

    def readMem(mbuf, pos, bts, svpos, posret=True, bytesout=False, datetimedouble=False):
        size = sizeof(bts)
        bts_s = C.create_string_buffer(size)
        source = mbuf + pos
        length = SIZE_T(size)
        kernel32.RtlMoveMemory(bts_s, source, length)
        if svpos and posret:
            retpos = pos + size
        elif not svpos and posret:
            retpos = pos
        if bytesout:
            if posret:
                return np.array(bts_s, order='C').view(dtype=bts), retpos
            else:
                return np.array(bts_s, order='C').view(dtype=bts)
        elif datetimedouble:
            if posret:
                return (datetime_fromdelphi(C.cast(bts_s,POINTER(bts)).contents.value).timestamp(),
                        retpos)
            else:
                return datetime_fromdelphi(C.cast(bts_s,POINTER(bts)).contents.value).timestamp()
        else:
            if posret:
                return C.cast(bts_s, POINTER(bts)).contents.value, retpos
            else:
                return C.cast(bts_s, POINTER(bts)).contents.value
    
    def _getMVData(mbuf, pos, data, create):
        tpos = pos
        def _dmvmapret(data):
            nonlocal mbuf
            nonlocal create
            nonlocal tpos
            buf = readMem(mbuf, tpos, FLOAT, False, posret=False, bytesout=True)
            tpos += SingleSize
            if create:
                return np.ndarray((1,), buffer=buf, dtype=FLOAT, order='C')
            else:
                return np.concatenate((data, np.ndarray((1,), buffer=buf,
                                                        dtype=FLOAT,
                                                        order='C')),
                                      axis = 0)
        return list(map(_dmvmapret, data)), tpos
    
    def _OPret(data, datalen):
        def mapret(data):
            return data[-(datalen):,]
        return list(map(mapret, data)) # Выделение из общего массива считанных данных окна, равного CwtFreq
    
    while True:
        try:
            #hmap = kernel32.CreateFileMappingW(INVALID_HANDLE_VALUE, SA, PAGE_READWRITE, 0, EXPECTED_SIZE, TAGNAME)
            hmap = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, TAGNAME)
            handle_nonzero_success(hmap)
            if hmap == INVALID_HANDLE_VALUE:
                kernel32.CloseHandle(hmap)
                raise Exception("Ошибка создания Filemapping")
            mbuf = kernel32.MapViewOfFile(hmap, FILE_MAP_ALL_ACCESS, 0, 0, EXPECTED_SIZE)
            break
        except WindowsError:
            print(C.WinError(C.get_last_error()))
            print('Перезапустите программу или запустите запись brainwin.exe...')
            time.sleep(5)
            continue
    tc = TChannel()
    while True:
            Freq, pos = readMem(mbuf, Int64Size*3, INT64, True) # Частота оцифровки
            if Freq:
                break
    CwtFreq = int(Freq/DB)# Частота преобразования и отправки данных и длина окна
    print('\nЧастота оцифровки: ', Freq, 'Гц')
    Channels, pos = readMem(mbuf, pos, INT64, True) # Фактическое количество используемых каналов
    print('Количество каналов: ', Channels)
    sock.sendall(first_message(FIRST_MESSAGE_PAYLOAD(), Freq, CwtFreq, Channels)) # Сообщение серверу с первоначальными данными
    DataQ.put(Channels, PUTBLOCK, PUTTIMEOUT)
    LeadsAct = [0]*Channels
    LeadsPas = [0]*Channels
    Leads = [(0,0)]*Channels
    for i in range(0, Channels):
        LeadsAct[i], pos = readMem(mbuf, pos, INT, True)
        cp = pos
        pos = (cp + IntegerSize*(ExpectedChannels - 1))
        LeadsPas[i], pos = readMem(mbuf, pos, INT, False)
        pos = cp
        Leads[i] = (tc.leads[LeadsAct[i]],tc.leads[LeadsPas[i]])
    print('Отведения: ', Leads)
    prepos1 = ((Int64Size*5 + IntegerSize*ExpectedChannels*2 +
               NameExpectedLength*AnsiCharSize))
    prepos2 = ((DateTimeSize + Int64Size + SingleSize*ExpectedChannels))
    Cut, pos = readMem(mbuf, Int64Size*2, INT64, False)
    DataPayload = DATAMV_PAYLOAD()
    Datalen = 0
    DataMV = [list()]*Channels
    FlushTime = True
    FlushMVData = True
    Flow = False
    cpr.SetPriority(5)
    slpt = 1/Freq/1000
    try:
        while not ShutDown.is_set():
            if not Flow:
                oldCut = Cut
                with LockQ:
                    Cut = readMem(mbuf, Int64Size*2, INT64, False, posret=False)
                acCut = Cut
                CwtCut = Cut + (SMOOTH+50)
                if oldCut == Cut-1:
                    Flow = True
                    print("Анализ...\n")
                else:
                    time.sleep(slpt)
                    continue
            else:
                acCut = readMem(mbuf, Int64Size*2, INT64, False, posret=False)
                if acCut < oldCut:
                    Flow = False
                    Datalen = 0
                    continue
            """
            with LockQ:
                mvCut, pos = readMem(mbuf,
                                     Int64Size+(prepos1+prepos2*(divmod(Cut, MaxData)[1])),
                                     INT64, False)
            """
            if acCut > Cut:
                Cut += 1
            else:
                time.sleep(slpt)
                continue
            
            Datalen += 1
            
            # Чтение момента регистрации сигналов из общей памяти
            with LockQ:
                pos = prepos1+prepos2*(divmod(Cut, MaxData)[1])
                AstrTime, pos = readMem(mbuf, pos, DOUBLE, True, bytesout=True)
            #
            
            # Чтение данных из общей памяти и конкатенация биосигнала в мкВ в массив типа Float
            if FlushMVData:
                FlushMVData = False
            with LockQ:
                DataMV, pos = _getMVData(mbuf, pos+Int64Size, DataMV, FlushMVData)
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
            if Cut-CwtCut >= CwtFreq:
                if Datalen > CwtFreq:
                    Datalen = CwtFreq
                CwtCut = Cut
                DataPayload.Cut = INT64(Cut)
                DataPayload.Data_Length = INT64(Datalen)
                DataPayload.nTimestamp = CwtT[-(Datalen+SMOOTH):,]
                DataPayload.nChannel = _OPret(DataMV, Datalen+SMOOTH)
                DataQ.put(DataPayload, PUTBLOCK, PUTTIMEOUT)
                print('\nРазмер окна: '+str(Datalen)+'\nСечение: '+str(Cut))
                Datalen = 0
            #
    finally:
        print('\n---------------------------------------------------------------\nАнализ окончен.')
        kernel32.CloseHandle(hmap)
        kernel32.UnmapViewOfFile(mbuf)
        while True:
            try:
                DataPayload = DataQ.get(GETBLOCK, GETTIMEOUT)
            except queue.Empty:
                continue
            except EOFError:
                break
            break
        WA = DataPayload.nWA
        print('Сохранение результатов!\n')
        timed = list(map(datetime_fromdelphi,
                         CwtT[(SMOOTH_CUTRANGE+50):(SMOOTH_CUTRANGE+50)+len(WA[0])]))
        times = np.array(list(map(_2sec,timed)))
        times = times-np.min(times)
        for i in range(Channels):
            ar1 = (DataMV[i])[(SMOOTH_CUTRANGE+50):(SMOOTH_CUTRANGE+50)+len(WA[i])]
            ar2 = WA[i]
            plt.plot(times, ar1, linewidth=0.1)
            plt.plot(times, ar2, linewidth=0.4)
            plt.title("Результат анализа по каналу "+str(i+1))
            plt.ylabel("Измеренные значения и мощность, мкВ")
            plt.xlabel("Длительность, сек")
            plt.xticks()
            plt.savefig('Channel_'+str(i+1)+'_cwt.svg')
            plt.clf()
            ar = np.vstack((timed,ar1))
            ar = np.transpose(np.vstack((ar, ar2)))
            np.savetxt('Channel_'+str(i+1)+'_cwt.csv', ar,
                       header='Time,MV,CWT', delimiter=",", encoding='utf-8', fmt='%s')
            print('Сохранено: Канал '+str(i+1)+'!\n')
            

def main():
    
    SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            host = input('Введите адрес сервера (127.0.0.1/192.168.ххх.ххх/localhost): ')
            while True:
                try:
                    port = abs(int(input('Введите номер порта (целое положительное число, >1023 не требует привелегий): ')))
                    break
                except ValueError:
                    print('Должно быть целое число!')
                    continue
            SOCKET.connect((host,port))
            break
        except WindowsError:
            print(C.WinError(C.get_last_error()))
            input('Нажмите Enter, чтобы повторить попытку подключения...')
            continue
    
    flt = [0,0]
    while True:
        while True:
            try:
                flti = input("Нижняя граница фильтра, ГЦ (0 - без нижней границы): ")
                flt[0] = abs(int(flti))
                break
            except ValueError:
                print('Должно быть целое положительное число или 0!')
                continue
        while True:
            try:
                flti = input("Верхняя граница фильтра, ГЦ (0 - без верхней границы): ")
                flt[1] = abs(int(flti))
                break
            except ValueError:
                print('Должно быть целое положительное число или 0!')
                continue
        if flt[0] >= flt[1] and flt[0]+flt[1] != 0:
            print("Для получения полезного сигнала значение верхней границы фильтра должно быть больше значения нижней!")
            continue
        else:
            for i in range(2):
                if flt[i] == 0:
                    flt[i] = None
            break
    DataQ = Queue()
    DataS = Queue()
    LockQ = Lock()
    ShutDown = Event()
    Filemapping = Process(target=file_mapping, args=(SOCKET, DataQ, DataS, ShutDown, LockQ))
    Analysis = Process(target=analysis, args=(DataQ, DataS, ShutDown, LockQ, flt,))
    SocketClient = Process(target=socket_client, args=(DataS, ShutDown, SOCKET, LockQ,))
    Filemapping.daemon = True
    #Analysis.daemon = True
    SocketClient.daemod = True
    Filemapping.start()
    Analysis.start()
    SocketClient.start()
    try:
        input('Для остановки нажмите Enter...')
        raise SystemExit()
    except (KeyboardInterrupt, SystemExit, EOFError):
        ShutDown.set()
        time.sleep(10)
    finally:
        DataQ.close()
        DataQ.join_thread()
        DataS.close()
        DataS.join_thread()
        print('Работа окончена!')
        time.sleep(2)
        Filemapping.join(2)
        Analysis.join(2)
        SocketClient.join(2)
        sys.exit(0)

if __name__ == '__main__':
    main()
