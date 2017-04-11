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


def apply(config_id, config, managed_by, labels=None, docker_cmd=None):
    """Execute supplied container configuration.

    :param str config_id: Unique config ID, should not be re-used until any
                          running containers with that config ID have been
                          deleted.
    :param dict config: Configuration data describing container actions to
                        apply.
    :param str managed_by: Name of the tool managing the containers. Only
                           containers labelled with this will be modified.
    :param dict labels: Optional keys/values of labels to apply to containers
                        created with this invocation.
    :param str docker_cmd: Optional override to the docker command to run.

    :returns (list, list, int) lists of stdout and stderr for each execution,
                               and a single return code representing the
                               overall success of the apply.
    :rtype: tuple
    """
    r = runner.DockerRunner(managed_by, docker_cmd=docker_cmd)
    builder = compose1.ComposeV1Builder(
        config_id=config_id,
        config=config,
        runner=r,
        labels=labels
    )
    return builder.apply()


def cleanup(config_ids, managed_by, docker_cmd=None):
    """Delete containers no longer applied, rename others to preferred name.

    :param list config_ids: List of config IDs still applied. All containers
                            managed by this tool will be deleted if their
                            config ID is not specified in this list.
    :param str managed_by: Name of the tool managing the containers. Only
                           containers labelled with this will be modified.
    :param str docker_cmd: Optional override to the docker command to run.
    """
    r = runner.DockerRunner(managed_by, docker_cmd=docker_cmd)
    r.delete_missing_configs(config_ids)
    r.rename_containers()


def list(managed_by, docker_cmd=None):
    raise NotImplementedError()


def show(config_id, managed_by, docker_cmd=None):
    raise NotImplementedError()


def delete(config_id, managed_by, docker_cmd=None):
    raise NotImplementedError()
