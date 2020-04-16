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

import distutils.spawn
import itertools
import json
import os
import re
import shutil
import tenacity
import yaml

from paunch.utils import common
from paunch.utils import systemd


class BaseBuilder(object):

    def __init__(self, config_id, config, runner, labels, log=None,
                 cont_log_path=None, healthcheck_disabled=False, cleanup=True):
        self.config_id = config_id
        self.config = config
        self.labels = labels
        self.runner = runner
        # Leverage pre-configured logger
        self.log = log or common.configure_logging(__name__)
        self.cont_log_path = cont_log_path
        self.healthcheck_disabled = healthcheck_disabled
        self.cleanup = cleanup

        if os.path.isfile('/var/lib/tripleo-config/.ansible-managed'):
            msg = ('Containers were previously deployed with '
                   'tripleo-ansible, paunch CLI can not be used.')
            raise RuntimeError(msg)

        self.log.warning('Paunch is deprecated and has been replaced by '
                         'tripleo_container_manage role in tripleo-ansible.')

    def apply(self):

        stdout = []
        stderr = []
        pull_returncode = self.pull_missing_images(stdout, stderr)
        if pull_returncode != 0:
            return stdout, stderr, pull_returncode

        deploy_status_code = 0
        key_fltr = lambda k: self.config[k].get('start_order', 0)

        failed_containers = []
        container_names = self.runner.container_names(self.config_id)

        # Cleanup containers missing from the config.
        # Also applying new containers configs is an opportunity for
        # renames to their preferred names.
        changed = self.delete_missing(container_names)
        changed |= self.runner.rename_containers()
        if changed:
            # If anything has been changed, refresh the container_names
            container_names = self.runner.container_names(self.config_id)
        desired_names = set([cn[-1] for cn in container_names])

        for container in sorted(self.config, key=key_fltr):
            # Before creating the container, figure out if it needs to be
            # removed because of its configuration has changed.
            # If anything has been deleted, refresh the container_names/desired
            if self.delete_updated(container, container_names):
                container_names = self.runner.container_names(self.config_id)
                desired_names = set([cn[-1] for cn in container_names])

            self.log.debug("Running container: %s" % container)
            cconfig = self.config[container]
            action = cconfig.get('action', 'run')
            restart = cconfig.get('restart', 'none')
            exit_codes = cconfig.get('exit_codes', [0])
            container_name = self.runner.unique_container_name(container)
            systemd_managed = (restart != 'none'
                               and self.runner.cont_cmd == 'podman'
                               and action == 'run')
            start_cmd = 'create' if systemd_managed else 'run'

            # When upgrading from Docker to Podman, we want to stop the
            # container that runs under Docker first before starting it with
            # Podman. The container will be removed later in THT during
            # upgrade_tasks.
            if self.runner.cont_cmd == 'podman' and \
                    os.path.exists('/var/run/docker.sock'):
                self.runner.stop_container(container, 'docker', quiet=True)

            if action == 'run':
                if container in desired_names:
                    self.log.debug('Skipping existing container: %s' %
                                   container)
                    continue

                c_name = self.runner.discover_container_name(
                    container, self.config_id) or container
                cmd = [
                    self.runner.cont_cmd,
                    start_cmd,
                    '--name',
                    c_name
                ]

                self.label_arguments(cmd, container)
                self.log.debug("Start container {} as {}.".format(container,
                                                                  c_name))
                validations_passed = self.container_run_args(
                    cmd, container, c_name)
            elif action == 'exec':
                # for exec, the first argument is the fixed named container
                # used when running the command into the running container.
                # use the discovered container name to manipulate with the
                # real (delagate) container representing the fixed named one
                command = self.command_argument(cconfig.get('command'))
                if command:
                    c_name = self.runner.discover_container_name(
                        command[0], self.config_id)
                else:
                    c_name = self.runner.discover_container_name(
                        container, self.config_id)
                # Before running the exec, we want to make sure the container
                # is running.
                # https://bugs.launchpad.net/bugs/1839559
                if not c_name or not self.runner.container_running(c_name):
                    msg = ('Failing to apply action exec for '
                           'container: %s' % container)
                    raise RuntimeError(msg)
                cmd = [self.runner.cont_cmd, 'exec']
                validations_passed = self.cont_exec_args(cmd,
                                                         container,
                                                         c_name)

            if not validations_passed:
                self.log.debug('Validations failed. Skipping container: %s' %
                               container)
                failed_containers.append(container)
                continue

            (cmd_stdout, cmd_stderr, returncode) = self.runner.execute(
                cmd, self.log)
            if cmd_stdout:
                stdout.append(cmd_stdout)
            if cmd_stderr:
                stderr.append(cmd_stderr)

            if returncode not in exit_codes:
                self.log.error("Error running %s. [%s]\n" % (cmd, returncode))
                self.log.error("stdout: %s" % cmd_stdout)
                self.log.error("stderr: %s" % cmd_stderr)
                deploy_status_code = returncode
            else:
                self.log.debug('Completed $ %s' % ' '.join(cmd))
                self.log.info("stdout: %s" % cmd_stdout)
                self.log.info("stderr: %s" % cmd_stderr)
                if systemd_managed:
                    systemd.service_create(container=container_name,
                                           cconfig=cconfig,
                                           log=self.log)
                    if (not self.healthcheck_disabled and
                            'healthcheck' in cconfig):
                        check = cconfig.get('healthcheck')['test']
                        systemd.healthcheck_create(container=container_name,
                                                   log=self.log, test=check)
                        systemd.healthcheck_timer_create(
                            container=container_name,
                            cconfig=cconfig,
                            log=self.log)

        if failed_containers:
            message = (
                "The following containers failed validations "
                "and were not started: {}".format(
                    ', '.join(failed_containers)))
            self.log.error(message)
            # The message is also added to stderr so that it's returned and
            # logged by the paunch module for ansible
            stderr.append(message)
            deploy_status_code = 1

        return stdout, stderr, deploy_status_code

    def delete_missing(self, container_names):
        deleted = False
        for cn in container_names:
            container = cn[0]
            # if the desired name is not in the config, delete it
            if cn[-1] not in self.config:
                if self.cleanup:
                    self.log.debug("Deleting container (removed): "
                                   "%s" % container)
                    self.runner.remove_container(container)
                    deleted = True
                else:
                    self.log.debug("Skipping container (cleanup disabled): "
                                   "%s" % container)
        return deleted

    def delete_updated(self, container, container_names):
        # If a container is not deployed, there is nothing to delete
        if (container not in
           list(itertools.chain.from_iterable(container_names))):
            return False

        ex_data_str = self.runner.inspect(
            container, '{{index .Config.Labels "config_data"}}')
        if not ex_data_str:
            if self.cleanup:
                self.log.debug("Deleting container (no_config_data): "
                               "%s" % container)
                self.runner.remove_container(container)
                return True
            else:
                self.log.debug("Skipping container (cleanup disabled): "
                               "%s" % container)

        try:
            ex_data = yaml.safe_load(str(ex_data_str))
        except Exception:
            ex_data = None

        new_data = self.config[container]
        if new_data != ex_data:
            self.log.debug("Deleting container (changed config_data): %s"
                           % container)
            self.runner.remove_container(container)
            return True
        return False

    def label_arguments(self, cmd, container):
        if self.labels:
            for i, v in self.labels.items():
                cmd.extend(['--label', '%s=%s' % (i, v)])
        cmd.extend([
            '--label',
            'config_id=%s' % self.config_id,
            '--label',
            'container_name=%s' % container,
            '--label',
            'managed_by=%s' % self.runner.managed_by,
            '--label',
            'config_data=%s' % json.dumps(self.config.get(container))
        ])

    def boolean_arg(self, cconfig, cmd, key, arg):
        if cconfig.get(key, False):
            cmd.append(arg)

    def string_arg(self, cconfig, cmd, key, arg, transform=None):
        if key in cconfig:
            if transform:
                value = transform(cconfig[key])
            else:
                value = cconfig[key]
            cmd.append('%s=%s' % (arg, value))

    def list_or_string_arg(self, cconfig, cmd, key, arg):
        if key not in cconfig:
            return
        value = cconfig[key]
        if not isinstance(value, list):
            value = [value]
        for v in value:
            if v:
                cmd.append('%s=%s' % (arg, v))

    def list_arg(self, cconfig, cmd, key, arg):
        if key not in cconfig:
            return
        value = cconfig[key]
        for v in value:
            if v:
                cmd.append('%s=%s' % (arg, v))

    def list_or_dict_arg(self, cconfig, cmd, key, arg):
        if key not in cconfig:
            return
        value = cconfig[key]
        if isinstance(value, dict):
            for k, v in sorted(value.items()):
                if v:
                    cmd.append('%s=%s=%s' % (arg, k, v))
                elif k:
                    cmd.append('%s=%s' % (arg, k))
        elif isinstance(value, list):
            for v in value:
                if v:
                    cmd.append('%s=%s' % (arg, v))

    def cont_exec_args(self, cmd, container, delegate=None):
        """Prepare the exec command args, from the container configuration.

        :param cmd: The list of command options to be modified
        :param container: A dict with container configurations
        :param delegate: A predictable/unique name of the actual container
        :returns: True if configuration is valid, otherwise False
        """
        if delegate and container != delegate:
            self.log.debug("Container {} has a delegate "
                           "{}".format(container, delegate))
        cconfig = self.config[container]
        if 'privileged' in cconfig:
            cmd.append('--privileged=%s' % str(cconfig['privileged']).lower())
        if 'user' in cconfig:
            cmd.append('--user=%s' % cconfig['user'])
        self.list_or_dict_arg(cconfig, cmd, 'environment', '--env')
        command = self.command_argument(cconfig.get('command'))
        # for exec, the first argument is the container name,
        # make sure the correct one is used
        if command:
            if not delegate:
                command[0] = self.runner.discover_container_name(
                    command[0], self.config_id)
            else:
                command[0] = delegate
        cmd.extend(command)

        return True

    def pull_missing_images(self, stdout, stderr):
        images = set()
        for container in self.config:
            cconfig = self.config[container]
            image = cconfig.get('image')
            if image:
                images.add(image)

        returncode = 0

        for image in sorted(images):

            # only pull if the image does not exist locally
            if self.runner.cont_cmd == 'docker':
                if self.runner.inspect(image,
                                       output_format='exists',
                                       o_type='image'):
                    continue
            else:
                img_exist = self.runner.image_exist(image)
                if img_exist:
                    continue

            try:
                (cmd_stdout, cmd_stderr) = self._pull(image)
            except PullException as e:
                returncode = e.rc
                cmd_stdout = e.stdout
                cmd_stderr = e.stderr
                self.log.error("Error pulling %s. [%s]\n" %
                               (image, returncode))
                self.log.error("stdout: %s" % e.stdout)
                self.log.error("stderr: %s" % e.stderr)
            else:
                self.log.debug('Pulled %s' % image)
                self.log.info("stdout: %s" % cmd_stdout)
                self.log.info("stderr: %s" % cmd_stderr)

            if cmd_stdout:
                stdout.append(cmd_stdout)
            if cmd_stderr:
                stderr.append(cmd_stderr)

        return returncode

    @tenacity.retry(  # Retry up to 4 times with jittered exponential backoff
        reraise=True,
        wait=tenacity.wait_random_exponential(multiplier=1, max=10),
        stop=tenacity.stop_after_attempt(4)
    )
    def _pull(self, image):
        cmd = [self.runner.cont_cmd, 'pull', image]
        (stdout, stderr, rc) = self.runner.execute(cmd, self.log)
        if rc != 0:
            raise PullException(stdout, stderr, rc)
        return stdout, stderr

    @staticmethod
    def command_argument(command):
        if not command:
            return []
        if not isinstance(command, list):
            return command.split()
        return command

    def lower(self, a):
        return str(a).lower()

    def which(self, program):
        try:
            pgm = shutil.which(program)
        except AttributeError:
            pgm = distutils.spawn.find_executable(program)
        return pgm

    def duration(self, a):
        if isinstance(a, (int, float)):
            return a

        # match groups of the format 5h34m56s
        m = re.match('^'
                     '(([\d\.]+)h)?'
                     '(([\d\.]+)m)?'
                     '(([\d\.]+)s)?'
                     '(([\d\.]+)ms)?'
                     '(([\d\.]+)us)?'
                     '$', a)

        if not m:
            # fallback to parsing string as a number
            return float(a)

        n = 0.0
        if m.group(2):
            n += 3600 * float(m.group(2))
        if m.group(4):
            n += 60 * float(m.group(4))
        if m.group(6):
            n += float(m.group(6))
        if m.group(8):
            n += float(m.group(8)) / 1000.0
        if m.group(10):
            n += float(m.group(10)) / 1000000.0
        return n

    def validate_volumes(self, volumes):
        """Validate volume sources

        Validates that the source volume either exists on the filesystem
        or is a valid container volume.  Since podman will error if the
        source volume filesystem path doesn't exist, we want to catch the
        error before podman.

        :param: volumes: list of volume mounts in the format of "src:path"
        """
        valid = True
        for volume in volumes:
            if not volume:
                # ignore when volume is ''
                continue
            src_path = volume.split(':', 1)[0]
            check = self.runner.validate_volume_source(src_path)
            if not check:
                self.log.error("%s is not a valid volume source" % src_path)
                valid = False
        return valid


class PullException(Exception):

    def __init__(self, stdout, stderr, rc):
        self.stdout = stdout
        self.stderr = stderr
        self.rc = rc
