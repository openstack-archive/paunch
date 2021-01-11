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

import collections
import jmespath
import json
import os
import random
import string
import subprocess
import time

from paunch.builder import podman
from paunch.utils import common
from paunch.utils import systemctl
from paunch.utils import systemd


class BaseRunner(object):
    def __init__(self, managed_by, cont_cmd, log=None, cont_log_path=None,
                 healthcheck_disabled=False):
        self.managed_by = managed_by
        self.cont_cmd = cont_cmd
        # Leverage pre-configured logger
        self.log = log or common.configure_logging(__name__)
        self.cont_log_path = cont_log_path
        self.healthcheck_disabled = healthcheck_disabled
        if self.cont_cmd == 'docker':
            self.log.warning('docker runtime is deprecated in Stein '
                             'and will be removed in Train.')

    @staticmethod
    def execute(cmd, log=None, quiet=False, warn_only=False):
        if not log:
            log = common.configure_logging(__name__)
        if not quiet:
            log.debug('$ %s' % ' '.join(cmd))
        subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        cmd_stdout, cmd_stderr = subproc.communicate()
        if subproc.returncode != 0:
            if warn_only:
                log.warning('Error executing %s: '
                            'returned %s' % (cmd, subproc.returncode))
            else:
                log.error('Error executing %s: '
                          'returned %s' % (cmd, subproc.returncode))
        if not quiet:
            log.debug(cmd_stdout)
            log.debug(cmd_stderr)
        return (cmd_stdout.decode('utf-8'),
                cmd_stderr.decode('utf-8'),
                subproc.returncode)

    @staticmethod
    def execute_interactive(cmd, log=None):
        if not log:
            log = common.configure_logging(__name__)
        log.debug('$ %s' % ' '.join(cmd))
        return subprocess.call(cmd)

    def current_config_ids(self):
        # List all config_id labels for managed containers
        # FIXME(bogdando): remove once we have it fixed:
        # https://github.com/containers/libpod/issues/1729
        if self.cont_cmd == 'docker':
            fmt = '{{.Label "config_id"}}'
        else:
            fmt = '{{.Labels.config_id}}'
        cmd = [
            self.cont_cmd, 'ps', '-a',
            '--filter', 'label=managed_by=%s' % self.managed_by,
            '--format', fmt
        ]
        cmd_stdout, cmd_stderr, returncode = self.execute(
            cmd, log=self.log, quiet=False, warn_only=True)
        results = cmd_stdout.split()
        if returncode != 0 or not results or results == ['']:
            # NOTE(bogdando): also look by the historically used to
            # be always specified defaults, we must also identify such configs
            cmd = [
                self.cont_cmd, 'ps', '-a',
                '--filter', 'label=managed_by=paunch',
                '--format', fmt
            ]
            cmd_stdout, cmd_stderr, returncode = self.execute(cmd, self.log)
            if returncode != 0:
                return set()
            results += cmd_stdout.split()
        return set(results)

    def containers_in_config(self, conf_id):
        cmd = [
            self.cont_cmd, 'ps', '-q', '-a',
            '--filter', 'label=managed_by=%s' % self.managed_by,
            '--filter', 'label=config_id=%s' % conf_id
        ]
        cmd_stdout, cmd_stderr, returncode = self.execute(
            cmd, log=self.log, quiet=False, warn_only=True)
        results = cmd_stdout.split()
        if returncode != 0 or not results or results == ['']:
            # NOTE(bogdando): also look by the historically used to
            # be always specified defaults, we must also identify such configs
            cmd = [
                self.cont_cmd, 'ps', '-q', '-a',
                '--filter', 'label=managed_by=paunch',
                '--filter', 'label=config_id=%s' % conf_id
            ]
            cmd_stdout, cmd_stderr, returncode = self.execute(cmd, self.log)
            if returncode != 0:
                return []
            results += cmd_stdout.split()

        return [c for c in results]

    def inspect(self, name, output_format=None, o_type='container',
                quiet=False):
        # In podman, if we're being asked to inspect a container image, we
        # want to verify that the image exists before inspecting it.
        # Context: https://github.com/containers/libpod/issues/1845
        if o_type == 'image':
            if not self.image_exist(name):
                return
        cmd = [self.cont_cmd, 'inspect', '--type', o_type]
        if output_format:
            cmd.append('--format')
            cmd.append(output_format)
        cmd.append(name)
        (cmd_stdout, cmd_stderr, returncode) = self.execute(
            cmd, self.log, quiet, True)
        if returncode != 0:
            return
        try:
            if output_format:
                return cmd_stdout
            else:
                return json.loads(cmd_stdout)[0]
        except Exception as e:
            self.log.error('Problem parsing %s inspect: %s' %
                           (self.cont_cmd, e))

    def unique_container_name(self, container):
        container_name = container
        if self.cont_cmd == 'docker':
            while self.inspect(container_name, output_format='exists',
                               quiet=True):
                suffix = ''.join(random.choice(
                    string.ascii_lowercase + string.digits) for i in range(8))
                container_name = '%s-%s' % (container, suffix)
                break
        else:
            while self.container_exist(container_name, quiet=True):
                suffix = ''.join(random.choice(
                    string.ascii_lowercase + string.digits) for i in range(8))
                container_name = '%s-%s' % (container, suffix)
                break
        return container_name

    def discover_container_name(self, container, cid):
        cmd = [
            self.cont_cmd,
            'ps',
            '-a',
            '--filter',
            'label=container_name=%s' % container,
            '--filter',
            'label=config_id=%s' % cid,
            '--format',
            '{{.Names}}'
        ]
        (cmd_stdout, cmd_stderr, returncode) = self.execute(
            cmd, log=self.log, quiet=False, warn_only=True)
        if returncode == 0:
            names = cmd_stdout.split()
            if names:
                return names[0]
        self.log.warning('Did not find container with "%s" - retrying without '
                         'config_id' % cmd)

        cmd = [
            self.cont_cmd,
            'ps',
            '-a',
            '--filter',
            'label=container_name=%s' % container,
            '--format',
            '{{.Names}}'
        ]
        (cmd_stdout, cmd_stderr, returncode) = self.execute(cmd, self.log)
        if returncode == 0:
            names = cmd_stdout.split()
            if names:
                return names[0]

        self.log.warning('Did not find container with "%s"' % cmd)

    def delete_missing_configs(self, config_ids):
        if not config_ids:
            config_ids = []

        for conf_id in self.current_config_ids():
            if conf_id not in config_ids:
                self.log.debug('%s no longer exists, deleting containers' %
                               conf_id)
                self.remove_containers(conf_id)

    def discover_container_config(self, configs, container, name):
        '''Find the paunch and runtime configs of a container by name.'''
        for conf_id in self.current_config_ids():
            jquerry = ("[] | [?(Name=='%s' && "
                       "Config.Labels.container_name=='%s' && "
                       "Config.Labels.config_id=='%s')]" %
                       (container, name, conf_id))
            runtime_conf = None
            try:
                runtime_conf = jmespath.search(jquerry,
                                               configs[conf_id])[0]
                result = (conf_id, runtime_conf)
            except Exception:
                self.log.error("Failed searching container %s "
                               "for config %s" % (container, conf_id))
                result = (None, None)
            if runtime_conf:
                self.log.debug("Found container %s "
                               "for config %s" % (container, conf_id))
                break
        return result

    def list_configs(self):
        configs = collections.defaultdict(list)
        for conf_id in self.current_config_ids():
            for container in self.containers_in_config(conf_id):
                configs[conf_id].append(self.inspect(container))
        return configs

    def container_names(self, conf_id=None):
        # list every container name, and its container_name label
        # FIXME(bogdando): remove once we have it fixed:
        # https://github.com/containers/libpod/issues/1729
        if self.cont_cmd == 'docker':
            fmt = '{{.Label "container_name"}}'
        else:
            fmt = '{{.Labels.container_name}}'
        cmd = [
            self.cont_cmd, 'ps', '-a',
            '--filter', 'label=managed_by=%s' % self.managed_by
        ]
        if conf_id:
            cmd.extend((
                '--filter', 'label=config_id=%s' % conf_id
            ))
        cmd.extend((
            '--format', '{{.Names}} %s' % fmt
        ))
        cmd_stdout, cmd_stderr, returncode = self.execute(
            cmd, log=self.log, quiet=False, warn_only=True)
        results = cmd_stdout.split("\n")
        if returncode != 0 or not results or results == ['']:
            # NOTE(bogdando): also look by the historically used to
            # be always specified defaults, we must also identify such configs
            cmd = [
                self.cont_cmd, 'ps', '-a',
                '--filter', 'label=managed_by=paunch'
            ]
            if conf_id:
                cmd.extend((
                    '--filter', 'label=config_id=%s' % conf_id
                ))
            cmd.extend((
                '--format', '{{.Names}} %s' % fmt
            ))
            cmd_stdout, cmd_stderr, returncode = self.execute(cmd, self.log)
            if returncode != 0:
                return []
            results += cmd_stdout.split("\n")
        result = []
        for line in results:
            if line:
                result.append(line.split())
        return result

    def remove_containers(self, conf_id):
        for container in self.containers_in_config(conf_id):
            self.remove_container(container)

    def remove_container(self, container):
        self.execute([self.cont_cmd, 'stop', container], self.log)
        cmd = [self.cont_cmd, 'rm', container]
        cmd_stdout, cmd_stderr, returncode = self.execute(cmd, self.log)
        if returncode != 0:
            self.log.error('Error removing container '
                           'gracefully: %s' % container)
            self.log.error(cmd_stderr)
            cmd = [self.cont_cmd, 'rm', '-f', container]
            cmd_stdout, cmd_stderr, returncode = self.execute(cmd, self.log)
            if returncode != 0:
                self.log.error('Error removing container: %s' % container)
                self.log.error(cmd_stderr)
                raise Exception('Unable to remove container: %s' % container)

    def stop_container(self, container, cont_cmd=None, quiet=False):
        cont_cmd = cont_cmd or self.cont_cmd
        cmd = [cont_cmd, 'stop', container]
        cmd_stdout, cmd_stderr, returncode = self.execute(cmd, quiet=quiet)
        if returncode != 0 and not quiet:
            self.log.error('Error stopping container: %s' % container)
            self.log.error(cmd_stderr)
            raise Exception('Unable to stop container: %s' % container)

    def rename_containers(self):
        current_containers = []
        need_renaming = {}
        renamed = False
        for entry in self.container_names():
            current_containers.append(entry[0])

            # ignore if container_name label not set
            if len(entry) < 2:
                continue

            # ignore if desired name is already actual name
            if entry[0] == entry[-1]:
                continue

            need_renaming[entry[0]] = entry[-1]

        for current, desired in sorted(need_renaming.items()):
            if desired in current_containers:
                self.log.info('Cannot rename "%s" since "%s" still exists' % (
                    current, desired))
            else:
                self.log.info('Renaming "%s" to "%s"' % (current, desired))
                self.rename_container(current, desired)
                renamed = True
                current_containers.append(desired)
        return renamed

    def validate_volume_source(self, volume):
        """Validate that the provided volume

        This checks that the provided volume either exists on the filesystem
        or is a container volume.

        :param: volume: string containing either a filesystme path or container
                        volume name
        """
        if os.path.exists(volume):
            return True

        if os.path.sep in volume:
            # if we get here and have a path seperator, let's skip the
            # container lookup because container volumes won't have / in them.
            self.log.debug('Path seperator found in volume (%s), but did not '
                           'exist on the file system' % volume)
            return False

        self.log.debug('Running volume lookup for "%s"' % volume)
        filter_opt = '--filter=name={}'.format(volume)
        cmd = [self.cont_cmd, 'volume', 'ls', '-q', filter_opt]
        cmd_stdout, cmd_stderr, returncode = self.execute(cmd)
        if returncode != 0:
            self.log.error('Error during volume verification')
            self.log.error(cmd_stderr)
            return False
        return (volume in set(cmd_stdout.split()))


