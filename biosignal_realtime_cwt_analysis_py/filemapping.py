# -*- coding: utf-8 -*-
import queue
import sys
import time
from datetime import timedelta

import numpy as np
from matplotlib import pyplot as plt

import changepriority as cpr
import multiprocpayload as mpp
import socketpayload as sp
from environment import *


def first_message(st: sp.FirstMessagePayload, fr, cwt_fr, ch):
    st.Frequency = INT64(fr)
    st.Cwt_Frequency = INT64(cwt_fr)
    st.Channels = INT64(ch)
    st.Timestamp = DOUBLE(datetime.now().timestamp())

    return st


def file_mapping(sock, data_q, shutdown_e, lock_q):
    def _2sec(dvalue):
        return dvalue.timestamp()

    def datetime_fromdelphi(dvalue):
        return DELPHI_EPOCH + timedelta(days=dvalue)

    def read_mem(cur_mem_buf, cur_pos, bts, save_pos, return_pos=True, bytesout=False, datetimedouble=False):
        size = sizeof(bts)
        bts_s = c.create_string_buffer(size)
        source = cur_mem_buf + cur_pos
        length = SIZE_T(size)
        RtlMoveMemory(bts_s, source, length)

        if save_pos:
            pos_to_return = cur_pos + size
        else:
            pos_to_return = cur_pos

        if bytesout:
            if return_pos:
                return np.array(bts_s, order='C').view(dtype=bts), pos_to_return
            else:
                return np.array(bts_s, order='C').view(dtype=bts)
        elif datetimedouble:
            if return_pos:
                return (datetime_fromdelphi(c.cast(bts_s, POINTER(bts)).contents.value).timestamp(),
                        pos_to_return)
            else:
                return datetime_fromdelphi(c.cast(bts_s, POINTER(bts)).contents.value).timestamp()
        else:
            if return_pos:
                return c.cast(bts_s, POINTER(bts)).contents.value, pos_to_return
            else:
                return c.cast(bts_s, POINTER(bts)).contents.value

    def _get_mv_data(cur_mem_buf, cur_pos, data, create):
        tpos = cur_pos

        def _desc_mv_map_ret(int_data):
            nonlocal cur_mem_buf
            nonlocal create
            nonlocal tpos
            buf = read_mem(cur_mem_buf, tpos, FLOAT, False, return_pos=False, bytesout=True)
            tpos += SINGLE_SIZE
            if create:
                return np.ndarray((1,), buffer=buf, dtype=FLOAT, order='C')
            else:
                return np.concatenate((int_data, np.ndarray((1,), buffer=buf,
                                                            dtype=FLOAT,
                                                            order='C')),
                                      axis=0)

        return list(map(_desc_mv_map_ret, data)), tpos

    def _frame_ret(data, datalen):
        def mapret(int_data):
            return int_data[-datalen:, ]

        return list(map(mapret, data))  # Выделение из общего массива считанных данных окна, равного CwtFreq

    while True:
        try:
            # hmap = CreateFileMappingW(INVALID_HANDLE_VALUE, SA, PAGE_READWRITE, 0, EXPECTED_SIZE, TAGNAME)
            hmap = OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, TAGNAME)
            handle_valid_nonzero_success(hmap)
            mem_buf = MapViewOfFile(hmap, FILE_MAP_ALL_ACCESS, 0, 0, EXPECTED_SIZE)
            break
        except WindowsError:
            print(c.WinError(c.get_last_error()))
            print('Перезапустите программу или запустите запись brainwin.exe...')
            time.sleep(5)
            continue

    tc = TChannel()

    while True:
        # noinspection PyUnboundLocalVariable
        freq, pos = read_mem(mem_buf, INT64_SIZE * 3, INT64, True)  # Частота оцифровки
        if freq:
            break

    cwt_freq = int(freq / DB)  # Частота преобразования и отправки данных и длина окна
    print('\nЧастота оцифровки: ', freq, 'Гц')

    channels, pos = read_mem(mem_buf, pos, INT64, True)  # Фактическое количество используемых каналов
    print('Количество каналов: ', channels)

    sock.sendall(first_message(sp.FirstMessagePayload(), freq, cwt_freq,
                               channels))  # Сообщение серверу с первоначальными данными
    data_q.put(channels, PUTBLOCK, PUTTIMEOUT)

    leads_act = [0] * channels
    leads_pas = [0] * channels
    leads = [(0, 0)] * channels
    for i in range(0, channels):
        leads_act[i], pos = read_mem(mem_buf, pos, INT, True)
        cp = pos
        pos = (cp + INTEGER_SIZE * (EXPECTED_CHANNELS - 1))
        leads_pas[i], pos = read_mem(mem_buf, pos, INT, False)
        pos = cp
        leads[i] = (tc.leads[leads_act[i]], tc.leads[leads_pas[i]])
    print('Отведения: ', leads)

    prepos1 = ((INT64_SIZE * 5 + INTEGER_SIZE * EXPECTED_CHANNELS * 2 +
                NAME_EXPECTED_LENGTH * ANSI_CHAR_SIZE))
    prepos2 = (DATETIME_SIZE + INT64_SIZE + SINGLE_SIZE * EXPECTED_CHANNELS)
    cur_cut, pos = read_mem(mem_buf, INT64_SIZE * 2, INT64, False)
    data_payload = mpp.DataMVPayload()
    data_len = 0
    data_mv = [list()] * channels

    flush_time = True
    flush_mv_data = True
    data_flow = False
    cpr.set_priority(5)
    sleep_duration = 1 / freq / 1000
    old_cut = cur_cut
    cwt_time = list()
    actual_time = list()
    cwt_cut = cur_cut
    e = None

    try:
        while not shutdown_e.is_set():
            if not data_flow:
                old_cut = cur_cut
                with lock_q:
                    cur_cut = read_mem(mem_buf, INT64_SIZE * 2, INT64, False, return_pos=False)
                actual_cut = cur_cut
                cwt_cut = cur_cut + (SMOOTH + 50)
                if old_cut < cur_cut:
                    data_flow = True
                    print("Анализ...\n")
                else:
                    time.sleep(sleep_duration)
                    continue
            else:
                actual_cut = read_mem(mem_buf, INT64_SIZE * 2, INT64, False, return_pos=False)
                if actual_cut < old_cut:
                    data_flow = False
                    data_len = 0
                    continue

            if actual_cut > cur_cut:
                cur_cut += 1
            else:
                time.sleep(sleep_duration)
                continue

            data_len += 1

            # Чтение момента регистрации сигналов из общей памяти
            with lock_q:
                pos = prepos1 + prepos2 * (divmod(cur_cut, MaxData)[1])
                astr_time, pos = read_mem(mem_buf, pos, DOUBLE, True, bytesout=True)
            #

            # Чтение данных из общей памяти и конкатенация биосигнала в мкВ в массив типа Float
            with lock_q:
                data_mv, pos = _get_mv_data(mem_buf, pos + INT64_SIZE, data_mv, flush_mv_data)

            if flush_mv_data:
                flush_mv_data = False
            #

            # Конкатенация времени в массив типа Double
            if flush_time:
                cwt_time = np.ndarray((1,), buffer=astr_time, dtype=DOUBLE, order='C')
                actual_time = np.ndarray((1,), buffer=datetime.now().timestamp(), dtype=DOUBLE, order='C')
                flush_time = False
            else:
                cwt_time = np.concatenate((cwt_time,
                                           np.ndarray((1,),
                                                      buffer=astr_time,
                                                      dtype=DOUBLE, order='C')),
                                          axis=0)
                actual_time = np.concatenate((actual_time,
                                              np.ndarray((1,),
                                                         buffer=datetime.now().timestamp(),
                                                         dtype=DOUBLE, order='C')),
                                             axis=0)
            #

            # Отправка массива данных в очередь для дальнейшей обработки с окном, равным CwtFreq
            if cur_cut - cwt_cut >= cwt_freq:
                if data_len > cwt_freq:
                    data_len = cwt_freq
                cwt_cut = cur_cut
                data_payload.mv_cut = INT64(cur_cut)
                data_payload.mv_data_length = INT64(data_len)
                data_payload.mv_timestamp = cwt_time[-(data_len + SMOOTH):, ]
                data_payload.mv_timestamp = actual_time[-(data_len + SMOOTH):, ]
                data_payload.mv_data = _frame_ret(data_mv, data_len + SMOOTH)
                data_q.put(data_payload, PUTBLOCK, PUTTIMEOUT)
                # print('\nРазмер окна: ' + str(data_len) + '\nСечение: ' + str(cur_cut))
                data_len = 0
            #
    except Exception as e:
        print("Filemapping error: ", e)
    except KeyboardInterrupt:
        print("Filemapping: Keyboard interrupt!")
        shutdown_e.set()
    finally:
        print('\n---------------------------------------------------------------\nАнализ окончен.')

        shutdown_e.set()

        # noinspection PyUnboundLocalVariable
        CloseHandle(hmap)
        UnmapViewOfFile(mem_buf)

        while True:
            try:
                data_payload = data_q.get(GETBLOCK, GETTIMEOUT)
            except queue.Empty:
                continue
            except EOFError:
                break
            break

        analyzed = data_payload.analyzed_sent
        if len(analyzed) == 0:
            print("Nothing to save on disk!")

            return

        try:
            print('Сохранение результатов!\n')
            timed = list(map(datetime_fromdelphi,
                             cwt_time[(SMOOTH_CUTRANGE + 50):(SMOOTH_CUTRANGE + 50) + len(analyzed[0])]))
            times = np.array(list(map(_2sec, timed)))
            times = times - np.min(times)
            actual_timed = cwt_time[(SMOOTH_CUTRANGE + 50):(SMOOTH_CUTRANGE + 50) + len(analyzed[0])]

            for i in range(channels):
                ar1 = (data_mv[i])[(SMOOTH_CUTRANGE + 50):(SMOOTH_CUTRANGE + 50) + len(analyzed[i])]
                ar2 = analyzed[i]
                plt.plot(times, ar1, linewidth=0.1)
                plt.plot(times, ar2, linewidth=0.4)
                plt.title("Результат анализа по каналу " + str(i + 1))
                plt.ylabel("Измеренные значения и мощность, мкВ")
                plt.xlabel("Длительность, сек")
                plt.xticks()
                plt.savefig('Channel_' + str(i + 1) + '_cwt.svg')
                plt.clf()
                ar = np.vstack((timed, actual_timed))
                ar = np.vstack((ar, ar1))
                ar = np.transpose(np.vstack((ar, ar2)))
                np.savetxt('Channel_' + str(i + 1) + '_cwt.csv', ar,
                           header='Time,MV,CWT', delimiter=",", encoding='utf-8', fmt='%s')
                print('Сохранено: Канал ' + str(i + 1) + '!\n')

        except Exception as e:
            print("Result saving error: ", e)
        finally:
            print("Filemapping: All done!")
            sys.exit(0)
