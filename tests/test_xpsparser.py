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

import pytest
import logging
import os.path

from nomad import utils
from nomad.datamodel import EntryArchive, EntryMetadata
from nomad.datamodel.ems import EMSMetadata

from xpsparser import XPSParser


@pytest.fixture(scope='session', autouse=True)
def nomad_logging():
    utils.set_console_log_level(logging.ERROR)


@pytest.fixture
def xpsparser():
    return XPSParser()


@pytest.mark.parametrize('path, n_values, n_channel', [
    ('data/multiple_channels.xy', 121, 3),
    ('data/EX236_oxidizing_Ir50Ru50.xy', 1201, 1)
])
def test_example(xpsparser, path, n_values, n_channel):
    archive = EntryArchive()
    xpsparser.run(
        os.path.join(os.path.dirname(__file__), path),
        archive, utils.get_logger(__name__))

    measurement = archive.section_measurement[0]
    assert measurement.section_metadata.section_sample.sample_id is not None
    assert measurement.section_metadata.section_experiment.method_name is not None
    if n_values is None:
        assert measurement.section_data is None
    else:
        assert measurement.section_data.section_spectrum[0].n_values == n_values
    if n_channel is None:
        assert measurement.section_data is None
    else:
        assert measurement.section_data.section_spectrum[0].n_channel == n_channel
        assert len(measurement.section_data.section_spectrum[0].supplemental_channel_data) == n_channel
        assert len(measurement.section_data.section_spectrum[0].supplemental_channel_header) == n_channel
