# -*- coding: utf-8 -*-
import numpy as np

from environment import *


class DataCWTPayload(object):

    def __init__(self, *args, **kwargs):
        super(DataCWTPayload, self).__init__(*args, **kwargs)
        self.cwt_cut = INT64()
        self.cwt_data_length = INT64()
        self.cwt_timestamp = DOUBLE()
        self.cwt_time_interval = FLOAT()
        self.cwt_data = [np.array([], dtype=DOUBLE, order='C')] * EXPECTED_CHANNELS


class DataMVPayload(object):

    def __init__(self, *args, **kwargs):
        super(DataMVPayload, self).__init__(*args, **kwargs)
        self.mv_cut = INT64()
        self.mv_data_length = INT64()
        self.mv_timestamp = np.array([], dtype=DOUBLE, order='C')
        self.actual_timestamp = np.array([], dtype=DOUBLE, order='C')
        self.mv_data = [np.array([], dtype=FLOAT, order='C')] * EXPECTED_CHANNELS
        self.analyzed_sent = [np.array([], dtype=DOUBLE, order='C')] * EXPECTED_CHANNELS
