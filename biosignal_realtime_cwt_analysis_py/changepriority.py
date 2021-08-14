# -*- coding: utf-8 -*-
"""
reference to https://gist.github.com/spiwn/1876666
"""
from ctypes import windll, c_bool, c_uint
from os import getpid

GetPriorityClass = windll.kernel32.GetPriorityClass
SetPriorityClass = windll.kernel32.SetPriorityClass
OpenProcess = windll.kernel32.OpenProcess
CloseHandle = windll.kernel32.CloseHandle


class Priorities:
    ABOVE_NORMAL_PRIORITY_CLASS = 0x8000
    BELOW_NORMAL_PRIORITY_CLASS = 0x4000
    HIGH_PRIORITY_CLASS = 0x0080
    IDLE_PRIORITY_CLASS = 0x0040
    NORMAL_PRIORITY_CLASS = 0x0020
    REALTIME_PRIORITY_CLASS = 0x0100
    order = [0x0040, 0x4000, 0x0020, 0x8000, 0x0080, 0x0100]
    reverseOrder = {'0x40': 0, '0x4000': 1, '0x20': 2, '0x8000': 3, '0x80': 4, '0x100': 5}


__shouldClose = [False]


def get_process_handle(process, inherit=False):
    __shouldClose[0] = True
    if not process:
        process = getpid()
    return OpenProcess(c_uint(0x0200 | 0x0400), c_bool(inherit), c_uint(process))


def set_priority_by_id(priority, process=None, inherit=False):
    return set_priority(priority, get_process_handle(process, inherit))


def set_priority(priority, process=None, inherit=False):
    if not process:
        process = get_process_handle(None, inherit)
    result = SetPriorityClass(process, c_uint(priority)) != 0
    if __shouldClose:
        CloseHandle(process)
        __shouldClose[0] = False
    return result


def increase_priority_by_id(process=None, inherit=False, times=1):
    # noinspection PyArgumentList
    return increase_priority(get_process_handle(process, inherit, times))


def increase_priority(process=None, inherit=False, times=1):
    if times < 1:
        raise ValueError("Wrong value for the number of increments")
    if not process:
        process = get_process_handle(None, inherit)
    current_priority = Priorities.reverseOrder[hex(GetPriorityClass(process))]
    if current_priority < (len(Priorities.order) - 1):
        return set_priority(Priorities.order[min(current_priority + times, len(Priorities.order) - 1)], process)
    return False


def decrease_priority_by_id(process=None, inherit=False, times=1):
    # noinspection PyArgumentList
    return decrease_priority(get_process_handle(process, inherit, times))


def decrease_priority(process=None, inherit=False, times=1):
    if times < 1:
        raise ValueError("Wrong value for the number of decrements")
    if not process:
        process = get_process_handle(None, inherit)
    current_priority = Priorities.reverseOrder[hex(GetPriorityClass(process))]
    if current_priority > 0:
        return set_priority(Priorities.order[max(0, current_priority - times)], process)
    return False
