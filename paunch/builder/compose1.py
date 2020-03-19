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
import tenacity
import yaml

from paunch.utils import common


class ComposeV1Builder(object):

    def __init__(self, config_id, config, runner, labels=None, log=None):
        self.config_id = config_id
        self.config = config
        self.labels = labels
        self.runner = runner
        # Leverage pre-configured logger
        self.log = log or common.configure_logging(__name__)

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
            action = self.config[container].get('action', 'run')
            exit_codes = self.config[container].get('exit_codes', [0])

            if action == 'run':
                if container in desired_names:
                    self.log.debug(
                        'Skipping existing container: %s' % container)
                    continue

                c_name = self.runner.discover_container_name(
                    container, self.config_id) or container
                cmd = [
                    self.runner.docker_cmd,
                    'run',
                    '--name',
                    c_name
                ]
                self.label_arguments(cmd, container)
                self.docker_run_args(cmd, container)
            elif action == 'exec':
                cmd = [self.runner.docker_cmd, 'exec']
                self.docker_exec_args(cmd, container)

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
                self.log.debug("Deleting container (no config_data): %s" %
                               container)
                self.runner.remove_container(container)
                continue

            try:
                ex_data = yaml.safe_load(str(ex_data_str))
            except Exception:
                ex_data = None

            new_data = self.config.get(cn[-1])
            if new_data != ex_data:
                self.log.debug("Deleting container (changed config_data): %s" %
                               container)
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
        if 'uts' in cconfig:
            cmd.append('--uts=%s' % cconfig['uts'])
        for u in cconfig.get('ulimit', []):
            if u:
                cmd.append('--ulimit=%s' % u)
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
        if 'log_tag' in cconfig:
            cmd.append('--log-opt=tag=%s' % cconfig['log_tag'])
        if 'cpu_shares' in cconfig:
            cmd.append('--cpu-shares=%s' % cconfig['cpu_shares'])
        if 'security_opt' in cconfig:
            cmd.append('--security-opt=%s' % cconfig['security_opt'])
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
        if 'mem_limit' in cconfig:
            cmd.append('--memory=%s' % cconfig['mem_limit'])
        if 'memswap_limit' in cconfig:
            cmd.append('--memory-swap=%s' % cconfig['memswap_limit'])
        if 'mem_swappiness' in cconfig:
            cmd.append('--memory-swappiness=%s' % cconfig['mem_swappiness'])

        cmd.append(cconfig.get('image', ''))
        cmd.extend(self.command_argument(cconfig.get('command')))

    def docker_exec_args(self, cmd, container):
        cconfig = self.config[container]
        if 'privileged' in cconfig:
            cmd.append('--privileged=%s' % str(cconfig['privileged']).lower())
        if 'user' in cconfig:
            cmd.append('--user=%s' % cconfig['user'])
        # TODO(sbaker): support the dict layout for this property
        for v in cconfig.get('environment', []):
            if v:
                cmd.append('--env=%s' % v)
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
        cmd = [self.runner.docker_cmd, 'pull', image]
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


class PullException(Exception):

    def __init__(self, stdout, stderr, rc):
        self.stdout = stdout
        self.stderr = stderr
        self.rc = rc
