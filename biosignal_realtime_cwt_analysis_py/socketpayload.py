# -*- coding: utf-8 -*-

from environment import *

frame_200hz = 50
frame_250hz = 62
frame_500hz = 125
frame_1khz = 250


class FirstMessagePayload(Structure):
    _fields_ = (("Frequency", INT64),
                ("Cwt_Frequency", INT64),
                ("Channels", INT64),
                ("Timestamp", DOUBLE))


class MessagePreload(Structure):
    _fields_ = (("Cut", INT64),
                ("Size", INT64))


# noinspection DuplicatedCode
class MessagePayload200Hz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("TimeInterval", FLOAT),
                ("Channel_1", DOUBLE * frame_200hz),
                ("Channel_2", DOUBLE * frame_200hz),
                ("Channel_3", DOUBLE * frame_200hz),
                ("Channel_4", DOUBLE * frame_200hz),
                ("Channel_5", DOUBLE * frame_200hz),
                ("Channel_6", DOUBLE * frame_200hz),
                ("Channel_7", DOUBLE * frame_200hz),
                ("Channel_8", DOUBLE * frame_200hz),
                ("Channel_9", DOUBLE * frame_200hz),
                ("Channel_10", DOUBLE * frame_200hz),
                ("Channel_11", DOUBLE * frame_200hz),
                ("Channel_12", DOUBLE * frame_200hz),
                ("Channel_13", DOUBLE * frame_200hz),
                ("Channel_14", DOUBLE * frame_200hz),
                ("Channel_15", DOUBLE * frame_200hz),
                ("Channel_16", DOUBLE * frame_200hz),
                ("Channel_17", DOUBLE * frame_200hz),
                ("Channel_18", DOUBLE * frame_200hz),
                ("Channel_19", DOUBLE * frame_200hz),
                ("Channel_20", DOUBLE * frame_200hz),
                ("Channel_21", DOUBLE * frame_200hz),
                ("Channel_22", DOUBLE * frame_200hz))

    def pack(self):
        return c.string_at(c.byref(self), c.sizeof(self))

    def unpack(self, buf):
        return c.cast(c.pointer(c.create_string_buffer(buf)), POINTER(self)).contents

    def __init__(self, *args, **kwargs):
        super(MessagePayload200Hz, self).__init__(*args, **kwargs)


# noinspection DuplicatedCode
class MessagePayload250Hz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("TimeInterval", FLOAT),
                ("Channel_1", DOUBLE * frame_250hz),
                ("Channel_2", DOUBLE * frame_250hz),
                ("Channel_3", DOUBLE * frame_250hz),
                ("Channel_4", DOUBLE * frame_250hz),
                ("Channel_5", DOUBLE * frame_250hz),
                ("Channel_6", DOUBLE * frame_250hz),
                ("Channel_7", DOUBLE * frame_250hz),
                ("Channel_8", DOUBLE * frame_250hz),
                ("Channel_9", DOUBLE * frame_250hz),
                ("Channel_10", DOUBLE * frame_250hz),
                ("Channel_11", DOUBLE * frame_250hz),
                ("Channel_12", DOUBLE * frame_250hz),
                ("Channel_13", DOUBLE * frame_250hz),
                ("Channel_14", DOUBLE * frame_250hz),
                ("Channel_15", DOUBLE * frame_250hz),
                ("Channel_16", DOUBLE * frame_250hz),
                ("Channel_17", DOUBLE * frame_250hz),
                ("Channel_18", DOUBLE * frame_250hz),
                ("Channel_19", DOUBLE * frame_250hz),
                ("Channel_20", DOUBLE * frame_250hz),
                ("Channel_21", DOUBLE * frame_250hz),
                ("Channel_22", DOUBLE * frame_250hz))

    def pack(self):
        return c.string_at(c.byref(self), c.sizeof(self))

    def unpack(self, buf):
        return c.cast(c.pointer(c.create_string_buffer(buf)), POINTER(self)).contents

    def __init__(self, *args, **kwargs):
        super(MessagePayload250Hz, self).__init__(*args, **kwargs)


