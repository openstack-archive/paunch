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
import json
import mock

from paunch.builder import compose1
from paunch import runner
from paunch.tests import base


class TestComposeV1Builder(base.TestCase):

    def test_apply(self):
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
                'image': 'centos:6',
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

        r = runner.DockerRunner(managed_by='tester', docker_cmd='docker')
        exe = mock.Mock()
        exe.side_effect = [
            ('exists', '', 0),  # inspect for image centos:6
            ('', '', 1),  # inspect for missing image centos:7
            ('Pulled centos:7', '', 0),  # pull centos:6
            ('', '', 0),  # ps for delete_missing_and_updated container_names
            ('', '', 0),  # ps for after delete_missing_and_updated renames
            ('', '', 0),  # ps to only create containers which don't exist
            ('Created one-12345678', '', 0),
            ('Created two-12345678', '', 0),
            ('Created three-12345678', '', 0),
            ('Created four-12345678', '', 0),
            ('a\nb\nc', '', 0)
        ]
        r.discover_container_name = lambda n, c: '%s-12345678' % n
        r.unique_container_name = lambda n: '%s-12345678' % n
        r.execute = exe

        builder = compose1.ComposeV1Builder('foo', config, r)
        stdout, stderr, deploy_status_code = builder.apply()
        self.assertEqual(0, deploy_status_code)
        self.assertEqual([
            'Pulled centos:7',
            'Created one-12345678',
            'Created two-12345678',
            'Created three-12345678',
            'Created four-12345678',
            'a\nb\nc'
        ], stdout)
        self.assertEqual([], stderr)

        exe.assert_has_calls([
            # inspect existing image centos:6
            mock.call(
                ['docker', 'inspect', '--type', 'image',
                 '--format', 'exists', 'centos:6']
            ),
            # inspect and pull missing image centos:7
            mock.call(
                ['docker', 'inspect', '--type', 'image',
                 '--format', 'exists', 'centos:7']
            ),
            mock.call(
                ['docker', 'pull', 'centos:7']
            ),
            # ps for delete_missing_and_updated container_names
            mock.call(
                ['docker', 'ps', '-a',
                 '--filter', 'label=managed_by=tester',
                 '--filter', 'label=config_id=foo',
                 '--format', '{{.Names}} {{.Label "container_name"}}']
            ),
            # ps for after delete_missing_and_updated renames
            mock.call(
                ['docker', 'ps', '-a',
                 '--filter', 'label=managed_by=tester',
                 '--format', '{{.Names}} {{.Label "container_name"}}']
            ),
            # ps to only create containers which don't exist
            mock.call(
                ['docker', 'ps', '-a',
                 '--filter', 'label=managed_by=tester',
                 '--filter', 'label=config_id=foo',
                 '--format', '{{.Names}} {{.Label "container_name"}}']
            ),
            # run one
            mock.call(
                ['docker', 'run', '--name', 'one-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=one',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['one']),
                 '--detach=true', 'centos:7']
            ),
            # run two
            mock.call(
                ['docker', 'run', '--name', 'two-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=two',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['two']),
                 '--detach=true', 'centos:7']
            ),
            # run three
            mock.call(
                ['docker', 'run', '--name', 'three-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=three',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['three']),
                 '--detach=true', 'centos:6']
            ),
            # run four
            mock.call(
                ['docker', 'run', '--name', 'four-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=four',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['four']),
                 '--detach=true', 'centos:7']
            ),
            # execute within four
            mock.call(
                ['docker', 'exec', 'four-12345678', 'ls', '-l', '/']
            ),
        ])

    def test_apply_idempotency(self):
        config = {
            # not running yet
            'one': {
                'start_order': 0,
                'image': 'centos:7',
            },
            # running, but with a different config
            'two': {
                'start_order': 1,
                'image': 'centos:7',
            },
            # running with the same config
            'three': {
                'start_order': 2,
                'image': 'centos:7',
            },
            # not running yet
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

        r = runner.DockerRunner(managed_by='tester', docker_cmd='docker')
        exe = mock.Mock()
        exe.side_effect = [
            # inspect for image centos:7
            ('exists', '', 0),
            # ps for delete_missing_and_updated container_names
            ('''five five
six six
two-12345678 two
three-12345678 three''', '', 0),
            # rm five
            ('', '', 0),
            # rm six
            ('', '', 0),
            # inspect two
            ('{"start_order": 1, "image": "centos:6"}', '', 0),
            # rm two, changed config data
            ('', '', 0),
            # inspect three
            ('{"start_order": 2, "image": "centos:7"}', '', 0),
            # ps for after delete_missing_and_updated renames
            ('', '', 0),
            # ps to only create containers which don't exist
            ('three-12345678 three', '', 0),
            ('Created one-12345678', '', 0),
            ('Created two-12345678', '', 0),
            ('Created four-12345678', '', 0),
            ('a\nb\nc', '', 0)
        ]
        r.discover_container_name = lambda n, c: '%s-12345678' % n
        r.unique_container_name = lambda n: '%s-12345678' % n
        r.execute = exe

        builder = compose1.ComposeV1Builder('foo', config, r)
        stdout, stderr, deploy_status_code = builder.apply()
        self.assertEqual(0, deploy_status_code)
        self.assertEqual([
            'Created one-12345678',
            'Created two-12345678',
            'Created four-12345678',
            'a\nb\nc'
        ], stdout)
        self.assertEqual([], stderr)

        exe.assert_has_calls([
            # inspect image centos:7
            mock.call(
                ['docker', 'inspect', '--type', 'image',
                 '--format', 'exists', 'centos:7']
            ),
            # ps for delete_missing_and_updated container_names
            mock.call(
                ['docker', 'ps', '-a',
                 '--filter', 'label=managed_by=tester',
                 '--filter', 'label=config_id=foo',
                 '--format', '{{.Names}} {{.Label "container_name"}}']
            ),
            # rm containers not in config
            mock.call(['docker', 'rm', '-f', 'five']),
            mock.call(['docker', 'rm', '-f', 'six']),
            # rm two, changed config
            mock.call(['docker', 'inspect', '--type', 'container',
                       '--format', '{{index .Config.Labels "config_data"}}',
                       'two-12345678']),
            mock.call(['docker', 'rm', '-f', 'two-12345678']),
            # check three, config hasn't changed
            mock.call(['docker', 'inspect', '--type', 'container',
                       '--format', '{{index .Config.Labels "config_data"}}',
                       'three-12345678']),
            # ps for after delete_missing_and_updated renames
            mock.call(
                ['docker', 'ps', '-a',
                 '--filter', 'label=managed_by=tester',
                 '--format', '{{.Names}} {{.Label "container_name"}}']
            ),
            # ps to only create containers which don't exist
            mock.call(
                ['docker', 'ps', '-a',
                 '--filter', 'label=managed_by=tester',
                 '--filter', 'label=config_id=foo',
                 '--format', '{{.Names}} {{.Label "container_name"}}']
            ),
            # run one
            mock.call(
                ['docker', 'run', '--name', 'one-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=one',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['one']),
                 '--detach=true', 'centos:7']
            ),
            # run two
            mock.call(
                ['docker', 'run', '--name', 'two-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=two',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['two']),
                 '--detach=true', 'centos:7']
            ),
            # don't run three, its already running
            # run four
            mock.call(
                ['docker', 'run', '--name', 'four-12345678',
                 '--label', 'config_id=foo',
                 '--label', 'container_name=four',
                 '--label', 'managed_by=tester',
                 '--label', 'config_data=%s' % json.dumps(config['four']),
                 '--detach=true', 'centos:7']
            ),
            # execute within four
            mock.call(
                ['docker', 'exec', 'four-12345678', 'ls', '-l', '/']
            ),
        ])

    def test_apply_failed_pull(self):
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
                'image': 'centos:6',
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

        r = runner.DockerRunner(managed_by='tester', docker_cmd='docker')
        exe = mock.Mock()
        exe.side_effect = [
            ('exists', '', 0),  # inspect for image centos:6
            ('', '', 1),  # inspect for missing image centos:7
            ('Pulling centos:7', 'ouch', 1),  # pull centos:7 failure
        ]
        r.execute = exe

        builder = compose1.ComposeV1Builder('foo', config, r)
        stdout, stderr, deploy_status_code = builder.apply()
        self.assertEqual(1, deploy_status_code)
        self.assertEqual(['Pulling centos:7'], stdout)
        self.assertEqual(['ouch'], stderr)

        exe.assert_has_calls([
            # inspect existing image centos:6
            mock.call(
                ['docker', 'inspect', '--type', 'image',
                 '--format', 'exists', 'centos:6']
            ),
            # inspect and pull missing image centos:7
            mock.call(
                ['docker', 'inspect', '--type', 'image',
                 '--format', 'exists', 'centos:7']
            ),
            mock.call(
                ['docker', 'pull', 'centos:7']
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
             '--label', 'managed_by=tester',
             '--label', 'config_data=null'],
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
             '--label', 'managed_by=tester',
             '--label', 'config_data=null'],
            cmd)

    def test_docker_run_args(self):
        config = {
            'one': {
                'image': 'centos:7',
                'privileged': True,
                'user': 'bar',
                'net': 'host',
                'ipc': 'host',
                'pid': 'container:bar',
                'restart': 'always',
                'healthcheck': {
                    'test': '/bin/true',
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 3
                },
                'env_file': '/tmp/foo.env',
            }
        }
        builder = compose1.ComposeV1Builder('foo', config, None)

        cmd = ['docker', 'run', '--name', 'one']
        builder.docker_run_args(cmd, 'one')
        self.assertEqual(
            ['docker', 'run', '--name', 'one',
             '--detach=true', '--env-file=/tmp/foo.env',
             '--net=host', '--ipc=host', '--pid=container:bar',
             '--health-cmd=/bin/true', '--health-interval=30s',
             '--health-timeout=10s', '--health-retries=3',
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
                'remove': True,
                'tty': True,
                'interactive': True,
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
             '--rm', '--interactive', '--tty',
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
