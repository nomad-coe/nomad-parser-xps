#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import numpy as np
from datetime import datetime
import logging

from nomad.datamodel import EntryArchive
from nomad.parsing import MatchingParser
from nomad.units import ureg
from nomad.datamodel.metainfo.common_experimental import (
    Measurement,
    Metadata,
    Sample,
    Experiment,
    Instrument,
    Origin, Author,
    Data, DataHeader, Spectrum)

logger = logging.getLogger(__name__)

# Global variables
PRIMARY_SPECTRUM_INDICATORS = ['region', 'Region']
EXTERNAL_CHANNEL_INDICATORS = ['external channel', 'External Channel']

GROUP_METADATA_ATTRIBUTE_MAP = {
    'Acquisition Date':'timestamp',
    'Dwell Time':'dwell_time',
    'Group':'group_name',
    'Number of Scans':'n_scans',
    'Region':'spectrum_region',
    'Excitation Energy':'excitation_energy',
    'Values/Curve':'n_values',
    'Source':'source_label',            
    }

SETTINGS_ATTRIBUTE_MAP = {
    'Analysis Method':'analysis_method',
    'Analyzer Lens':'analyzer_lens',
    'Analyzer Slit':'analyzer_slit',
    'Detector Voltage':'detector_voltage',
    'Eff. Workfunction':'workfunction',
    'Scan Mode':'scan_mode',
    }

DEFAULT_ENERGY_UNIT = 'eV'

KNOWN_CHANNEL_LABELS = {
    'Ring Current':'ring current',
    'I_mirror':'mirror current', 
    'Excitation Energy':'excitation energy',
    'TEY':'total electron yield',
    }

KNOWN_CHANNEL_UNITS = {
    '[mA]':'mA',
    '[V]':'V', 
    '[eV]':'eV',
    }

KNOWN_DEVICE_NAMES = {
    'AMC Mono (TCP)':'monochromator',
    'UE56/2-PGM1 (TCP)':'beamline',
    'ARMIN-ADC3':'armin',
    'Armin10':'armin',
    }


DEFAULT_PRIMARY_DEVICE_NAME = 'Phoibos Hemispherical Analyzer'
DEFAULT_AXIS_DEVICE_NAME = 'HSA 3500 plus'
DEFAULT_METHOD_TYPE = 'XPS'

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
            

