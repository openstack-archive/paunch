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

import json
import logging
import pbr.version
import yaml

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
    """List all containers associated with all config IDs.

    :returns a dict where the key is the config ID and the value is a list of
             'docker inspect' dicts for each container.
    :rtype: defaultdict(list)
    """
    r = runner.DockerRunner(managed_by, docker_cmd=docker_cmd)
    return r.list_configs()


def debug(config_id, container_name, action, config, managed_by, labels=None,
          docker_cmd=None):
    """Execute supplied container configuration.

    :param str config_id: Unique config ID, should not be re-used until any
                          running containers with that config ID have been
                          deleted.
    :param str container_name: Name of the container in the config you
                               wish to manipulate.
    :param str action: Action to take.
    :param dict config: Configuration data describing container actions to
                        apply.
    :param str managed_by: Name of the tool managing the containers. Only
                           containers labeled with this will be modified.
    :param dict labels: Optional keys/values of labels to apply to containers
                        created with this invocation.
    :param str docker_cmd: Optional override to the docker command to run.

    :returns integer return value from running command or failure for any
             other reason.
    :rtype: int
    """

    r = runner.DockerRunner(managed_by, docker_cmd=docker_cmd)
    builder = compose1.ComposeV1Builder(
        config_id=config_id,
        config=config,
        runner=r,
        labels=labels
    )
    if action == 'print-cmd':
        cmd = [
            r.docker_cmd,
            'run',
            '--name',
            r.unique_container_name(container_name)
        ]
        builder.docker_run_args(cmd, container_name)
        print(' '.join(cmd))
    elif action == 'run':
        cmd = [
            r.docker_cmd,
            'run',
            '--name',
            r.unique_container_name(container_name)
        ]
        builder.docker_run_args(cmd, container_name)
        return r.execute_interactive(cmd)
    elif action == 'dump-yaml':
        print(yaml.safe_dump(config, default_flow_style=False))
    elif action == 'dump-json':
        print(json.dumps(config, indent=4))
    else:
        raise ValueError('action should be one of: "dump-json", "dump-yaml"',
                         '"print-cmd", or "run"')


def delete(config_ids, managed_by, docker_cmd=None):
    """Delete containers with the specified config IDs.

    :param list config_ids: List of config IDs to delete the containers for.
    :param str managed_by: Name of the tool managing the containers. Only
                           containers labelled with this will be modified.
    :param str docker_cmd: Optional override to the docker command to run.
    """
    if not config_ids:
        LOG.warn('No config IDs specified')

    r = runner.DockerRunner(managed_by, docker_cmd=docker_cmd)
    for conf_id in config_ids:
        r.remove_containers(conf_id)
