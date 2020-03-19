#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import os
from paunch.builder import base
from paunch.utils import common


class PodmanBuilder(base.BaseBuilder):

    def __init__(self, config_id, config, runner, labels=None, log=None,
                 cont_log_path=None, healthcheck_disabled=False, cleanup=True):
        super(PodmanBuilder, self).__init__(config_id, config, runner,
                                            labels, log, cont_log_path,
                                            healthcheck_disabled, cleanup)

    def container_run_args(self, cmd, container, delegate=None):
        """Prepare the run command args, from the container configuration.

        :param cmd: The list of command options to be modified
        :param container: A dict with container configurations
        :param delegate: A predictable/unique name of the actual container
        :returns: True if configuration is valid, otherwise False
        """
        if delegate and container != delegate:
            self.log.debug("Container {} has a delegate "
                           "{}".format(container, delegate))
        if not delegate:
            delegate = container
        cconfig = self.config[container]

        # write out a pid file so we can restart the container delegate
        # via systemd
        cmd.append('--conmon-pidfile=/var/run/{}.pid'.format(delegate))

        if cconfig.get('detach', True):
            cmd.append('--detach=true')

        if self.cont_log_path is not None:
            if os.path.isabs(self.cont_log_path):

                if not os.path.exists(self.cont_log_path):
                    os.makedirs(self.cont_log_path)
                log_path = os.path.join(self.cont_log_path, delegate)
                logging = ['--log-driver', 'k8s-file',
                           '--log-opt', 'path=%s.log' % log_path]
                cmd.extend(logging)
            else:
                raise ValueError('cont_log_path passed but not absolute.')

        self.list_or_string_arg(cconfig, cmd, 'env_file', '--env-file')
        self.list_or_dict_arg(cconfig, cmd, 'environment', '--env')
        self.boolean_arg(cconfig, cmd, 'remove', '--rm')
        self.boolean_arg(cconfig, cmd, 'interactive', '--interactive')
        self.boolean_arg(cconfig, cmd, 'tty', '--tty')
        self.string_arg(cconfig, cmd, 'net', '--net')
        self.string_arg(cconfig, cmd, 'ipc', '--ipc')
        self.string_arg(cconfig, cmd, 'pid', '--pid')
        self.string_arg(cconfig, cmd, 'uts', '--uts')
        # TODO(sbaker): implement ulimits property, deprecate this ulimit
        # property
        for u in cconfig.get('ulimit', []):
            if u:
                cmd.append('--ulimit=%s' % u)

        self.string_arg(cconfig, cmd, 'privileged', '--privileged', self.lower)
        self.string_arg(cconfig, cmd, 'user', '--user')
        self.list_arg(cconfig, cmd, 'group_add', '--group-add')
        self.list_arg(cconfig, cmd, 'volumes', '--volume')
        self.list_arg(cconfig, cmd, 'volumes_from', '--volumes-from')
        # TODO(sbaker): deprecate log_tag, implement log_driver, log_opt
        if 'log_tag' in cconfig:
            cmd.append('--log-opt=tag=%s' % cconfig['log_tag'])
        self.string_arg(cconfig, cmd, 'cpu_shares', '--cpu-shares')
        self.string_arg(cconfig, cmd, 'mem_limit', '--memory')
        self.string_arg(cconfig, cmd, 'memswap_limit', '--memory-swap')
        self.string_arg(cconfig, cmd, 'mem_swappiness', '--memory-swappiness')
        self.string_arg(cconfig, cmd, 'security_opt', '--security-opt')
        self.string_arg(cconfig, cmd, 'stop_signal', '--stop-signal')
        self.string_arg(cconfig, cmd, 'hostname', '--hostname')
        for extra_host in cconfig.get('extra_hosts', []):
            if extra_host:
                cmd.append('--add-host=%s' % extra_host)
        if 'cpuset_cpus' in cconfig:
            # 'all' is a special value to directly configure all CPUs
            # that are available. Without specifying --cpuset-cpus, we'll
            # let the container engine to figure out what CPUs are online.
            # https://bugs.launchpad.net/tripleo/+bug/1868135
            # https://bugzilla.redhat.com/show_bug.cgi?id=1813091
            if cconfig['cpuset_cpus'] != 'all':
                cmd.append('--cpuset-cpus=%s' % cconfig['cpuset_cpus'])
        else:
            cmd.append('--cpuset-cpus=%s' % common.get_cpus_allowed_list())

        self.string_arg(cconfig, cmd,
                        'stop_grace_period', '--stop-timeout',
                        self.duration)

        self.list_arg(cconfig, cmd, 'cap_add', '--cap-add')
        self.list_arg(cconfig, cmd, 'cap_drop', '--cap-drop')
        self.string_arg(cconfig, cmd, 'check_interval', '--check-interval')

        cmd.append(cconfig.get('image', ''))
        cmd.extend(self.command_argument(cconfig.get('command')))

        return self.validate_volumes(cconfig.get('volumes', []))
