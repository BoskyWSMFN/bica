# -*- coding: utf-8 -*-
from __future__ import division
from functools import partial
from scipy.signal import (gaussian,convolve)
from pycwt.wavelet import cwt
from multiprocessing import Pool
from appVar import *
import changePriority as cpr
import multiprocPayload as mpp
import numpy as np
import queue

def ar_elements(array):
    return array.ndim and array.size

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
    
    Message = mpp.DATACWT_PAYLOAD()
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