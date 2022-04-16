# -*- coding: utf-8 -*-
import queue
import sys
from functools import partial
from multiprocessing import Pool

import numpy as np
from pycwt.wavelet import cwt
from scipy.signal.signaltools import convolve
from scipy.signal.windows import gaussian

import changepriority as cpr
import multiprocpayload as mpp
from environment import *


def ar_elements(array):
    return array.ndim and array.size


def mv2cwt(an_dt, an_s0, an_j, an_datalen, an_fltr, data):
    if ar_elements(data) == 0:
        return

    try:
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
                                                      EST_WAVELET)  # Выше указан алгоритм произведения анализа

        power = np.abs(wave)  # Мощность по модулю в квадрате
        tmean = np.transpose(np.mean(power[an_fltr[0]:an_fltr[1]],
                                     axis=0))  # Обрезка по диапазону частот, вычисление среднего и транспонирование
        # получившейся 2D-матрицы, производится для совмещения "сырого" и обработанного сигнала по длительности.
        gauss_filter = gaussian(len(tmean), std=10)
        gauss_filter = gauss_filter / np.sum(
            gauss_filter)  # Создание сглаживающей гаусианны с длиной, равной размеру окна, для дальнейшей свертки.
        buff = convolve(tmean, gauss_filter, 'same')  # Свертка с фильтром
        return (buff.astype(dtype=DOUBLE, order='C',
                            copy=False))[SMOOTH_CUTRANGE:an_datalen - SMOOTH_CUTRANGE]
    except KeyboardInterrupt:
        return


def signal_analysis(data_q, data_s, shutdown_e, quasi_freq_filter):
    def get_cwt(cur_pool, data, dt, datalen):

        s0 = 2 * dt / EST_WAVELET.flambda()
        j = np.int(np.round(np.log2(datalen * dt / s0) / DJ))
        func = partial(mv2cwt, dt, s0, j, datalen, quasi_freq_filter)
        return cur_pool.map(func, data)

    message = mpp.DataCWTPayload()
    channels = EXPECTED_CHANNELS

    while not shutdown_e.is_set():
        # Чтение данных из очереди
        try:
            channels = data_q.get(GETBLOCK, GETTIMEOUT)
            break
        except queue.Empty:
            continue
        except EOFError:
            shutdown_e.set()
            break
        #

    pool = Pool(processes=channels)
    data_payload = mpp.DataMVPayload()
    cpr.set_priority(1)
    analyzed = list()
    cwt_cut = 1
    first_time = True

    try:
        flush_cwt = True

        while not shutdown_e.is_set():
            # Чтение данных из очереди
            try:
                data_payload = data_q.get(GETBLOCK, GETTIMEOUT)
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                print("Keyboard interrupt!")
                shutdown_e.set()

                break
            except EOFError:
                shutdown_e.set()

                break
            #

            # Отправка данных на анализ и преобразование
            cwt_dt = np.diff(data_payload.mv_timestamp).mean()  # Вычисление интервала между точками
            cwt_data = get_cwt(pool, data_payload.mv_data, cwt_dt,
                               data_payload.mv_data_length.value + SMOOTH)
            #

            #
            if first_time:
                first_time = False
                data_s.put(data_payload.mv_data_length, PUTBLOCK, PUTTIMEOUT)
            #

            # Отправка данных в очередь на формирование пакета Sockets
            message.cwt_cut = INT64(cwt_cut)
            message.cwt_data_length = data_payload.mv_data_length
            message.cwt_time_interval = FLOAT(cwt_dt)
            message.cwt_data = cwt_data
            data_s.put(message, PUTBLOCK, PUTTIMEOUT)
            #

            #
            if flush_cwt:
                analyzed = cwt_data
                flush_cwt = False
            else:
                analyzed = np.concatenate((analyzed, cwt_data), axis=1)
            cwt_cut += 1
            #
    except KeyboardInterrupt:
        print("Signal analyzer: Keyboard interrupt!")
        shutdown_e.set()
    except Exception as e:
        print("Signal analyzer error: ", e)
        shutdown_e.set()
    finally:
        if data_payload is not None:
            data_payload.analyzed_sent = analyzed
            data_q.put(data_payload, PUTBLOCK, PUTTIMEOUT)
        pool.terminate()
        pool.close()
        pool.join()
        print("Signal analyzer: All done!")
        sys.exit(0)
