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
import json
import re
import shutil
import tenacity
import yaml

from paunch.utils import common
from paunch.utils import systemd


class BaseBuilder(object):

    def __init__(self, config_id, config, runner, labels, log=None,
                 cont_log_path=None, healthcheck_disabled=False):
        self.config_id = config_id
        self.config = config
        self.labels = labels
        self.runner = runner
        # Leverage pre-configured logger
        self.log = log or common.configure_logging(__name__)
        self.cont_log_path = cont_log_path
        self.healthcheck_disabled = healthcheck_disabled

    def apply(self):

        stdout = []
        stderr = []
        pull_returncode = self.pull_missing_images(stdout, stderr)
        if pull_returncode != 0:
            return stdout, stderr, pull_returncode

        self.delete_missing_and_updated()

        deploy_status_code = 0
        key_fltr = lambda k: self.config[k].get('start_order', 0)

        container_names = self.runner.container_names(self.config_id)
        desired_names = set([cn[-1] for cn in container_names])

        for container in sorted(self.config, key=key_fltr):
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
            if self.runner.cont_cmd == 'podman' and self.which('docker'):
                self.runner.stop_container(container, 'docker', quiet=True)

            if action == 'run':
                if container in desired_names:
                    self.log.debug('Skipping existing container: %s' %
                                   container)
                    continue

                cmd = [
                    self.runner.cont_cmd,
                    start_cmd,
                    '--name',
                    container_name
                ]

                self.label_arguments(cmd, container)
                self.container_run_args(cmd, container)
            elif action == 'exec':
                cmd = [self.runner.cont_cmd, 'exec']
                self.cont_exec_args(cmd, container)

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
        return stdout, stderr, deploy_status_code

    def delete_missing_and_updated(self):
        container_names = self.runner.container_names(self.config_id)
        for cn in container_names:
            container = cn[0]

            # if the desired name is not in the config, delete it
            if cn[-1] not in self.config:
                self.log.debug("Deleting container (removed): %s" % container)
                self.runner.remove_container(container)
                continue

            ex_data_str = self.runner.inspect(
                container, '{{index .Config.Labels "config_data"}}')
            if not ex_data_str:
                self.log.debug("Deleting container (no config_data): %s"
                               % container)
                self.runner.remove_container(container)
                continue

            try:
                ex_data = yaml.safe_load(str(ex_data_str))
            except Exception:
                ex_data = None

            new_data = self.config.get(cn[-1])
            if new_data != ex_data:
                self.log.debug("Deleting container (changed config_data): %s"
                               % container)
                self.runner.remove_container(container)

        # deleting containers is an opportunity for renames to their
        # preferred name
        self.runner.rename_containers()

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

    def cont_exec_args(self, cmd, container):
        cconfig = self.config[container]
        if 'privileged' in cconfig:
            cmd.append('--privileged=%s' % str(cconfig['privileged']).lower())
        if 'user' in cconfig:
            cmd.append('--user=%s' % cconfig['user'])
        command = self.command_argument(cconfig.get('command'))
        # for exec, the first argument is the container name,
        # make sure the correct one is used
        if command:
            command[0] = self.runner.discover_container_name(
                command[0], self.config_id)
        cmd.extend(command)

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
            if self.runner.inspect(image,
                                   output_format='exists',
                                   o_type='image'):
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


class PullException(Exception):

    def __init__(self, stdout, stderr, rc):
        self.stdout = stdout
        self.stderr = stderr
        self.rc = rc
