# -*- coding: utf-8 -*-

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

from paunch.builder import podman
from paunch.tests import test_builder_base as base


class TestPodmanBuilder(base.TestBaseBuilder):
    def test_cont_run_args(self):
        config = {
            'one': {
                'image': 'centos:7',
                'privileged': True,
                'user': 'bar',
                'net': 'host',
                'ipc': 'host',
                'pid': 'container:bar',
                'uts': 'host',
                'restart': 'always',
                'env_file': '/tmp/foo.env',
                'log_tag': '{{.ImageName}}/{{.Name}}/{{.ID}}',
                'cpu_shares': 600,
                'mem_limit': '1G',
                'memswap_limit': '1G',
                'mem_swappiness': '60',
                'security_opt': 'label:disable',
                'cap_add': ['SYS_ADMIN', 'SETUID'],
                'cap_drop': ['NET_RAW'],
                'hostname': 'foohostname',
                'extra_hosts': [
                    'foohost:127.0.0.1',
                    'barhost:127.0.0.2'
                    ]
            }
        }
        builder = podman.PodmanBuilder('foo', config, None)

        cmd = ['podman', 'run', '--name', 'one']
        builder.container_run_args(cmd, 'one')
        self.assertEqual(
            ['podman', 'run', '--name', 'one',
             '--conmon-pidfile=/var/run/one.pid',
             '--detach=true', '--env-file=/tmp/foo.env',
             '--net=host', '--ipc=host', '--pid=container:bar',
             '--uts=host', '--privileged=true', '--user=bar',
             '--log-opt=tag={{.ImageName}}/{{.Name}}/{{.ID}}',
             '--cpu-shares=600',
             '--memory=1G',
             '--memory-swap=1G',
             '--memory-swappiness=60',
             '--security-opt=label:disable',
             '--hostname=foohostname',
             '--add-host=foohost:127.0.0.1',
             '--add-host=barhost:127.0.0.2',
             '--cap-add=SYS_ADMIN', '--cap-add=SETUID', '--cap-drop=NET_RAW',
             'centos:7'],
            cmd
        )
