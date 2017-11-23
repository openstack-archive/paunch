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

import json
import logging

LOG = logging.getLogger(__name__)


class ComposeV1Builder(object):

    def __init__(self, config_id, config, runner, labels=None):
        self.config_id = config_id
        self.config = config
        self.labels = labels
        self.runner = runner

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
            LOG.debug("Running container: %s" % container)
            action = self.config[container].get('action', 'run')
            exit_codes = self.config[container].get('exit_codes', [0])

            if action == 'run':
                if container in desired_names:
                    LOG.debug('Skipping existing container: %s' % container)
                    continue

                cmd = [
                    self.runner.docker_cmd,
                    'run',
                    '--name',
                    self.runner.unique_container_name(container)
                ]
                self.label_arguments(cmd, container)
                self.docker_run_args(cmd, container)
            elif action == 'exec':
                cmd = [self.runner.docker_cmd, 'exec']
                self.docker_exec_args(cmd, container)

            (cmd_stdout, cmd_stderr, returncode) = self.runner.execute(cmd)
            if cmd_stdout:
                stdout.append(cmd_stdout)
            if cmd_stderr:
                stderr.append(cmd_stderr)

            if returncode not in exit_codes:
                LOG.error("Error running %s. [%s]\n" % (cmd, returncode))
                LOG.error("stdout: %s" % cmd_stdout)
                LOG.error("stderr: %s" % cmd_stderr)
                deploy_status_code = returncode
            else:
                LOG.debug('Completed $ %s' % ' '.join(cmd))
                LOG.info("stdout: %s" % cmd_stdout)
                LOG.info("stderr: %s" % cmd_stderr)
        return stdout, stderr, deploy_status_code

    def delete_missing_and_updated(self):
        container_names = self.runner.container_names(self.config_id)
        for cn in container_names:
            container = cn[0]

            # if the desired name is not in the config, delete it
            if cn[-1] not in self.config:
                LOG.debug("Deleting container (removed): %s" % container)
                self.runner.remove_container(container)
                continue

            ex_data_str = self.runner.inspect(
                container, '{{index .Config.Labels "config_data"}}')
            if not ex_data_str:
                LOG.debug("Deleting container (no config_data): %s"
                          % container)
                self.runner.remove_container(container)
                continue

            try:
                ex_data = json.loads(ex_data_str)
            except Exception:
                ex_data = None

            new_data = self.config.get(cn[-1])
            if new_data != ex_data:
                LOG.debug("Deleting container (changed config_data): %s"
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

    def docker_run_args(self, cmd, container):
        cconfig = self.config[container]
        if cconfig.get('detach', True):
            cmd.append('--detach=true')
        if 'env_file' in cconfig:
            env_file = cconfig['env_file']
            if not isinstance(env_file, list):
                env_file = [env_file]
            for f in env_file:
                if f:
                    cmd.append('--env-file=%s' % f)
        for v in cconfig.get('environment', []):
            if v:
                cmd.append('--env=%s' % v)
        if cconfig.get('remove', False):
            cmd.append('--rm')
        if cconfig.get('interactive', False):
            cmd.append('--interactive')
        if cconfig.get('tty', False):
            cmd.append('--tty')
        if 'net' in cconfig:
            cmd.append('--net=%s' % cconfig['net'])
        if 'ipc' in cconfig:
            cmd.append('--ipc=%s' % cconfig['ipc'])
        if 'pid' in cconfig:
            cmd.append('--pid=%s' % cconfig['pid'])
        if 'healthcheck' in cconfig:
            hconfig = cconfig['healthcheck']
            if 'test' in hconfig:
                cmd.append('--health-cmd=%s' % hconfig['test'])
            if 'interval' in hconfig:
                cmd.append('--health-interval=%s' % hconfig['interval'])
            if 'timeout' in hconfig:
                cmd.append('--health-timeout=%s' % hconfig['timeout'])
            if 'retries' in hconfig:
                cmd.append('--health-retries=%s' % hconfig['retries'])
        if 'privileged' in cconfig:
            cmd.append('--privileged=%s' % str(cconfig['privileged']).lower())
        if 'restart' in cconfig:
            cmd.append('--restart=%s' % cconfig['restart'])
        if 'user' in cconfig:
            cmd.append('--user=%s' % cconfig['user'])
        for v in cconfig.get('volumes', []):
            if v:
                cmd.append('--volume=%s' % v)
        for v in cconfig.get('volumes_from', []):
            if v:
                cmd.append('--volumes-from=%s' % v)

        cmd.append(cconfig.get('image', ''))
        cmd.extend(self.command_argument(cconfig.get('command')))

    def docker_exec_args(self, cmd, container):
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
            if self.runner.inspect(image, format='exists', type='image'):
                continue

            cmd = [self.runner.docker_cmd, 'pull', image]
            (cmd_stdout, cmd_stderr, rc) = self.runner.execute(cmd)
            if cmd_stdout:
                stdout.append(cmd_stdout)
            if cmd_stderr:
                stderr.append(cmd_stderr)

            if rc != 0:
                returncode = rc
                LOG.error("Error running %s. [%s]\n" % (cmd, returncode))
                LOG.error("stdout: %s" % cmd_stdout)
                LOG.error("stderr: %s" % cmd_stderr)
            else:
                LOG.debug('Completed $ %s' % ' '.join(cmd))
                LOG.info("stdout: %s" % cmd_stdout)
                LOG.info("stderr: %s" % cmd_stderr)
        return returncode

    @staticmethod
    def command_argument(command):
        if not command:
            return []
        if not isinstance(command, list):
            return command.split()
        return command
