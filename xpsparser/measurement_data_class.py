# -*- coding: utf-8 -*-
"""
Created on Mon Feb  1 08:25:00 2021

@author: Mark
"""

class MetaData:
    def __init__(self):
        self.timestamp = ''
        self.dwell_time = ''
        self.n_scans = ''
        self.excitation_energy = ''
        self.method_type = ''
        self.data_labels = []
        self.device_settings = []

class DeviceSettings():
    def __init__(self):
        self.device_name = ''
        self.channel_id = ''
            
class AnalyzerSettings(DeviceSettings):
    def __init__(self):
        super().__init__()
        self.pass_energy = ''
        self.lens_modes = ''
        self.detector_voltage = ''
    
class DataChannel:
    def __init__(self):   
        pass
        
class MeasurementData:
    def __init__(self):
        self.metadata = MetaData()
        self.data = []
        
    def addDataChannel(self, data_channel):
        self.data += [data_channel]
            

        
        
       