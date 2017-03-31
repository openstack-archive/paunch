# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

'''Stable library interface to managing containers with paunch.'''

import logging

import pbr.version

from paunch.builder import compose1
from paunch import runner

__version__ = pbr.version.VersionInfo('paunch').version_string()

LOG = logging.getLogger(__name__)


def apply(config_id, config, managed_by, labels=None):
    builder = compose1.ComposeV1Builder(
        config_id=config_id,
        config=config,
        managed_by=managed_by,
        labels=labels
    )
    return builder.apply()


def cleanup(config_ids, managed_by):
    runner.delete_missing_configs(config_ids)
    runner.rename_containers()


def list():
    raise NotImplementedError()


def show(config_id):
    raise NotImplementedError()


def delete(config_id):
    raise NotImplementedError()
