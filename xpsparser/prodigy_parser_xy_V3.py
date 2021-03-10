# -*- coding: utf-8 -*-
"""
Created on Wed Mar 10 18:02:55 2021

@author: Mark
"""

import matplotlib.pyplot as plt
import json
from datetime import datetime
from measurement_data_class import (
    MeasurementData, DataChannel, DeviceSettings, AnalyzerSettings, MetaData,
    )

class ProdigyParserXY():
    """A parser for reading in ASCII-encoded .xy data from Specs Prodigy.
    
    Tested with SpecsLab Prodigy v 4.64.1-r88350.
    """
    
    def __init__(self, **kwargs): 
        """Construct the parser."""
        
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

        self.primary_spectrum_indicators = ['region', 'Region']
        self.external_channel_indicators = ['external channel', 'External Channel']
        
        self.group_metadata_attribute_map = {
            'Acquisition Date':'timestamp',
            'Dwell Time':'dwell_time',
            'Group':'group_name',
            'Number of Scans':'n_scans',
            'Region':'spectrum_region',
            'Excitation Energy':'excitation_energy',
            'Values/Curve':'n_values',
            'Source':'source_label',            
            }
        
        self.settings_attribute_map = {
            'Analysis Method':'analysis_method',
            'Analyzer Lens':'analyzer_lens',
            'Analyzer Slit':'analyzer_slit',
            'Detector Voltage':'detector_voltage',
            'Eff. Workfunction':'workfunction',
            'Scan Mode':'scan_mode',
            }
        
        self.default_energy_unit = 'eV'
        
        self.known_channel_labels = {'Ring Current':'ring current',
                                     'I_mirror':'mirror current', 
                                     'Excitation Energy':'excitation energy',
                                     'TEY':'total electron yield',
                                     }
        
        self.known_channel_units = {'[mA]':'mA',
                                    '[V]':'V', 
                                    '[eV]':'eV',
                                    }
        
        self.known_device_names = {'AMC Mono (TCP)':'monochromator',
                                   'UE56/2-PGM1 (TCP)':'beamline',
                                   'ARMIN-ADC3':'armin',
                                   'Armin10':'armin',
                                   }
        
        self.default_primary_device_name = 'Phoibos Hemispherical Analyzer'
        self.default_axis_device_name = 'HSA 3500 plus'
        
        self.default_method_type = 'XPS'
        
        self.precision = 3
        self.line_nr = 0

    def parseFile(self, filepath, commentprefix = '#'):
        """Parse the .xy file into a list of dictionaries.
        
        Parsed data is stored in the attribute 'self.data'.
        """
        self.data = []
        self.file_contents = []
        self.prefix = commentprefix
        self.filepath = filepath
        self._loadFile(filepath)
        self.global_header = {}
        """ There is a global header for the whole file. First parse that."""
        self._parseGlobalHeader(self.file_contents)

        """ Then parse each of the data sets."""
        while len(self.file_contents) > (self.line_nr + 1):
            self.data+= [[self._parseDataHeader(self.file_contents),
                         self._parseDataValues(self.file_contents)]]
        self._groupSpectra(self.data)
        
        self.measurement_data = self._putGroupsIntoClasses(self.spectra_groups)
        
        self.dataset = self.objectToDict(self.measurement_data)
        
        self.dataset = self._moveChannelMetaToGlobal(self.dataset)
    
    def _loadFile(self, filepath):
        with open(filepath) as file:
            for line in file:
                self.file_contents += [line]
                
    def _parseGlobalHeader(self, file_contents):
        """ Parse the file's global header."""
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
        """ Parse the data header for the group of data channels."""
        data_header = {}

        while file_contents[self.line_nr][0] == self.prefix:
            temp_line = self.file_contents[self.line_nr]
            self.line_nr += 1
            temp_line = temp_line.strip('#').split(':', 1)
            data_header[temp_line[0].strip()] = temp_line[-1].strip()
        return data_header
    
    def _parseDataValues(self, file_contents):
        """ Parse the numerical values from the data array and convert to
        float."""
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
        """ Check if the data channel is an external data channel."""
        result = False
        for indicator in self.external_channel_indicators:
            for key in dictionary.keys():
                if indicator in key.lower():
                    result = True
        return result
            
    def _groupSpectra(self, data_list):
        """ Group together external channels with the primary data channel."""
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
        """ Gather all of the metadata for the group of data channels."""
        
        """ The primary data channel contains some of the group's metadata."""
        for channel in group:
            if channel[0]['channel_type'] == 'primary':
                dictionary = channel[0]
                for key in dictionary.keys():
                    if key in self.group_metadata_attribute_map.keys():
                        attr = self.group_metadata_attribute_map[key]
                        value = dictionary[key]
                        setattr(metadata, attr, value)
                        
                """ In cases where the spectrum was part of a loop or multiple scans,
                the spectrum region is not stored in the data header."""
                if 'Region' in dictionary.keys():
                    self.current_region = dictionary['Region']
                else:
                    setattr(metadata, 'spectrum_region', self.current_region)
                if 'Group' in dictionary.keys():
                    self.current_group = dictionary['Group']
                else:
                    setattr(metadata, 'group_name', self.current_group)
        
        """ Get what can be found in the global header."""
        for key in self.global_header.keys():
            if key in self.group_metadata_attribute_map.keys():
                attr = self.group_metadata_attribute_map[key]
                value = self.global_header[key]
                setattr(metadata, attr, value)
                
        """ Then get from kwargs."""
        for key in self.kwarg_keys:
            if key in self.__dict__.keys():
                setattr(metadata, key, getattr(self, key))
        
        """ Then get method type."""
        method_type = self._getMethodType(group)
        metadata.method_type = method_type
                
        return metadata

    def _getDeviceSettings(self, channel, device_settings_object):
        """ Get the device settings."""
        
        """ First look in the channel's data."""
        settings = device_settings_object
        for key in channel[0].keys():
            if key in self.settings_attribute_map.keys():
                attr = self.settings_attribute_map[key]
                value = channel[0][key]
                setattr(settings, attr, value)
        
        """ Then look in the global header."""
        for key in self.global_header.keys():
            if key in self.settings_attribute_map.keys():
                attr = self.settings_attribute_map[key]
                value = self.global_header[key]
                setattr(settings, attr, value)    
                
        settings.device_name = self._getDeviceName(channel)
        
        return settings
    
    def _getDeviceName(self, channel):
        """ Get the name of the device."""
        
        """ The device name is not provided for the spectrometer, so 
        get it from the default device name.
        """
        if channel[0]['channel_type'] == 'primary':
            device_name = self.default_primary_device_name
        elif channel[0]['channel_type'] == 'axis':
            device_name = self.default_axis_device_name
        else:
            for key in channel[0].keys():
                if 'External Channel' in key:
                    for _device_name in self.known_device_names.keys():
                        if _device_name in channel[0][key]:
                            device_name = self.known_device_names[_device_name]
                        else:
                            device_name = 'unknown device'
        
        return device_name
    
    def _addDataChannels(self, group, measurement_data):
        """ Add all the data channels to the measurement data.
        PARAMETERS:
        ----------
            group: list of dictionaries
                A list of dictionaries that contains all the meta-data and
                data values for a spectrum and its external channels.
            measurement_data: MeasurementData
                This is an instance of a MeasurementData class. It should hold
                all of the parsed data.
        RETURNS:
        -------
            meausurment_data: MeasurementData
                The instance of MeasurementData class, populated with data
                and metadata.
        """

        """ First go get the data of the X-axis."""
        x_channel = self._getXChannel(group, DataChannel())
        measurement_data.addDataChannel(x_channel)
        """ Then go get for each of the additional data channels."""
        for channel in group:
            y_channel = self._getChannelData(channel, DataChannel())
            y_channel.channel_id = self.channel_id
            self.channel_id += 1
            measurement_data.addDataChannel(y_channel)
        return measurement_data
    
    def _getChannelData(self, channel, data_channel):
        """ Get the data and metadata for a single channel."""
        unit, label = self._getUnit(channel)
        data_channel.label = label
        data_channel.unit = unit
        data_channel.values = self._getValues(channel)
        data_channel.device_settings = self._getDeviceSettings(channel, 
                                                               DeviceSettings())
        return data_channel   
        
    def _getValues(self, channel):
        """ Get the actual numerical array from the channel."""
        values = [v[1] for v in channel[1]]
        return values
    
    def _getUnit(self, channel):
        """ Get the units and data channel label."""
        if channel[0]['channel_type'] == 'primary':
            unit, label = self._getPrimaryUnit(channel)
        elif channel[0]['channel_type']=='external':
            unit, label = self._getExternalUnit(channel)           
        return unit, label
                    
    def _getPrimaryUnit(self, channel):
        """ If the data channel is the primary channel, then its units are 
        in the global header."""
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
        """ If the data channel is external, then its label and units are
        in some labels close to the data array."""
        unit = ''
        label = ''
        for key in channel[0].keys():
            if 'External Channel' in key:
                for _label in self.known_channel_labels.keys():
                    if _label in channel[0][key]:
                        label = self.known_channel_labels[_label]
                        break
                    else:
                        label = 'unknown data label'
                for _unit in self.known_channel_units.keys():
                    if _unit in channel[0][key]:
                        unit = self.known_channel_units[_unit]
        return unit, label
                     
    def _checkIfNexafs(self, group):
        """ Check if the spectrum is NEXAFS data. This is not clear from the
        method type, and needs to be inferred from other metadata."""
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
        """ Get data for the X channel.
        The X channel is exported differently than the Y values, so 
        it has its own method.
        
        PARAMETERS:
        ----------
            group: list of dictionaries
                A list of dictionaries that contains all the data and metadata
                of the spectrum and its external channels.
            data_channel: DataChannel
                An instance of the DataChannel class.
                
        RETURNS:
        --------
            data_channel: DataChannel
                An instance of the DataChannel class populated with data.
        """
        data_channel.unit = self.default_energy_unit
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
        """ Take the parsed and grouped data, and put it into the 
        classes defined for measurement data.
        PARAMETERS:
        ----------
            spectra_groups: list of lists of dicts
                The parsed and grouped data. Each item in the root list
                represents a spectrum, including all of its meta-data and
                external channels.
        """
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
                    method_type = self.default_method_type
        return method_type
    
    def objectToDict(self, obj):
        """ Convert the list of MeasurementData objects to a nested dictionary."""
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
        
    def writeJSON(self, filename):
        """ Write the currently loaded data-set to a JSON file."""
        with open(f'{filename}.json', 'w') as fp:
            json.dump(self.dataset, fp, indent=4)
            
    def _moveChannelMetaToGlobal(self, dataset):
        """ Move the channel metadata into the spectrum's global metadata.
        
        This is a bandaid fix to re-organize the data structure.
        """
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
        """ Remove the 'align' spectra from the data-set."""
        for idx, d in reversed(list(enumerate(self.dataset))):
            if 'align' in d['metadata']['spectrum_region'].lower():
                del self.dataset[idx]
                
    def extractAllTags(self):
        """ Extract the user-entered metadata tags."""
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
            
    def convertToJson(self, filepath):
        """ Convert directly from XY to JSON."""
        self.parseFile(filepath)
        self.removeAlign()
        self.extractAllTags()
        name = filepath.rsplit('.',1)[0]
        self.writeJSON(name)
        

