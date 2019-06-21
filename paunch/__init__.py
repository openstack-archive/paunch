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
import pbr.version
import yaml

from paunch.builder import compose1
from paunch.builder import podman
from paunch import runner
from paunch.utils import common

__version__ = pbr.version.VersionInfo('paunch').version_string()


def apply(config_id, config, managed_by, labels=None, cont_cmd='podman',
          default_runtime=None, log_level=None, log_file=None,
          cont_log_path=None, healthcheck_disabled=False):
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
    :param str cont_cmd: Optional override to the container command to run.
    :param str default_runtime: (deprecated) does nothing.
    :param int log_level: optional log level for loggers
    :param str log_file: optional log file for messages
    :param str cont_log_path: optional log path for containers. Works only for
                              podman engine. Must be an absolute path.
    :param bool healthcheck_disabled: optional boolean to disable container
                                      healthcheck.

    :returns (list, list, int) lists of stdout and stderr for each execution,
                               and a single return code representing the
                               overall success of the apply.
    :rtype: tuple
    """
    log = common.configure_logging(__name__, log_level, log_file)
    if default_runtime:
        log.warning("DEPRECATION: 'default_runtime' does nothing, "
                    "use 'cont_cmd' instead")

    if cont_cmd == 'podman':
        r = runner.PodmanRunner(managed_by, cont_cmd=cont_cmd, log=log)
        builder = podman.PodmanBuilder(
            config_id=config_id,
            config=config,
            runner=r,
            labels=labels,
            log=log,
            cont_log_path=cont_log_path,
            healthcheck_disabled=healthcheck_disabled
        )
    else:
        r = runner.DockerRunner(managed_by, cont_cmd=cont_cmd, log=log)
        builder = compose1.ComposeV1Builder(
            config_id=config_id,
            config=config,
            runner=r,
            labels=labels,
            log=log
        )
    return builder.apply()


def cleanup(config_ids, managed_by, cont_cmd='podman', default_runtime=None,
            log_level=None, log_file=None):
    """Delete containers no longer applied, rename others to preferred name.

    :param list config_ids: List of config IDs still applied. All containers
                            managed by this tool will be deleted if their
                            config ID is not specified in this list.
    :param str managed_by: Name of the tool managing the containers. Only
                           containers labelled with this will be modified.
    :param str cont_cmd: Optional override to the container command to run.
    :param str default_runtime: (deprecated) does nothing.
    :param int log_level: optional log level for loggers
    :param int log_file: optional log file for messages
    """
    log = common.configure_logging(__name__, log_level, log_file)
    if default_runtime:
        log.warning("DEPRECATION: 'default_runtime' does nothing, "
                    "use 'cont_cmd' instead")

    if cont_cmd == 'podman':
        r = runner.PodmanRunner(managed_by, cont_cmd=cont_cmd, log=log)
        log.warning("paunch cleanup is partially supported with podman")
    else:
        r = runner.DockerRunner(managed_by, cont_cmd=cont_cmd, log=log)

    r.delete_missing_configs(config_ids)
    r.rename_containers()


def list(managed_by, cont_cmd='podman', default_runtime=None,
         log_level=None, log_file=None):
    """List all containers associated with all config IDs.

    :param str managed_by: Name of the tool managing the containers. Only
                           containers labelled with this will be modified.
    :param str cont_cmd: Optional override to the container command to run.
    :param str default_runtime: (deprecated) does nothing.
    :param int log_level: optional log level for loggers
    :param int log_file: optional log file for messages

    :returns a dict where the key is the config ID and the value is a list of
             'podman inspect' dicts for each container.
    :rtype: defaultdict(list)
    """
    log = common.configure_logging(__name__, log_level, log_file)
    if default_runtime:
        log.warning("DEPRECATION: 'default_runtime' does nothing, "
                    "use 'cont_cmd' instead")

    if cont_cmd == 'podman':
        r = runner.PodmanRunner(managed_by, cont_cmd=cont_cmd, log=log)
    else:
        r = runner.DockerRunner(managed_by, cont_cmd=cont_cmd, log=log)

    return r.list_configs()


def debug(config_id, container_name, action, config, managed_by, labels=None,
          cont_cmd='podman', default_runtime=None, log_level=None,
          log_file=None):
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
    :param str cont_cmd: Optional override to the container command to run.
    :param str default_runtime: (deprecated) does nothing.
    :param int log_level: optional log level for loggers
    :param int log_file: optional log file for messages

    :returns integer return value from running command or failure for any
             other reason.
    :rtype: int
    """
    log = common.configure_logging(__name__, log_level, log_file)
    if default_runtime:
        log.warning("DEPRECATION: 'default_runtime' does nothing, "
                    "use 'cont_cmd' instead")

    if cont_cmd == 'podman':
        r = runner.PodmanRunner(managed_by, cont_cmd=cont_cmd, log=log)
        builder = podman.PodmanBuilder(
            config_id=config_id,
            config=config,
            runner=r,
            labels=labels,
            log=log
        )
    else:
        r = runner.DockerRunner(managed_by, cont_cmd=cont_cmd, log=log)
        builder = compose1.ComposeV1Builder(
            config_id=config_id,
            config=config,
            runner=r,
            labels=labels,
            log=log
        )
    if action == 'print-cmd':
        cmd = [
            r.cont_cmd,
            'run',
            '--name',
            r.unique_container_name(container_name)
        ]
        builder.container_run_args(cmd, container_name)

        if '--health-cmd' in cmd:
            health_check_arg_index = cmd.index('--health-cmd') + 1

            # The argument given needs to be quoted to work properly with a
            # copy and paste of the full command.
            try:
                cmd[health_check_arg_index] = (
                    '"%s"' % cmd[health_check_arg_index])
            except IndexError:
                log.warning("No argument provided to --health-cmd.")

        print(' '.join(cmd))
    elif action == 'run':
        cmd = [
            r.cont_cmd,
            'run',
            '--name',
            r.unique_container_name(container_name)
        ]
        builder.container_run_args(cmd, container_name)
        return r.execute_interactive(cmd, log)
    elif action == 'dump-yaml':
        print(yaml.safe_dump(config, default_flow_style=False))
    elif action == 'dump-json':
        print(json.dumps(config, indent=4))
    else:
        raise ValueError('action should be one of: "dump-json", "dump-yaml"',
                         '"print-cmd", or "run"')


def delete(config_ids, managed_by, cont_cmd='podman', default_runtime=None,
           log_level=None, log_file=None):
    """Delete containers with the specified config IDs.

    :param list config_ids: List of config IDs to delete the containers for.
    :param str managed_by: Name of the tool managing the containers. Only
                           containers labelled with this will be modified.
    :param str cont_cmd: Optional override to the container command to run.
    :param str default_runtime: (deprecated) does nothing.
    """
    log = common.configure_logging(__name__, log_level, log_file)
    if default_runtime:
        log.warning("DEPRECATION: 'default_runtime' does nothing, "
                    "use 'cont_cmd' instead")

    if not config_ids:
        log.warn('No config IDs specified')

    if cont_cmd == 'podman':
        r = runner.PodmanRunner(managed_by, cont_cmd=cont_cmd, log=log)
        log.warning("paunch cleanup is partially supported with podman")
    else:
        r = runner.DockerRunner(managed_by, cont_cmd=cont_cmd, log=log)

    for conf_id in config_ids:
        r.remove_containers(conf_id)
