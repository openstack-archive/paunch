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

import mock

from paunch.builder import compose1
from paunch.tests import test_builder_base as tbb


class TestComposeV1Builder(tbb.TestBaseBuilder):
    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_cont_run_args(self, runner):
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
                'healthcheck': {
                    'test': '/bin/true',
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 3
                },
                'env_file': '/tmp/foo.env',
                'log_tag': '{{.ImageName}}/{{.Name}}/{{.ID}}',
                'cpu_shares': 600,
                'cpuset_cpus': 'all',
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
        runner.validate_volume_source.return_value = True
        builder = compose1.ComposeV1Builder('foo', config, runner)

        cmd = ['docker', 'run', '--name', 'one']
        builder.container_run_args(cmd, 'one')
        self.assertEqual(
            ['docker', 'run', '--name', 'one',
             '--detach=true', '--env-file=/tmp/foo.env',
             '--net=host', '--ipc=host', '--pid=container:bar',
             '--uts=host', '--health-cmd', '/bin/true',
             '--health-interval=30s',
             '--health-timeout=10s', '--health-retries=3',
             '--privileged=true', '--restart=always', '--user=bar',
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

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_cont_run_args_validation_true(self, runner):
        config = {
            'one': {
                'image': 'foo',
                'volumes': ['/foo:/foo:rw', '/bar:/bar:ro'],
            }
        }
        runner.validate_volume_source.return_value = True
        builder = compose1.ComposeV1Builder('foo', config, runner)

        cmd = ['docker']
        self.assertTrue(builder.container_run_args(cmd, 'one'))
        self.assertEqual(
            ['docker', '--detach=true',
             '--volume=/foo:/foo:rw', '--volume=/bar:/bar:ro', 'foo'],
            cmd
        )

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_cont_run_args_validation_false(self, runner):
        config = {
            'one': {
                'image': 'foo',
                'volumes': ['/foo:/foo:rw', '/bar:/bar:ro'],
            }
        }
        runner.validate_volume_source.return_value = False
        builder = compose1.ComposeV1Builder('foo', config, runner)

        cmd = ['docker']
        self.assertFalse(builder.container_run_args(cmd, 'one'))
        self.assertEqual(
            ['docker', '--detach=true',
             '--volume=/foo:/foo:rw', '--volume=/bar:/bar:ro', 'foo'],
            cmd
        )
