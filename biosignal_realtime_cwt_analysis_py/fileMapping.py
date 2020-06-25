# -*- coding: utf-8 -*-
from __future__ import division
from ctypes import sizeof,POINTER
from datetime import timedelta
from matplotlib import pyplot as plt
from appVar import *
import ctypes as C
import numpy as np
import changePriority as cpr
import multiprocPayload as mpp
import socketPayload as sp
import queue,time

def first_message(st, fr, cwtfr, ch):
    st.Frequency = INT64(fr)
    st.Cwt_Frequency = INT64(cwtfr)
    st.Channels = INT64(ch)
    st.Timestamp = DOUBLE(datetime.now().timestamp())
    return st

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
        RtlMoveMemory(bts_s, source, length)
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
            #hmap = CreateFileMappingW(INVALID_HANDLE_VALUE, SA, PAGE_READWRITE, 0, EXPECTED_SIZE, TAGNAME)
            hmap = OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, TAGNAME)
            handle_valid_nonzero_success(hmap)
            mbuf = MapViewOfFile(hmap, FILE_MAP_ALL_ACCESS, 0, 0, EXPECTED_SIZE)
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
    sock.sendall(first_message(sp.FIRST_MESSAGE_PAYLOAD(), Freq, CwtFreq, Channels)) # Сообщение серверу с первоначальными данными
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
    DataPayload = mpp.DATAMV_PAYLOAD()
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