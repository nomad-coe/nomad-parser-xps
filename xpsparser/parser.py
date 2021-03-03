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

# import datetime
# import numpy as np
import json
import numpy as np
from datetime import datetime
import logging
from nomad.units import ureg

from nomad.datamodel import EntryArchive
from nomad.parsing import FairdiParser

from . import metainfo  # pylint: disable=unused-import
from .metainfo import *
'''
This is a test parser for XPS Parser
'''

logger = logging.getLogger(__name__)


class XPSParser(FairdiParser):
    def __init__(self):
        super().__init__(
            name='parsers/xpsparser', code_name='XPS', code_homepage='https://www.example.eu/',
            mainfile_mime_re=r'(application/json)'
        )

    def run(self, mainfile: str, archive: EntryArchive, logger):
        # Log a hello world, just to get us started.
        logger.info('Testing the XPS World')

        # Read the JSON file into a dictionary
        with open(mainfile, 'rt') as f:
            file_data = json.load(f)

        for item in file_data:
            # Create a measurement in the archive
            measurement = archive.m_create(Measurement)

            """
            Create metadata schematic and import values
            """
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
            # experiment.experiment_start_time = datetime.strptime(
            # item['metadata']['timestamp'], '%d-%m-%Y %H:%M:%S')

            # Instrument
            instrument = metadata.m_create(Instrument)
            instrument.n_scans = item['metadata']['n_scans']
            instrument.dwell_time = item['metadata']['dwell_time']
            instrument.excitation_energy = item['metadata']['excitation_energy']

            if item['metadata']['source_label'] is not None:
                instrument.source_label = item['metadata']['source_label']

            # Origin
            origin = metadata.m_create(Origin)

            # Author
            author = origin.m_create(Author)
            author.author_name = item['metadata']['author']
            author.group_name = item['metadata']['group_name']

            # Data Header
            labels_to_match = []
            for dlabel in item['metadata']['data_labels']:
                data_header = metadata.m_create(DataHeader)
                data_header.channel_id = dlabel['channel_id']
                data_header.label = dlabel['label']
                data_header.unit = dlabel['unit']
                labels_to_match.append(dlabel['label'].replace(' ', '_'))

            # Import Data
            data = measurement.m_create(Data)
            for i, label in enumerate(labels_to_match):
                spectrum = data.m_create(Spectrum)
                if label == 'count':
                    value = np.array(item['data'][i])
                else:
                    value = np.array(item['data'][i]) * ureg(item['metadata']['data_labels'][i]['unit'])
                setattr(spectrum, label, value)
