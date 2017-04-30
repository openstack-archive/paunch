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

import collections
import mock

from paunch.builder import compose1
from paunch.tests import base


class TestComposeV1Builder(base.TestCase):

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_apply(self, runner):
        config = {
            'one': {
                'start_order': 0,
                'image': 'centos:7',
            },
            'two': {
                'start_order': 1,
                'image': 'centos:7',
            },
            'three': {
                'start_order': 2,
                'image': 'centos:7',
            },
            'four': {
                'start_order': 10,
                'image': 'centos:7',
            },
            'four_ls': {
                'action': 'exec',
                'start_order': 20,
                'command': ['four', 'ls', '-l', '/']
            }
        }

        r = runner.return_value
        r.managed_by = 'tester'
        r.discover_container_name = lambda n, c: '%s-12345678' % n
        r.unique_container_name = lambda n: '%s-12345678' % n
        r.docker_cmd = 'docker'
        r.execute.return_value = ('Done!', '', 0)

        builder = compose1.ComposeV1Builder('foo', config, r)
        stdout, stderr, deploy_status_code = builder.apply()
        self.assertEqual(0, deploy_status_code)
        self.assertEqual(['Done!', 'Done!', 'Done!', 'Done!', 'Done!'], stdout)
        self.assertEqual([], stderr)

        r.execute.assert_has_calls([
            mock.call(
                ['docker', 'run', '--name', 'one-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=one',
                 '--label', 'managed_by=tester',
                 '--detach=true', 'centos:7']
            ),
            mock.call(
                ['docker', 'run', '--name', 'two-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=two',
                 '--label', 'managed_by=tester',
                 '--detach=true', 'centos:7']
            ),
            mock.call(
                ['docker', 'run', '--name', 'three-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=three',
                 '--label', 'managed_by=tester',
                 '--detach=true', 'centos:7']
            ),
            mock.call(
                ['docker', 'run', '--name', 'four-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=four',
                 '--label', 'managed_by=tester',
                 '--detach=true', 'centos:7']
            ),
            mock.call(
                ['docker', 'exec', 'four-12345678', 'ls', '-l', '/']
            ),
        ])

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_label_arguments(self, runner):
        r = runner.return_value
        r.managed_by = 'tester'
        builder = compose1.ComposeV1Builder('foo', {}, r)
        cmd = []
        builder.label_arguments(cmd, 'one')
        self.assertEqual(
            ['--label', 'config_id=foo',
             '--label', 'container_name=one',
             '--label', 'managed_by=tester'],
            cmd)

        labels = collections.OrderedDict()
        labels['foo'] = 'bar'
        labels['bar'] = 'baz'

        builder = compose1.ComposeV1Builder('foo', {}, r, labels=labels)
        cmd = []
        builder.label_arguments(cmd, 'one')
        self.assertEqual(
            ['--label', 'foo=bar',
             '--label', 'bar=baz',
             '--label', 'config_id=foo',
             '--label', 'container_name=one',
             '--label', 'managed_by=tester'],
            cmd)

    def test_docker_run_args(self):
        config = {
            'one': {
                'image': 'centos:7',
                'privileged': True,
                'user': 'bar',
                'net': 'host',
                'pid': 'container:bar',
                'restart': 'always',
                'env_file': '/tmp/foo.env',
            }
        }
        builder = compose1.ComposeV1Builder('foo', config, None)

        cmd = ['docker', 'run', '--name', 'one']
        builder.docker_run_args(cmd, 'one')
        self.assertEqual(
            ['docker', 'run', '--name', 'one',
             '--detach=true', '--env-file=/tmp/foo.env',
             '--net=host', '--pid=container:bar',
             '--privileged=true', '--restart=always', '--user=bar',
             'centos:7'],
            cmd
        )

    def test_docker_run_args_lists(self):
        config = {
            'one': {
                'image': 'centos:7',
                'detach': False,
                'command': 'ls -l /foo',
                'environment': ['FOO=BAR', 'BAR=BAZ'],
                'env_file': ['/tmp/foo.env', '/tmp/bar.env'],
                'volumes': ['/foo:/foo:rw', '/bar:/bar:ro'],
                'volumes_from': ['two', 'three']
            }
        }
        builder = compose1.ComposeV1Builder('foo', config, None)

        cmd = ['docker', 'run', '--name', 'one']
        builder.docker_run_args(cmd, 'one')
        self.assertEqual(
            ['docker', 'run', '--name', 'one',
             '--env-file=/tmp/foo.env', '--env-file=/tmp/bar.env',
             '--env=FOO=BAR', '--env=BAR=BAZ',
             '--volume=/foo:/foo:rw', '--volume=/bar:/bar:ro',
             '--volumes-from=two', '--volumes-from=three',
             'centos:7', 'ls', '-l', '/foo'],
            cmd
        )

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_docker_exec_args(self, runner):
        r = runner.return_value
        r.discover_container_name.return_value = 'one-12345678'
        config = {
            'one': {
                'command': 'ls -l /foo',
                'privileged': True,
                'user': 'bar'
            }
        }
        self.builder = compose1.ComposeV1Builder(
            'foo', config, runner.return_value)

        cmd = ['docker', 'exec']
        self.builder.docker_exec_args(cmd, 'one')
        self.assertEqual(
            ['docker', 'exec',
             '--privileged=true', '--user=bar',
             'one-12345678', '-l', '/foo'],
            cmd
        )

    def test_command_argument(self):
        b = compose1.ComposeV1Builder
        self.assertEqual([], b.command_argument(None))
        self.assertEqual([], b.command_argument(''))
        self.assertEqual([], b.command_argument([]))
        self.assertEqual(
            ['ls', '-l', '/foo-bar'],
            b.command_argument(['ls', '-l', '/foo-bar'])
        )
        self.assertEqual(
            ['ls', '-l', '/foo-bar'],
            b.command_argument('ls -l /foo-bar')
        )
        self.assertEqual(
            ['ls', '-l', '/foo bar'],
            b.command_argument(['ls', '-l', '/foo bar'])
        )
        # don't expect quoted spaces to do the right thing
        self.assertEqual(
            ['ls', '-l', '"/foo', 'bar"'],
            b.command_argument('ls -l "/foo bar"')
        )