#%%  Usage example
 
if __name__ == "__main__": 
    '''Instantiate the parser. You can give 'author', 'experiment_id' and
    'sample' as additional metadata.'''
    parser = ProdigyParserXY(author='Mark Greiner', experiment_id='236', sample='S434')
    f = r'C:\Users\Mark\ownCloud\Muelheim Group\Projects\xps_data_conversion_tools\files\EX236 oxidizing_Ir50Ru50.xy'
    
    ''' You can convert directly to JSON.'''
    parser.convertToJson(f)
    
    ''' Or you can run the parser and have a look at the data in a dictionary.'''
    parser.parseFile(f)
    parser.removeAlign()
    parser.extractAllTags()
    data_set = parser.dataset
    
    #%%
    ''' Here is an example of how to plot the data.'''
    
    spectrum_types = list(set([d['metadata']['spectrum_region'] for d in data_set]))
    
    selection = spectrum_types[0]
    channel_nr = 1
    for data in data_set:
        if data['metadata']['spectrum_region'] == selection:
            axis_id = data['metadata']['axis_id']
            plt.plot(data['data'][axis_id], data['data'][channel_nr])
            plt.xlabel(data['metadata']['data_labels'][axis_id]['label'] 
                       + ' [' + data['metadata']['data_labels'][axis_id]['unit'] 
                       + ']', fontsize=14)
            plt.ylabel(data['metadata']['data_labels'][channel_nr]['label'] + 
                       ' [' + data['metadata']['data_labels'][channel_nr]['unit'] 
                       + ']', fontsize=14)
    plt.show()
