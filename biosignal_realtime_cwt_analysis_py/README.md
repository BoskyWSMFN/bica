Разработка ПО
========================
При всем многообразии сфер применения выбранного инструмента для разработки ПО – языка программирования Python – существует три наиболее популярные: 1) веб-разработка, 2) data science: машинное обучение, анализ данных и визуализация, 3) автоматизация процессов [[Библиотека программиста](https://proglib.io/p/python-applications "Сферы применения Python: возможности языка")], попытка отойти от которых или совместить их, как показала практика, вызывает  проблемы с производительностью. Например, при разработке ПО, которую можно в общем виде принять за совмещение второго и третьего пунктов, возникли проблемы со скоростью работы ПО, что связано с относительно низкой скоростью выполнения кода и GIL [33] (Глобальная Блокировка Интерпретатора), которая фактически блокирует параллельное выполнение потоков. Возникшие проблемы приводили к недостоверности результатов анализа полученного сигнала и общей нестабильности работы ПО, а в отдельных случаях – системы.

Возникшие проблемы удалось решить использованием нативных библиотек Windows и высокоэффективных библиотек NumPy для получения данных из отображенного файла и произведения расчетов с полученными данными и задокументированным способом обхода GIL [[Python 3.8.3](https://docs.python.org/3/library/multiprocessing.html "multiprocessing – Process-based parallelism")].

File Mapping в ПО
------------------------
Для Python существует библиотека mmap, которая реализует функционал протокола File Mapping [[Python 3.8.3](https://docs.python.org/3/library/mmap.html "mmap – Memory-mapped file support")], однако оная для работы в ОС MS Windows использует библиотеку Windows API kernel32, работа через которую – наиболее близкий для MS Windows способ работы с ней.

Этот программный интерфейс спроектирован для работы в языках программирования C/C++ [[Microsoft Docs](https://docs.microsoft.com/en-us/previous-versions//cc433218(v=vs.85) "Windows API")], функции первого из которых Python может без проблем вызывать, предварительно загрузив соответствующую библиотеку и описав способ работы с вызываемыми функциями.

Основываясь на вышеизложенном и учитывая то, что для успешного взаимодействия с программным интерфейсом АПК необходимо всего несколько функций, можно загрузить библиотеку WinAPI kernel32 и описать способы вызова необходимых функций. Для загрузки библиотеки WinAPI kernel32 использован функционал модуля Python для работы библиотеками MS Windows и языка C – ctypes.

```python
from ctypes import (c_size_t,WinDLL)
from ctypes.wintypes import (BOOL,LPVOID,DWORD,LPCWSTR,HANDLE)
import ctypes as C

kernel32 = WinDLL('kernel32', use_last_error=True)

SIZE_T = c_size_t

def errcheck_bool(result, func, args):
    if not result:
        raise C.WinError(C.get_last_error())
    return args

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

kernel32.RtlMoveMemory.errcheck = errcheck_bool
kernel32.RtlMoveMemory.argtypes = (
    HANDLE,
    HANDLE,
    SIZE_T)
```

Из загруженной библиотеки kernel32 для обеспечения доступа к содержимому отображенного файла используются функции OpenFileMappingW, MapViewOfFile и RtlMoveMemory, которые возвращают указатель на созданный ранее объект File Mapping, адрес в памяти программы, с которым объект был ассоциирован, и обеспечивают доступ к содержимому объекту соответственно.

Поскольку в Python необходимо описывать, что C-функции возвращают (restype) и принимают в качестве аргументов (argtypes) [[Хабр](https://habr.com/ru/post/466499/ "C/C++ из Python (ctypes)")], что является одним из минусов работы с C-функциями в Python, в данном случае требуется загрузить подмодуль wintypes, в котором содержатся часто используемые типы данных MS Windows. Для выявления ошибок при вызове C-функций (errcheck) объявлена типовая функция, которая вызывает исключение, если после вызова C-функции не был получен результат работы оной.

Ниже описан общий вид вызова функций из ранее загруженной библиотеки kernel32, расчета размера отображенного файла и поиск в содержимом файла значения nkdCut.
Стоит отметить, что данные в отображенном файле содержаться в виде строк байтов со своими позицией и длиной вида “(b'x00\x00\x00\x00\x00\x00\x00\x00')”, которые необходимо интерпретировать в значения определенного типа, для чего используется функция cast, преобразующая считанную из отображенного файла строку байт в значение.

```python
from ctypes import (c_int64,c_double,c_int,c_float,
                    c_char,sizeof,POINTER)

FILE_MAP_ALL_ACCESS  = 0x001f
INVALID_HANDLE_VALUE = HANDLE(-1)
TAGNAME              = LPCWSTR('NeuroKMData') # Ожидаемое
                       # наименование файла в общей памяти

NameExpectedLength   = 512 # Ожидаемый размер имени
Int64Size            = sizeof(c_int64)
DateTimeSize         = sizeof(c_double)
IntegerSize          = sizeof(c_int)
SingleSize           = sizeof(c_float)
AnsiCharSize         = sizeof(c_char) #Имя записано посимвольно
ExpectedChannels     = 22 # Ожидаемое количество каналов
MaxData              = 10000 # Максимальный размер буфера
                             # данных в общей памяти
EXPECTED_SIZE        = (Int64Size*5 + IntegerSize*
                        ExpectedChannels*2 +
                        NameExpectedLength*
                        AnsiCharSize +(DateTimeSize + 
                        Int64Size + SingleSize*
                        ExpectedChannels)*MaxData)

def handle_valid_nonzero_success(result):
    if result == 0:
        raise WindowsError()
    elif result == INVALID_HANDLE_VALUE:
        raise Exception("Ошибка создания Filemapping")

hmap = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS,
                                 False, TAGNAME)
handle_valid_nonzero_success(hmap)
mbuf = kernel32.MapViewOfFile(hmap, FILE_MAP_ALL_ACCESS,
                              0, 0, EXPECTED_SIZE)

def readMem(mbuf, pos, bts):
    size = sizeof(bts)
    bts_s = C.create_string_buffer(size)
    source = mbuf + pos
    length = SIZE_T(size)
    kernel32.RtlMoveMemory(bts_s, source, length)
    return C.cast(bts_s, POINTER(bts)).contents.value,
           (pos+size)

pos = Int64Size*2 # установка позиции для чтения
nkdCut, pos = readMem(mbuf, pos, c_int64) # возвращает текущее
              # значение счетчика nkdCut из отображенного файла
              # и позицию после считанного значения
```

Анализ и преобразование полученного сигнала в ПО
------------------------
Для анализа и преобразования данных, полученных из отображенного файла, используются непрерывное вейвлет преобразование из модуля PyCWT и свертка с гауссовым окном в качестве сглаживающего фильтра из модуля SciPy, а также – высокоуровневые математические функции для работы с многомерными массивами модуля NumPy.
При достижении длины массива принятых данных (биопотенциал в мкВ и момент его регистрации) определенного значения («окна»), этот массив отправляется на обработку.
Из листинга 3.5: для преобразования был использован вейвлет Морле (ω0=6) с масштабным фильтром по квазичастотам 24-43 Гц, полученным по результатам качественного анализа корреляций в статье «Empirical and modeling study of emotional state dynamics in social videogame paradigms», журнал «Cognitive Systems Research».
Сглаживание осуществляется в два этапа: 1) свертка с окном Гаусса со значение параметра σ равным 10 [Tikhomirova D. Empirical and modeling study of emotional state dynamics in social videogame paradigms // Cognitive Systems Research. - 2020. - №60.] и длиной, равной длине массива отправленных на обработку данных, вид которого представлен на рисунке 3.1, 2)обрезание участков в начале и конце обработанного сигнала, размером равных полуширине используемого вейвлета или превышающем ее, что связано с наличием краевых эффектов [[Кузнецов С.Ю. Использование вейвлет преобразования для анализа поверхностной ЭМГ // Физиология мышечной деятельности. – 2010. – №2.](http://phmag.imbp.ru/articles/Kuznetcov.pdf)].

![Окно Гаусса с параметром σ равным 10 и длиной, равной длине массива отправленных на обработку данных](https://i.ibb.co/LN5BRwH/Figure-4.png)

```python
import numpy as np
from pycwt.wavelet import (cwt,Morlet)
from scipy.signal import (gaussian,convolve)
from ctypes import c_double

EST_WAVELET = Morlet(6.)
DJ = 1/12
SMOOTH = 300
SMOOTH_CUTRANGE = int(SMOOTH/2)

def mv2cwt(an_dt, an_datalen, an_fltr, data):
    
    an_s0 = 2*an_dt/EST_WAVELET.flambda()
    an_j = np.int(np.round(np.log2((an_datalen)*an_dt/an_s0)/DJ))
            
    wave, scales, freqs, coi, fft, fftfreqs = cwt(data,
                                                  an_dt,
                                                  DJ,
                                                  an_s0,
                                                  an_j,
                                                  EST_WAVELET)
            
    Power = np.abs(wave)**2
    tmean = np.transpose(p.mean(Power[an_fltr[0]:an_fltr[1]],
                                axis = 0))
    gauss_filter = gaussian(len(tmean), std=10)
    gauss_filter = gauss_filter/np.sum(gauss_filter)
    buff = convolve(tmean, gauss_filter, 'same')
    return (buff.astype(dtype=c_double, order='C',
                        copy=False))[SMOOTH_CUTRANGE:
                                     an_datalen-SMOOTH_CUTRANGE]

datalen = 1000
fltr = (24,43)
data = np.random.random(datalen+SMOOTH)*10
tstamp = np.sort(np.random.random(datalen+SMOOTH))
dt = np.diff(tstamp).mean()
data_cwt = mv2cwt(dt, datalen+SMOOTH, fltr, data)
```

В качестве временных меток (tstamp) используется сортированный по возрастанию набор случайных чисел. Интервал между точками массива данных, которые требуется преобразовать, представляет из себя среднее арифметическое всех разниц между соседними точками tstamp.

Результат выполнения кода представлен на нижеследующих рисунках. Для наглядности в исходные данные были добавлены области с нулевыми значениями, получившаяся последовательность линейно возрастает.

![Спектр мощности обработанного сигнала. По оси абсцисс представлена длительность сигнала, по оси ординат – диапазон частот](https://i.ibb.co/bRFB6mc/Figure-2.png)

![Спектр мощности обработанного сигнала после применения масштабного фильтра по диапазону квазичастот 24-43 Гц](https://i.ibb.co/S5s1CL0/Figure-3.png)

![Исходные данные (синяя линия) и обработанный сигнал после двух этапов сглаживания усредненных значений по диапазону квазичастот 24-43 Гц (оранжевая плавная линия). По оси ординат представлены условные значения](https://i.ibb.co/cwRcbyB/Figure-1.png)

```python
import numpy as np

f0 = 6.

def Morlet_psi_ft(f):
    return (np.pi**-0.25)*np.exp(-0.5*(f-f0)**2)

def Morlet_flambda():
    return (4*np.pi)/(f0+np.sqrt(2+f0**2))

data # Массив исходных данных
dt   # Интервал между точками в массиве исходных данных
dj   # Интервал между дискретными масштабами, уменьшение
     # приведет к большему масштабному разрешению и увеличению
     # времени выполнения расчета.

datalen    = len(data) # n
data_ft    = np.fft.fft(data, n=datalen)
N          = len(data_ft)
s0         = 2*dt/Morlet_flambda()
J          = np.round(np.log2(datalen*dt/s0)/dj)
ftfreqs    = 2*np.pi*np.fft.fftfreq(N, dt)
sj_col     = (s0*2**(np.arange(0, J+1)*dj))[:, np.newaxis]
psi_ft_bar = (sj_col*ftfreqs[1]*N)**.5*
              np.conjugate(Morlet_psi_ft(sj_col*ftfreqs))
wave       = np.fft.ifft(data_ft*psi_ft_bar, axis=1, n=N)
```

Преобразование сигнала в ПО происходит по следующему алгоритму:

непрерывное вейвлет преобразование по базовому вейвлету Морле в модуле PyCWT представляет из себя последовательность быстрого преобразования Фурье для исходного сигнала, расчета двухмерной матрицы, содержащей масштабы и угловые частоты Фурье [s, f], и обратного преобразования Фурье для произведения результатов БПФ и двухмерной матрицы масштабов и угловых частот.
БПФ рассчитывается по следующей формуле [[NumPy](https://numpy.org/doc/stable/reference/routines.fft.html "Discrete Fourier Transform (numpy.fft) ")]:

![1](https://i.ibb.co/sRnbGrC/f1.png)

Для расчета матрицы масштабов и угловых частот необходимо рассчитать дискретный масштаб s0, количество масштабирований J, последовательность масштабов, представляющую из себя функцию:

![2](https://i.ibb.co/5BvJDSh/f2.png)

Дискретный масштаб s0 для вейвлета Морле вычисляется по формуле:

![3](https://i.ibb.co/Z8hD1dm/f3.png)

Количество масштабирований J в общем случае вычисляется по формуле:

![4](https://i.ibb.co/GvPwc7k/f4.png)

Для расчета матрицы масштабов и угловых частот также необходимо рассчитать угловые частоты Фурье, которые в общем случае вычисляются по формуле:

![5](https://i.ibb.co/9Wx0xCd/f5.png)

Сама же матрица для вейвлета Морле вычисляется по формуле:

![6](https://i.ibb.co/stTkMpN/f6.png)

Обратное преобразование Фурье для данного случая осуществляется по формуле:

![7](https://i.ibb.co/3vQzskL/f7.png)

В результате получается матрица W(J+1, m) вейвлет коэффициентов, возведение в степень по модулю которых приведено на рисунке выше.

Возведенная ранее в степень по модулю матрица обрезается по диапазону W(24-43, m), что отражено в следующей формуле:

![8](https://i.ibb.co/PrkCpRS/f8.png)

Для каждого столбца m матрицы P рассчитывается усредненное значение:

![9](https://i.ibb.co/d64xKYy/f9.png)

Полученная числовая последовательность свертывается с полученным ранее окном Гаусса по формуле [[NumPy](https://numpy.org/doc/stable/reference/generated/numpy.convolve.html "numpy.convolve")]:

![10](https://i.ibb.co/0tHnR9f/f10.png)

После свертки числовая последовательность обрезается в начале и в конце по значению переменной SMOOTH_CUTRANGE, что приводит к дополнительной задержке в 0,15 секунд при частоте оцифровки в 1000 Гц, однако эта мера необходима, чтобы исключить из обработанных данных искажения, вызванные краевыми эффектами при вейвлет преобразовании.

Передача обработанного сигнала через API Sockets
------------------------
В Python доступен для загрузки модуль sockets, который отвечает всем заявленным к ПО требованиям и является весьма простым в использовании, однако требует конвертации передаваемых данных в строку байт вида “(b'x00\x00\x00\x00\x00\x00\x00\x00')”.

Из документации [[Python 3.8.3](https://docs.python.org/3/library/socket.html "socket – Low-level networking interface")] становится понятно, что с помощью протокола Sockets возможно передавать класс Structure из модуля ctypes, который совпадает с типом struct в языке С, без очевидной конвертации в строку байт, что определяет выбор структуры данных для передачи.

Ниже представлен общий вид алгоритма передачи данных в ПО, а также структура и размер передаваемых данных. Следует принять во внимание, что для частоты оцифровки в 1000 Гц ширина окна передаваемых данных будет равна 1000/4=250 значений типа Double для одного канала из 22-х возможных.

Структура передаваемых данных представляет из себя три объекта типа Structure:

-	FIRST_MESSAGE_PAYLOAD состоит из трех переменных типа Int64 и одной – типа Double общим размером в 32 байта. Передается единожды в начале работы ПО, можно назвать инициализирующим.
-	PREMESSAGE_PAYLOAD состоит из двух переменных типа Int64 общим размером в 16 байт. Служит для передачи Socket-серверу размера основного пакета передаваемых данных, перед котором и передается.
-	MESSAGE_PAYLOAD состоит из двух переменных типа Int64, одной – типа Double, одной – типа Float и 22-х массивов типа Double длиной в 250 значений; размер вычисляется динамически. Служит для передачи Socket-серверу обработанных данных, по мере накопления которых отправляется.

```python
import socket
import ctypes as C
import numpy as np
from datetime import datetime

class FIRST_MESSAGE_PAYLOAD(C.Structure):
    _fields_ = (("Frequency", C.c_int64),
                ("Cwt_Frequency", C.c_int64),
                ("Channels", C.c_int64),
                ("Timestamp", C.c_double))

class PREMESSAGE_PAYLOAD(C.Structure):
    _fields_ = (("Cut", C.c_int64),
                ("Size", C.c_int64))

class MESSAGE_PAYLOAD_1KHz(C.Structure):
    _fields_ = (("Cut", C.c_int64),
                ("Data_Length", C.c_int64),
                ("Timestamp", C.c_double),
                ("Time_Interval", C.c_float),
                ("Channel_1", C.c_double*250),
                ("Channel_2", C.c_double*250),
                ("Channel_3", C.c_double*250),
                ("Channel_4", C.c_double*250),
                ("Channel_5", C.c_double*250),
                ("Channel_6", C.c_double*250),
                ("Channel_7", C.c_double*250),
                ("Channel_8", C.c_double*250),
                ("Channel_9", C.c_double*250),
                ("Channel_10", C.c_double*250),
                ("Channel_11", C.c_double*250),
                ("Channel_12", C.c_double*250),
                ("Channel_13", C.c_double*250),
                ("Channel_14", C.c_double*250),
                ("Channel_15", C.c_double*250),
                ("Channel_16", C.c_double*250),
                ("Channel_17", C.c_double*250),
                ("Channel_18", C.c_double*250),
                ("Channel_19", C.c_double*250),
                ("Channel_20", C.c_double*250),
                ("Channel_21", C.c_double*250),
                ("Channel_22", C.c_double*250))

first_message = FIRST_MESSAGE_PAYLOAD()
premessage    = PREMESSAGE_PAYLOAD()
message       = MESSAGE_PAYLOAD_1KHz()
sck           = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sck.connect((‘localhost’,1024))
first_message.Frequency     = 1000        # Частота оцифровки
first_message.Cwt_Frequency = int(1000/4) # Ширина окна
first_message.Channels      = 3           # Фактическое
                                          # количество каналов
first_message.Timestamp     = datetime.utcnow().timestamp()
                                          # Временная метка
sck.sendall(first_message)                # Отправка первого
                                          # сообщения
premessage.Cut              = 1           # Значение счетчика для
                                          # первого сообщения
premessage.Size             = C.sizeof(message)
                                          # Размер полезных
                                          # данных
sck.sendall(premessage)                   # Отправка
                                          # предварительного
                                          # сообщения с размером
                                          # полезных данных
message.Cut                 = premessage.Cut
message.Data_Length         = first_message.Cwt_Frequency
                                          # В общем случае длина
                                          # отправляемых данных
                                          # по каналам будет
                                          # равна ширине окна
message.Timestamp           = datetime.utcnow().timestamp()
                                          # Временная метка
message.Time_Interval       = 1/1000      # Интервал между
                                          # точками, в общем
                                          # случае
                                          # рассчитывается
                                          # динамически
message.Channel_1           = np.ctypeslib.as_ctypes(cwt[0])
…
message.Channel_22          = np.ctypeslib.as_ctypes(cwt[21])
                                          # Преобразование
                                          # массива NumPY в
                                          # массив С типа Double
sck.sendall(message)                      # Отправка обработанных
                                          # данных
sck.close()
```

Обход GIL и параллельные вычисления
------------------------
GIL (Global Interpreter Lock) — это блокировка (mutex) интерпретатора CPython, которая не позволяет нескольким потокам выполнить один и тот же байткод [39]. Эта блокировка является необходимой, поскольку интерпретатор CPython не является потокобезопасным, т. е. без блокировки может возникнуть ситуация, при которой один поток может произвести попытку считывания еще не записанных данных из другого потока. Впрочем, другие реализации Python не приспособлены для создания быстрых численных алгоритмов.
Под параллельными вычислениями в данном случае понимается SMP – симметричная многопроцессорность с общей памятью процессов.

![Схема SMP](https://i.ibb.co/MBCyzN1/2020-06-29-17-29-39.png)

В некоторых случаях при вычислениях с использованием модуля NumPy можно пренебречь реализацией многопроцессорности, потому что, допустим, процедура умножения двух матриц будет выполняться с использованием низкоуровневых высокоэффективных библиотек линейной алгебры на C++ (MKL или ATLAS)[[Хабр](https://habr.com/ru/post/238703/ "И еще раз о GIL в Python")], однако это верно лишь для типовых операций, и в случае преобразования Фурье вычисления будут производиться в пределах одного процесса.

На практике стало известно, что на одном физическом процессоре время вычисления по алгоритму ниже для 1000 точек занимает ~0,05 секунд, исходя из чего было принято очевидное решение увеличить количество процессов с общей памятью, которые выполняют вычисления для каждого канала параллельно на разных физических процессорах. Для этой цели в ПО был загружен модуль multiprocessing.

```python
import numpy as np
from multiprocessing import Pool

f0 = 6.
def Morlet_psi_ft(f):
    return (np.pi**-0.25)*np.exp(-0.5*(f-f0)**2)

def Morlet_flambda():
    return (4*np.pi)/(f0+np.sqrt(2+f0**2))

[data]*22 # Массив исходных данных
dt        # Интервал между точками в массиве исходных данных
dj        # Интервал между дискретными масштабами, уменьшение
          # приведет к большему масштабному разрешению и 
          # увеличению времени выполнения расчета.

def mv2cwt(in_data)
    datalen    = len(in_data) # n
    data_ft    = np.fft.fft(in_data, n=datalen)
    N          = len(data_ft)
    s0         = 2*dt/Morlet_flambda()
    J          = np.round(np.log2(datalen*dt/s0)/dj)
    ftfreqs    = 2*np.pi*np.fft.fftfreq(N, dt)
    sj_col     = (s0*2**(np.arange(0, J+1)*dj))[:, np.newaxis]
    psi_ft_bar = (sj_col*ftfreqs[1]*N)**.5*
                  np.conjugate(Morlet_psi_ft(sj_col*ftfreqs))
    wave       = np.fft.ifft(data_ft*psi_ft_bar, axis=1, n=N)
    return wave

p = Pool(processes=22)
wave = p.map(mv2cwt, data)
p.close()
p.join()
```

Благодаря использованию параллельных расчетов время обработки сигналов для 3-х и 22-х каналов при сопоставимом количестве процессов удалось сократить до 0,07 и 0,8 секунд соответственно на двух физических процессорах.

Алгоритм работы и схема взаимодействия между блоками
------------------------

![Блок-схема алгоритма работы ПО](https://i.ibb.co/8DynYYy/im3.png)

![Архитектура ПО](https://i.ibb.co/XDnZd6c/algo.png)