class DockerRunner(BaseRunner):

    def __init__(self, managed_by, cont_cmd=None, log=None):
        cont_cmd = cont_cmd or 'docker'
        super(DockerRunner, self).__init__(managed_by, cont_cmd, log)

    def rename_container(self, container, name):
        cmd = [self.cont_cmd, 'rename', container, name]
        cmd_stdout, cmd_stderr, returncode = self.execute(cmd, self.log)
        if returncode != 0:
            self.log.error('Error renaming container: %s' % container)
            self.log.error(cmd_stderr)

    def image_exist(self, name, quiet=False):
        self.log.warning("image_exist isn't supported "
                         "by %s" % self.cont_cmd)
        return True

    def container_exist(self, name, quiet=False):
        self.log.warning("container_exist isn't supported "
                         "by %s" % self.cont_cmd)
        return True

    def container_running(self, container):
        self.log.warning("container_running isn't supported "
                         "by %s" % self.cont_cmd)
        return True


class PodmanRunner(BaseRunner):

    def __init__(self, managed_by, cont_cmd=None, log=None,
                 cont_log_path=None, healthcheck_disabled=False):
        cont_cmd = cont_cmd or 'podman'
        super(PodmanRunner, self).__init__(managed_by, cont_cmd, log,
                                           cont_log_path, healthcheck_disabled)

    def rename_container(self, container, name):
        # TODO(emilien) podman doesn't support rename, we'll handle it
        # in paunch itself for now
        configs = self.list_configs()
        config_id, config = self.discover_container_config(
            configs, container, name)
        # Get config_data dict by the discovered conf ID,
        # paunch needs it for maintaining idempotency within a conf ID
        filter_names = ("[] | [?(Name!='%s' && "
                        "Config.Labels.config_id=='%s')]"
                        ".Name" % (container, config_id))
        filter_cdata = ("[] | [?(Name!='%s' && "
                        "Config.Labels.config_id=='%s')]"
                        ".Config.Labels.config_data" % (container, config_id))
        names = None
        cdata = None
        try:
            names = jmespath.search(filter_names, configs[config_id])
            cdata = jmespath.search(filter_cdata, configs[config_id])
        except jmespath.exceptions.LexerError:
            self.log.error("Failed to rename a container %s into %s: "
                           "used a bad search pattern" % (container, name))
            return

        if not names or not cdata:
            self.log.error("Failed to rename a container %s into %s: "
                           "no config_data was found" % (container, name))
            return

        # Rename the wanted container in the config_data fetched from the
        # discovered config
        config_data = dict(zip(names, map(json.loads, cdata)))
        config_data[name] = json.loads(
            config.get('Config').get('Labels').get('config_data'))

        # Re-apply a container under its amended name using the fetched configs
        self.log.debug("Renaming a container known as %s into %s, "
                       "via re-applying its original config" %
                       (container, name))
        # destination container
        self.stop_container(name)
        self.remove_container(name)
        self.stop_container(container)
        self.remove_container(container)
        builder = podman.PodmanBuilder(
            config_id=config_id,
            config=config_data,
            runner=self,
            labels=None,
            log=self.log,
            cont_log_path=self.cont_log_path,
            healthcheck_disabled=self.healthcheck_disabled
        )
        builder.apply()

    def stop_container(self, container, cont_cmd=None, quiet=False):
        if not self.container_running(container):
            self.log.debug('%s not running, skipping stop' % container)
            return
        self.log.debug("Stopping container: %s" % container)
        return super(PodmanRunner, self).stop_container(container,
                                                        cont_cmd,
                                                        quiet)

    def remove_container(self, container):
        if not self.container_exist(container):
            self.log.debug('%s does not exist, skipping remove' % container)
            return
        self.log.debug("Removing container: %s" % container)
        systemd.service_delete(container=container, log=self.log)
        return super(PodmanRunner, self).remove_container(container)

    def image_exist(self, name, quiet=False):
        cmd = ['podman', 'image', 'exists', name]
        (_, _, returncode) = self.execute(cmd, self.log, quiet, True)
        return returncode == 0

    def container_exist(self, name, quiet=False):
        cmd = ['podman', 'container', 'exists', name]
        (_, _, returncode) = self.execute(cmd, self.log, quiet, True)
        return returncode == 0

    def container_running(self, container):
        if not self.container_exist(container):
            self.log.debug('%s is not running because it does not exist' %
                           container)
            return False
        service_name = 'tripleo_' + container + '.service'
        try:
            systemctl.is_active(service_name)
            self.log.debug('Unit %s is running' % service_name)
            return True
        except systemctl.SystemctlException:
            chk_cmd = [
                self.cont_cmd,
                'ps',
                '--filter',
                'label=container_name=%s' % container,
                '--format',
                '{{.Names}}'
            ]
            cmd_stdout = ''
            returncode = -1
            count = 1
            while (not cmd_stdout or returncode != 0) and count <= 5:
                self.log.warning('Attempt %i to check if %s is '
                                 'running' % (count, container))
                # at the first retry, we will force a sync with the OCI runtime
                if self.cont_cmd == 'podman' and count == 2:
                    chk_cmd.append('--sync')
                (cmd_stdout, cmd_stderr, returncode) = self.execute(
                    chk_cmd, log=self.log, quiet=False, warn_only=True)

                if returncode != 0:
                    self.log.warning('Attempt %i Error when running '
                                     '%s:' % (count, chk_cmd))
                    self.log.warning(cmd_stderr)
                else:
                    if not cmd_stdout:
                        self.log.warning('Attempt %i Container %s '
                                         'is not running' % (count, container))

                count += 1
                time.sleep(0.2)
            # return True if ps ran successfuly and returned a container name.
            return (cmd_stdout and returncode == 0)
