# -*- coding: utf-8 -*-
import queue
import socket
import sys

import numpy as np

import changepriority as cpr
import socketpayload as sp
from environment import *


def get_premessage(st: sp.MessagePreload, cut, size):
    st.Cut = cut
    st.Size = INT64(size)
    return st


def socket_client(data_s, shutdown_e, connection, lock_q):
    cpr.set_priority(1)
    pre_message = sp.MessagePreload()
    message = sp.get_socket_payload(0)
    ar_type = [DOUBLE]

    while not shutdown_e.is_set():
        try:
            cwt_freq = data_s.get(GETBLOCK, GETTIMEOUT)
            message = sp.get_socket_payload(cwt_freq.value * DB)
            ar_type = DOUBLE * cwt_freq.value

            break
        except queue.Empty:
            continue
        except KeyboardInterrupt:
            print("Keyboard interrupt!")
            shutdown_e.set()

            break
        except EOFError:
            shutdown_e.set()

            break

    i = 0
    ch = 0

    try:
        while not shutdown_e.is_set():
            try:
                input_message = data_s.get(GETBLOCK, GETTIMEOUT)
            except queue.Empty:
                continue
            except EOFError:
                shutdown_e.set()

                break

            message.Cut = input_message.cwt_cut
            message.Timestamp = input_message.cwt_timestamp
            message.TimeInterval = input_message.cwt_time_interval

            for _ in input_message.cwt_data:
                ch += 1
            # noinspection PyProtectedMember
            for f in message._fields_:
                if i == ch:
                    break
                if f[1] == ar_type:
                    setattr(message, f[0], np.ctypeslib.as_ctypes(input_message.cwt_data[i]))
                    i += 1

            i = 0
            ch = 0

            try:
                connection.sendall(get_premessage(pre_message, message.Cut, c.sizeof(message)))
                message.Timestamp = DOUBLE(datetime.utcnow().timestamp())
                connection.sendall(message)  # Отправка преобразованных данных через протокол Sockets
            except KeyboardInterrupt:
                print("Keyboard interrupt!")
                shutdown_e.set()
            except socket.error as e:
                print(e)
                shutdown_e.set()
    except KeyboardInterrupt:
        print("Socket client: Keyboard interrupt!")
        shutdown_e.set()
    except Exception as e:
        print("Socket client error: ", e)
        shutdown_e.set()
    finally:
        print("Socket client: All done!")
        sys.exit(0)