# noinspection DuplicatedCode
class MessagePayload500Hz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("TimeInterval", FLOAT),
                ("Channel_1", DOUBLE * frame_500hz),
                ("Channel_2", DOUBLE * frame_500hz),
                ("Channel_3", DOUBLE * frame_500hz),
                ("Channel_4", DOUBLE * frame_500hz),
                ("Channel_5", DOUBLE * frame_500hz),
                ("Channel_6", DOUBLE * frame_500hz),
                ("Channel_7", DOUBLE * frame_500hz),
                ("Channel_8", DOUBLE * frame_500hz),
                ("Channel_9", DOUBLE * frame_500hz),
                ("Channel_10", DOUBLE * frame_500hz),
                ("Channel_11", DOUBLE * frame_500hz),
                ("Channel_12", DOUBLE * frame_500hz),
                ("Channel_13", DOUBLE * frame_500hz),
                ("Channel_14", DOUBLE * frame_500hz),
                ("Channel_15", DOUBLE * frame_500hz),
                ("Channel_16", DOUBLE * frame_500hz),
                ("Channel_17", DOUBLE * frame_500hz),
                ("Channel_18", DOUBLE * frame_500hz),
                ("Channel_19", DOUBLE * frame_500hz),
                ("Channel_20", DOUBLE * frame_500hz),
                ("Channel_21", DOUBLE * frame_500hz),
                ("Channel_22", DOUBLE * frame_500hz))

    def pack(self):
        return c.string_at(c.byref(self), c.sizeof(self))

    def unpack(self, buf):
        return c.cast(c.pointer(c.create_string_buffer(buf)), POINTER(self)).contents

    def __init__(self, *args, **kwargs):
        super(MessagePayload500Hz, self).__init__(*args, **kwargs)


# noinspection DuplicatedCode
class MessagePayload1KHz(Structure):
    _fields_ = (("Cut", INT64),
                ("Data_Length", INT64),
                ("Timestamp", DOUBLE),
                ("TimeInterval", FLOAT),
                ("Channel_1", DOUBLE * frame_1khz),
                ("Channel_2", DOUBLE * frame_1khz),
                ("Channel_3", DOUBLE * frame_1khz),
                ("Channel_4", DOUBLE * frame_1khz),
                ("Channel_5", DOUBLE * frame_1khz),
                ("Channel_6", DOUBLE * frame_1khz),
                ("Channel_7", DOUBLE * frame_1khz),
                ("Channel_8", DOUBLE * frame_1khz),
                ("Channel_9", DOUBLE * frame_1khz),
                ("Channel_10", DOUBLE * frame_1khz),
                ("Channel_11", DOUBLE * frame_1khz),
                ("Channel_12", DOUBLE * frame_1khz),
                ("Channel_13", DOUBLE * frame_1khz),
                ("Channel_14", DOUBLE * frame_1khz),
                ("Channel_15", DOUBLE * frame_1khz),
                ("Channel_16", DOUBLE * frame_1khz),
                ("Channel_17", DOUBLE * frame_1khz),
                ("Channel_18", DOUBLE * frame_1khz),
                ("Channel_19", DOUBLE * frame_1khz),
                ("Channel_20", DOUBLE * frame_1khz),
                ("Channel_21", DOUBLE * frame_1khz),
                ("Channel_22", DOUBLE * frame_1khz))

    def pack(self):
        return c.string_at(c.byref(self), c.sizeof(self))

    def unpack(self, buf):
        return c.cast(c.pointer(c.create_string_buffer(buf)), POINTER(self)).contents

    def __init__(self, *args, **kwargs):
        super(MessagePayload1KHz, self).__init__(*args, **kwargs)


def get_socket_payload(freq):
    if freq == 200:
        return MessagePayload200Hz()
    elif freq == 250:
        return MessagePayload250Hz()
    elif freq == 500:
        return MessagePayload500Hz()
    elif freq == 1000:
        return MessagePayload1KHz()
    else:
        return None