class XPSParser(MatchingParser):
    '''A parser for reading in ASCII-encoded .xy data from Specs Prodigy.
    
    Tested with SpecsLab Prodigy v 4.64.1-r88350.
    '''
    
    def __init__(self, **kwargs): 
        super().__init__(
            name='parsers/xps', code_name='XPS', domain='ems',
            code_homepage='https://www.example.eu/',
            mainfile_contents_re=r'"method_type": "(XPS)|(NEXAFS)"'
        )

        # Construct the parser
        
        self.kwarg_keys = ['author', 'sample', 'experiment_id', 'project',
                           'axis_id', 'primary_channel_id']
        
        self.default_axis_channel_id = 0
        self.default_primary_channel_id = 1
        
        for key in self.kwarg_keys:
            if key in kwargs.keys():
                setattr(self, key, kwargs[key])
            elif key == 'axis_id':
                setattr(self, key, self.default_axis_channel_id)
            elif key == 'primary_channel_id':
                setattr(self, key, self.default_primary_channel_id) 

        self.precision = 3
        self.line_nr = 0

    
    def _loadFile(self, filepath):
        with open(filepath) as file:
            for line in file:
                self.file_contents += [line]
                
    def _parseGlobalHeader(self, file_contents):
        ''' Parse the file's global header.'''
        empty_lines = 0

        while empty_lines < 2:
            temp_line = file_contents[self.line_nr].strip('#').strip()
            self.line_nr += 1
            if len(temp_line) == 0:
                empty_lines += 1
            else:
                temp_line = temp_line.split(':')
                self.global_header[temp_line[0].strip()] = temp_line[-1].strip()
                
    def _parseDataHeader(self, file_contents):
        ''' Parse the data header for the group of data channels.'''
        data_header = {}

        while file_contents[self.line_nr][0] == self.prefix:
            temp_line = self.file_contents[self.line_nr]
            self.line_nr += 1
            temp_line = temp_line.strip('#').split(':', 1)
            data_header[temp_line[0].strip()] = temp_line[-1].strip()
        return data_header
    
    def _parseDataValues(self, file_contents):
        ''' Parse the numerical values from the data array and convert to float.'''
        data_list = []

        while (len(file_contents) > (self.line_nr + 1)) and (file_contents[self.line_nr][0]!= self.prefix):
            temp_line = file_contents[self.line_nr].split()
            self.line_nr += 1
            if len(temp_line) == 0:
                end_of_data = True
            else:
                data_list += [[round(float(d.strip()),3) for d in temp_line]]
        return data_list
    
    def _checkExternalChannel(self, dictionary):
        ''' Check if the data channel is an external data channel.'''
        result = False

        for indicator in EXTERNAL_CHANNEL_INDICATORS:
            for key in dictionary.keys():
                if indicator in key.lower():
                    result = True
        return result
            
    def _groupSpectra(self, data_list):
        ''' Group together external channels with the primary data channel.'''
        self.spectra_groups = []
        channel_count = 0

        for data in data_list:
            if not self._checkExternalChannel(data[0]):
                data[0]['channel_type'] = 'primary'
                self.spectra_groups += [[data]]
            else:
                data[0]['channel_type'] = 'external'
                self.spectra_groups[-1] += [data]
                
     
    def _getGroupMetaData(self, group, metadata):
        ''' Gather all of the metadata for the group of data channels.'''
        
        # The primary data channel contains some of the group's metadata.
        for channel in group:
            if channel[0]['channel_type'] == 'primary':
                dictionary = channel[0]
                for key in dictionary.keys():
                    if key in GROUP_METADATA_ATTRIBUTE_MAP.keys():
                        attr = GROUP_METADATA_ATTRIBUTE_MAP[key]
                        value = dictionary[key]
                        setattr(metadata, attr, value)
                        
                # In cases where the spectrum was part of a loop or multiple scans,
                # the spectrum region is not stored in the data header.
                if 'Region' in dictionary.keys():
                    self.current_region = dictionary['Region']
                else:
                    setattr(metadata, 'spectrum_region', self.current_region)
                if 'Group' in dictionary.keys():
                    self.current_group = dictionary['Group']
                else:
                    setattr(metadata, 'group_name', self.current_group)
        
        # Get what can be found in the global header.
        for key in self.global_header.keys():
            if key in GROUP_METADATA_ATTRIBUTE_MAP.keys():
                attr = GROUP_METADATA_ATTRIBUTE_MAP[key]
                value = self.global_header[key]
                setattr(metadata, attr, value)
                
        # Then get from kwargs.
        for key in self.kwarg_keys:
            if key in self.__dict__.keys():
                setattr(metadata, key, getattr(self, key))
        
        # Then get method type.
        method_type = self._getMethodType(group)
        metadata.method_type = method_type
                
        return metadata

    def _getDeviceSettings(self, channel, device_settings_object):
        ''' Get the device settings.'''
        
        # First look in the channel's data.
        settings = device_settings_object
        for key in channel[0].keys():
            if key in SETTINGS_ATTRIBUTE_MAP.keys():
                attr = SETTINGS_ATTRIBUTE_MAP[key]
                value = channel[0][key]
                setattr(settings, attr, value)
        
        # Then look in the global header.
        for key in self.global_header.keys():
            if key in SETTINGS_ATTRIBUTE_MAP.keys():
                attr = SETTINGS_ATTRIBUTE_MAP[key]
                value = self.global_header[key]
                setattr(settings, attr, value)    
                
        settings.device_name = self._getDeviceName(channel)
        
        return settings
    
    def _getDeviceName(self, channel):
        ''' Get the name of the device.'''
        
        # The device name is not provided for the spectrometer, so 
        # get it from the default device name.
        if channel[0]['channel_type'] == 'primary':
            device_name = DEFAULT_PRIMARY_DEVICE_NAME
        elif channel[0]['channel_type'] == 'axis':
            device_name = DEFAULT_AXIS_DEVICE_NAME
        else:
            for key in channel[0].keys():
                if 'External Channel' in key:
                    for _device_name in KNOWN_DEVICE_NAMES.keys():
                        if _device_name in channel[0][key]:
                            device_name = KNOWN_DEVICE_NAMES[_device_name]
                        else:
                            device_name = 'unknown device'
        
        return device_name
    
    def _addDataChannels(self, group, measurement_data):
        ''' Add all the data channels to the measurement data.
        
        Arguments:
            - group: A list of dictionaries that contains all the meta-data and
                     data values for a spectrum and its external channels.
            - measurement_data: This is an instance of a MeasurementData class. 
                     It should hold all of the parsed data.

        Returns:
            The instance of MeasurementData class, populated with data and metadata.
        '''

        # First go get the data of the X-axis.
        x_channel = self._getXChannel(group, DataChannel())
        measurement_data.addDataChannel(x_channel)

        # Then go get for each of the additional data channels.
        for channel in group:
            y_channel = self._getChannelData(channel, DataChannel())
            y_channel.channel_id = self.channel_id
            self.channel_id += 1
            measurement_data.addDataChannel(y_channel)

        return measurement_data
    
    def _getChannelData(self, channel, data_channel):
        ''' Get the data and metadata for a single channel.'''
        unit, label = self._getUnit(channel)
        data_channel.label = label
        data_channel.unit = unit
        data_channel.values = self._getValues(channel)
        data_channel.device_settings = self._getDeviceSettings(channel, 
                                                               DeviceSettings())
        return data_channel   
        
    def _getValues(self, channel):
        ''' Get the actual numerical array from the channel.'''
        values = [v[1] for v in channel[1]]

        return values
    
    def _getUnit(self, channel):
        ''' Get the units and data channel label.'''
        if channel[0]['channel_type'] == 'primary':
            unit, label = self._getPrimaryUnit(channel)
        elif channel[0]['channel_type']=='external':
            unit, label = self._getExternalUnit(channel)           

        return unit, label
                    
    def _getPrimaryUnit(self, channel):
        ''' If the data channel is the primary channel, then its units are 
        in the global header.'''
        unit = ''
        label = ''
        if 'Count Rate' in self.global_header.keys():
            if self.global_header['Count Rate'] == 'Counts':
                unit = 'counts'
                label = 'total counts'
            elif self.global_header['Count Rate'] == 'Counts per Second':
                unit = 'counts per second'
                label = 'count rate'

        return unit, label
     
    def _getExternalUnit(self, channel):
        ''' If the data channel is external, then its label and units are
        in some labels close to the data array.'''
        unit = ''
        label = ''
        for key in channel[0].keys():
            if 'External Channel' in key:
                for _label in KNOWN_CHANNEL_LABELS.keys():
                    if _label in channel[0][key]:
                        label = KNOWN_CHANNEL_LABELS[_label]
                        break
                    else:
                        label = 'unknown data label'
                for _unit in KNOWN_CHANNEL_UNITS.keys():
                    if _unit in channel[0][key]:
                        unit = KNOWN_CHANNEL_UNITS[_unit]

        return unit, label
                     
    def _checkIfNexafs(self, group):
        ''' Check if the spectrum is NEXAFS data. This is not clear from the
        method type, and needs to be inferred from other metadata.'''
        NEXAFS = False
        for channel in group:
            if 'Scan Mode' in channel[0].keys():
                if channel[0]['Scan Mode'] == 'ConstantFinalState':
                    NEXAFS = True
            if 'ColumnLabels' in channel[0].keys():
                if 'Excitation Energy' in channel[0]['ColumnLabels']:
                    NEXAFS = True

        return NEXAFS
    
    def _getXChannel(self, group, data_channel):
        ''' Get data for the X channel.
        The X channel is exported differently than the Y values, so 
        it has its own method.
        
        Arguments:
            - group: A list of dictionaries that contains all the data and metadata
                   of the spectrum and its external channels.
            - data_channel: An instance of the DataChannel class.
                
        Returns:
            data_channel: An instance of the DataChannel class populated with data.
        '''
        data_channel.unit = DEFAULT_ENERGY_UNIT

        if self._checkIfNexafs(group):
            data_channel.label = 'excitation energy'
        elif 'Energy Axis' in self.global_header.keys():
            data_channel.label = self.global_header['Energy Axis']
        values = [g[0] for g in group[0][1]]
        data_channel.values = values
        data_channel.channel_id = self.channel_id
        channel = [{'channel_type':'axis'}]
        data_channel.device_settings = self._getDeviceSettings(channel, DeviceSettings())
        self.channel_id +=1

        return data_channel
    
    def _putGroupsIntoClasses(self, spectra_groups):
        ''' Take the parsed and grouped data, and put it into the 
        classes defined for measurement data.

        Arguments:
            - spectra_groups: The parsed and grouped data. Each item in the root list
                represents a spectrum, including all of its meta-data and
                external channels.
        '''
        data_set = []

        for group in spectra_groups:
            self.channel_id = 0
            measurement_data = MeasurementData()
            measurement_data.metadata = self._getGroupMetaData(group, MetaData())   
            measurement_data = self._addDataChannels(group, measurement_data)
            data_set += [measurement_data]

        return data_set
    
    def _getMethodType(self, group):
        if self._checkIfNexafs(group):
            method_type = 'NEXAFS'
        else:
            for channel in group:
                if 'Analysis Method' in channel[0].keys():
                    method_type = channel[0]['Analysis Method']
                else:
                    method_type = DEFAULT_METHOD_TYPE

        return method_type
    
    def objectToDict(self, obj):
        ''' Convert the list of MeasurementData objects to a nested dictionary.'''
        return self._todict(obj)
    
    def _todict(self, obj, classkey=None): 
        if isinstance(obj, dict):
            data = {}
            for (k, v) in obj.items():
                data[k] = self._todict(v, classkey)
            return data
        elif hasattr(obj, "_ast"):
            return self._todict(obj._ast())
        elif hasattr(obj, "__iter__") and not isinstance(obj, str):
            return [self._todict(v, classkey) for v in obj]
        elif hasattr(obj, "__dict__"):
            data = dict([(key, self._todict(value, classkey)) 
                for key, value in obj.__dict__.items() 
                if not callable(value) and not key.startswith('_')])
            if classkey is not None and hasattr(obj, "__class__"):
                data[classkey] = obj.__class__.__name__
            return data
        else:
            return obj
        
            
    def _moveChannelMetaToGlobal(self, dataset):
        ''' Move the channel metadata into the spectrum's global metadata.
        
        This is a bandaid fix to re-organize the data structure.
        '''
        for d in dataset:
            d['metadata']['data_labels'] = []
            d['metadata']['device_settings'] = []
            channel_values = []
            for s in d['data']:
                channel_id = s['channel_id']
                s['device_settings']['channel_id'] = channel_id
                d['metadata']['device_settings']+=[s['device_settings']]
                d['metadata']['data_labels'] += [{'channel_id':channel_id,
                                                  'label':s['label'],
                                                  'unit':s['unit']}]
                channel_values += [s['values']]
            d['data'] = channel_values
        return dataset
    
    def removeAlign(self):
        ''' Remove the 'align' spectra from the data-set.'''
        for idx, d in reversed(list(enumerate(self.dataset))):
            if 'align' in d['metadata']['spectrum_region'].lower():
                del self.dataset[idx]
                
    def extractAllTags(self):
        ''' Extract the user-entered metadata tags.'''
        for spectrum in self.dataset:
            self._extractTags(spectrum)
    
    def _extractTags(self, spectrum):
        tags = spectrum['metadata']['group_name'].split('#')
        spectrum['metadata']['experiment_parameters'] = {}
        vals = ''
        if len(tags)>1:
            for t in tags[1:]:
                key_val = t.split(':')
                key = key_val[0].strip()
                
                val = key_val[1].strip().strip(',')
    
                if len(val) != 0:
                    spectrum['metadata']['experiment_parameters'][key] = val
                    vals += val + ', '
            if len(tags[0].strip()) == 0:
                group_name = vals
            else:
                group_name = tags[0]
            spectrum['metadata']['group_name'] = group_name
            

    def run(self, mainfile: str, archive: EntryArchive, logger=logger):
        '''Parse the .xy file into a list of dictionaries.
        
        Parsed data is stored in the attribute 'self.data'.
        '''
        self.data = []
        self.file_contents = []
        self.prefix = '#'
        self.filepath = mainfile
        self._loadFile(mainfile)
        self.global_header = {}

        # Set Author , Experiment ID and Sample fields
        self.author = 'Mark Greiner'
        self.experiment_id = '236'
        self.sample = 'S434'

        # There is a global header for the whole file. First parse that.
        self._parseGlobalHeader(self.file_contents)

        # Then parse each of the data sets
        while len(self.file_contents) > (self.line_nr + 1):
            self.data+= [[self._parseDataHeader(self.file_contents),
                         self._parseDataValues(self.file_contents)]]

        self._groupSpectra(self.data)
        
        self.measurement_data = self._putGroupsIntoClasses(self.spectra_groups)
        
        self.dataset = self.objectToDict(self.measurement_data)
        
        self.dataset = self._moveChannelMetaToGlobal(self.dataset)

        self.removeAlign()
        self.extractAllTags()

        for item in self.dataset:
            # Create a measurement in the archive
            measurement = archive.m_create(Measurement)

            # Create metadata schematic and import values
            metadata = measurement.m_create(Metadata)

            # Load entries into each heading

            # Sample
            sample = metadata.m_create(Sample)
            sample.sample_id = item['metadata']['sample']
            sample.spectrum_region = item['metadata']['spectrum_region']

            # Experiment
            experiment = metadata.m_create(Experiment)
            experiment.method_name = item['metadata']['method_type']
            experiment.experiment_id = item['metadata']['experiment_id']
            experiment.experiment_publish_time = datetime.now()

            # Instrument
            instrument = metadata.m_create(Instrument)
            instrument.n_scans = item['metadata']['n_scans']
            instrument.dwell_time = item['metadata']['dwell_time']
            instrument.excitation_energy = item['metadata']['excitation_energy']

            if item['metadata'].get('source_label') is not None:
                instrument.source_label = item['metadata']['source_label']

            # Origin
            origin = metadata.m_create(Origin)

            # Author
            author = origin.m_create(Author)
            author.author_name = item['metadata']['author']
            author.group_name = item['metadata']['group_name']

            # Data Header
            data = measurement.m_create(Data)
            spectrum = data.m_create(Spectrum)
            channels_in_metainfo = []

            for dlabel in item['metadata']['data_labels']:
                current_label = dlabel['label'].lower().replace(' ', '_')
                channels_in_metainfo.append(current_label)

                conditions = [current_label != 'count', current_label != 'total_counts',
                              current_label != 'energy', current_label != 'kinetic_energy']

                if all(conditions):
                    data_header = spectrum.m_create(DataHeader)
                    data_header.channel_id = str(dlabel['channel_id'])
                    data_header.label = dlabel['label']
                    data_header.unit = dlabel['unit']
                    continue

            # Import Data
            supplemental_data = []
            for i, label in enumerate(channels_in_metainfo):
                if label == 'count' or label == 'total_counts':
                    label = 'count'
                    spectrum.count = np.array(item['data'][i])
                    continue
                if label == 'energy' or label == 'kinetic_energy':
                    value = np.array(
                        item['data'][i]) * ureg(item['metadata']['data_labels'][i]['unit'])
                    spectrum.energy = value
                    continue
                supplemental_data.append(item['data'][i])

            spectrum.n_values = len(item['data'][0])
            spectrum.n_channel = len(supplemental_data)

            spectrum.supplemental_channel_data = supplemental_data
