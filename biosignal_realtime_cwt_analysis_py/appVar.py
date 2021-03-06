# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import (c_void_p,c_size_t,c_char,c_int64,c_int,c_float,c_double,
                    sizeof,POINTER,WinDLL,Structure)
from ctypes.wintypes import (BOOL,DWORD,LPCWSTR,LPVOID)
from pycwt.wavelet import Morlet
from datetime import datetime
import ctypes as C

###---------------------------------------------------------------------------
FILE_MAP_COPY        = 0x0001
FILE_MAP_WRITE       = 0x0002
FILE_MAP_READ        = 0x0004
FILE_MAP_ALL_ACCESS  = 0x001f
FILE_MAP_EXECUTE     = 0x0020
PAGE_READWRITE       = 0x04
###---------------------------------------------------------------------------
SIZE_T               = c_size_t
VOID_P               = c_void_p
CHAR                 = c_char
INT64                = c_int64
INT                  = c_int
FLOAT                = c_float
DOUBLE               = c_double
###---------------------------------------------------------------------------
MAXDWORD             = DWORD(0xffffffff) #From Delphi
INVALID_HANDLE_VALUE = VOID_P(-1)
DELPHI_EPOCH         = datetime(1899, 12, 30) #Поправка на формат времени в Delphi
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
TAGNAME              = LPCWSTR('NeuroKMData') #Ожидаемое наименование файла в общей памяти
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
###---------------------------------------------------------------------------
EST_WAVELET          = Morlet(6.) # Morlet wavelet with ω0=6
DJ                   = 1/12 # Twelve sub-octaves per octaves
DB                   = 4 # Cwt Frequency = Frequency diveded by DB
SMOOTH               = 300
SMOOTH_CUTRANGE      = int(SMOOTH/2)
###---------------------------------------------------------------------------
GETBLOCK             = True
GETTIMEOUT           = 0.05
PUTBLOCK             = False
PUTTIMEOUT           = None
###---------------------------------------------------------------------------
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

def handle_valid_nonzero_success(result):
    if result == 0:
        raise WindowsError()
    if result == INVALID_HANDLE_VALUE:
        raise Exception("Ошибка создания Filemapping")

def errcheck_bool(result, func, args):
    if not result:
        raise C.WinError(C.get_last_error())
    return args

kernel32 = WinDLL('kernel32', use_last_error=True)
kernel32.CreateFileMappingW.errcheck = errcheck_bool
kernel32.CreateFileMappingW.restype = VOID_P
kernel32.CreateFileMappingW.argtypes = (
    VOID_P, # _In_ hFileMappingObject
    LPSECURITY_ATTRIBUTES, # _In_ lpFileMappingAttributes
    DWORD, # _In_ dwDesiredAccess
    DWORD, # _In_ dwFileOffsetHigh
    DWORD, # _In_ dwFileOffsetLow
    LPCWSTR) # _In_ lpName
CreateFileMappingW = kernel32.CreateFileMappingW

kernel32.OpenFileMappingW.errcheck = errcheck_bool
kernel32.OpenFileMappingW.restype = VOID_P
kernel32.OpenFileMappingW.argtypes = (
    DWORD,   # _In_ dwDesiredAccess
    BOOL,    # _In_ bInheritHandle
    LPCWSTR) # _In_ lpName
OpenFileMappingW = kernel32.OpenFileMappingW

kernel32.MapViewOfFile.errcheck = errcheck_bool
kernel32.MapViewOfFile.restype = LPVOID
kernel32.MapViewOfFile.argtypes = (
    VOID_P, # _In_ hFileMappingObject
    DWORD,  # _In_ dwDesiredAccess
    DWORD,  # _In_ dwFileOffsetHigh
    DWORD,  # _In_ dwFileOffsetLow
    SIZE_T) # _In_ dwNumberOfBytesToMap
MapViewOfFile = kernel32.MapViewOfFile

kernel32.CloseHandle.errcheck = errcheck_bool
kernel32.CloseHandle.argtypes = (VOID_P,)
CloseHandle = kernel32.CloseHandle

kernel32.UnmapViewOfFile.errcheck = errcheck_bool
kernel32.UnmapViewOfFile.argtypes = (LPVOID,)
UnmapViewOfFile = kernel32.UnmapViewOfFile

kernel32.RtlMoveMemory.errcheck  = errcheck_bool
kernel32.RtlMoveMemory.argtypes = (
    VOID_P,
    VOID_P,
    SIZE_T,)
RtlMoveMemory = kernel32.RtlMoveMemory