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
import os
import random
import string
import subprocess


DOCKER_CMD = os.environ.get('HEAT_DOCKER_CMD', 'docker')

LOG = logging.getLogger(__name__)


def execute(cmd):
    LOG.debug(' '.join(cmd))
    subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    cmd_stdout, cmd_stderr = subproc.communicate()
    LOG.debug(cmd_stdout)
    LOG.debug(cmd_stderr)
    return cmd_stdout, cmd_stderr, subproc.returncode


def current_config_ids():
    # List all config_id labels for containers managed by docker-cmd
    cmd = [
        DOCKER_CMD, 'ps', '-a',
        '--filter', 'label=managed_by=docker-cmd',
        '--format', '{{.Label "config_id"}}'
    ]
    cmd_stdout, cmd_stderr, returncode = execute(cmd)
    if returncode != 0:
        return set()
    return set(cmd_stdout.split())


def remove_containers(conf_id, managed_by):
    cmd = [
        DOCKER_CMD, 'ps', '-q', '-a',
        '--filter', 'label=managed_by=%s' % managed_by,
        '--filter', 'label=config_id=%s' % conf_id
    ]
    cmd_stdout, cmd_stderr, returncode = execute(cmd)
    if returncode == 0:
        for container in cmd_stdout.split():
            remove_container(container)


def remove_container(container):
    cmd = [DOCKER_CMD, 'rm', '-f', container]
    cmd_stdout, cmd_stderr, returncode = execute(cmd)
    if returncode != 0:
        LOG.error('Error removing container: %s' % container)
        LOG.error(cmd_stderr)


def rename_containers():
    # list every container name, and its container_name label
    cmd = [
        DOCKER_CMD, 'ps', '-a',
        '--format', '{{.Names}} {{.Label "container_name"}}'
    ]
    cmd_stdout, cmd_stderr, returncode = execute(cmd)
    if returncode != 0:
        return

    lines = cmd_stdout.split("\n")
    current_containers = []
    need_renaming = {}
    for line in lines:
        entry = line.split()
        if not entry:
            continue
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
            LOG.info('Cannot rename "%s" since "%s" still exists' % (
                current, desired))
        else:
            cmd = [DOCKER_CMD, 'rename', current, desired]
            execute(cmd)


def inspect(container, format=None):
    cmd = [DOCKER_CMD, 'inspect']
    if format:
        cmd.append('--format')
        cmd.append(format)
    cmd.append(container)
    (cmd_stdout, cmd_stderr, returncode) = execute(cmd)
    if returncode != 0:
        return
    try:
        if format:
            return cmd_stdout
        else:
            return json.loads(cmd_stdout)[0]
    except Exception as e:
        LOG.error('Problem parsing docker inspect: %s' % e)


def unique_container_name(container):
    container_name = container
    while inspect(container_name, format='exists'):
        suffix = ''.join(random.choice(
            string.ascii_lowercase + string.digits) for i in range(8))
        container_name = '%s-%s' % (container, suffix)
    return container_name


def discover_container_name(container, cid):
    cmd = [
        DOCKER_CMD,
        'ps',
        '-a',
        '--filter',
        'label=container_name=%s' % container,
        '--filter',
        'label=config_id=%s' % cid,
        '--format',
        '{{.Names}}'
    ]
    (cmd_stdout, cmd_stderr, returncode) = execute(cmd)
    if returncode != 0:
        return container
    names = cmd_stdout.split()
    if names:
        return names[0]
    return container
