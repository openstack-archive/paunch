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
from testtools import matchers

from paunch import runner
from paunch.tests import base


class TestBaseRunner(base.TestCase):
    def setUp(self):
        super(TestBaseRunner, self).setUp()
        self.runner = runner.DockerRunner('tester')
        self.podman_runner = runner.PodmanRunner('tester')

    def mock_execute(self, popen, stdout, stderr, returncode):
        subproc = mock.Mock()
        subproc.returncode = returncode
        subproc.communicate.return_value = (stdout.encode('utf-8'),
                                            stderr.encode('utf-8'))
        popen.return_value = subproc

    def assert_execute(self, popen, cmd):
        popen.assert_called_with(cmd, stderr=-1, stdout=-1)

    @mock.patch('subprocess.Popen')
    def test_execute(self, popen):
        self.mock_execute(popen, 'The stdout', 'The stderr', 0)

        self.assertEqual(
            ('The stdout', 'The stderr', 0),
            self.runner.execute(['ls', '-l'])
        )
        self.assert_execute(popen, ['ls', '-l'])

    @mock.patch('subprocess.Popen')
    def test_current_config_ids_docker(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree', '', 0)

        self.assertEqual(
            set(('one', 'two', 'three')),
            self.runner.current_config_ids()
        )
        self.assert_execute(
            popen, ['docker', 'ps', '-a', '--filter',
                    'label=managed_by=tester',
                    '--format', '{{.Label "config_id"}}']
        )

    @mock.patch('subprocess.Popen')
    def test_current_config_ids_podman(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree', '', 0)
        self.assertEqual(
            set(('one', 'two', 'three')),
            self.podman_runner.current_config_ids()
        )
        self.assert_execute(
            popen, ['podman', 'ps', '-a', '--filter',
                    'label=managed_by=tester',
                    '--format', '{{.Labels.config_id}}']
        )

    @mock.patch('subprocess.Popen')
    def test_containers_in_config(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree', '', 0)
        self.runner.remove_container = mock.Mock()

        result = self.runner.containers_in_config('foo')

        self.assert_execute(
            popen, ['docker', 'ps', '-q', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--filter', 'label=config_id=foo']
        )
        self.assertEqual(['one', 'two', 'three'], result)

    @mock.patch('subprocess.Popen')
    def test_inspect(self, popen):
        self.mock_execute(popen, '[{"foo": "bar"}]', '', 0)

        self.assertEqual(
            {"foo": "bar"},
            self.runner.inspect('one')
        )
        self.assert_execute(
            popen, ['docker', 'inspect', '--type', 'container', 'one']
        )

    @mock.patch('subprocess.Popen')
    def test_inspect_format(self, popen):
        self.mock_execute(popen, 'bar', '', 0)

        self.assertEqual(
            "bar",
            self.runner.inspect('one', output_format='{{foo}}')
        )
        self.assert_execute(
            popen, ['docker', 'inspect', '--type', 'container',
                    '--format', '{{foo}}', 'one']
        )

    def test_unique_container_name(self):
        self.runner.inspect = mock.Mock()
        self.runner.inspect.return_value = None
        self.assertEqual('foo', self.runner.unique_container_name('foo'))

        self.runner.inspect.side_effect = ['exists', 'exists', None]
        name = self.runner.unique_container_name('foo')
        name_pattern = '^foo-[a-z0-9]{8}$'
        self.assertThat(name, matchers.MatchesRegex(name_pattern))

    @mock.patch('subprocess.Popen')
    def test_discover_container_name(self, popen):
        self.mock_execute(popen, 'one-12345678', '', 0)

        self.assertEqual(
            'one-12345678',
            self.runner.discover_container_name('one', 'foo')
        )

        self.assert_execute(
            popen, ['docker', 'ps', '-a',
                    '--filter', 'label=container_name=one',
                    '--filter', 'label=config_id=foo',
                    '--format', '{{.Names}}']
        )

    @mock.patch('subprocess.Popen')
    def test_discover_container_name_empty(self, popen):
        self.mock_execute(popen, '', '', 0)

        self.assertEqual(
            'one',
            self.runner.discover_container_name('one', 'foo')
        )

    @mock.patch('subprocess.Popen')
    def test_discover_container_name_error(self, popen):
        self.mock_execute(popen, '', 'ouch', 1)

        self.assertEqual(
            'one',
            self.runner.discover_container_name('one', 'foo')
        )

    @mock.patch('subprocess.Popen')
    def test_delete_missing_configs_docker(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree\nfour', '', 0)
        self.runner.remove_containers = mock.Mock()

        self.runner.delete_missing_configs(['two', 'three'])
        self.assert_execute(
            popen, ['docker', 'ps', '-a', '--filter',
                    'label=managed_by=tester',
                    '--format', '{{.Label "config_id"}}']
        )

        # containers one and four will be deleted
        self.runner.remove_containers.assert_has_calls([
            mock.call('one'), mock.call('four')
        ], any_order=True)

    @mock.patch('subprocess.Popen')
    def test_delete_missing_configs_podman(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree\nfour', '', 0)
        self.podman_runner.remove_containers = mock.Mock()

        self.podman_runner.delete_missing_configs(['two', 'three'])
        self.assert_execute(
            popen, ['podman', 'ps', '-a', '--filter',
                    'label=managed_by=tester',
                    '--format', '{{.Labels.config_id}}']
        )

        # containers one and four will be deleted
        self.podman_runner.remove_containers.assert_has_calls([
            mock.call('one'), mock.call('four')
        ], any_order=True)

    @mock.patch('subprocess.Popen')
    def test_list_configs_docker(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree', '', 0)
        self.runner.inspect = mock.Mock(
            return_value={'e': 'f'})
        self.runner.containers_in_config = mock.Mock(
            return_value=['a', 'b', 'c'])

        result = self.runner.list_configs()

        self.assert_execute(
            popen, ['docker', 'ps', '-a', '--filter',
                    'label=managed_by=tester',
                    '--format', '{{.Label "config_id"}}']
        )
        self.runner.containers_in_config.assert_has_calls([
            mock.call('one'), mock.call('two'), mock.call('three')
        ], any_order=True)
        self.runner.inspect.assert_has_calls([
            mock.call('a'), mock.call('b'), mock.call('c'),
            mock.call('a'), mock.call('b'), mock.call('c'),
            mock.call('a'), mock.call('b'), mock.call('c')
        ])
        self.assertEqual({
            'one': [{'e': 'f'}, {'e': 'f'}, {'e': 'f'}],
            'two': [{'e': 'f'}, {'e': 'f'}, {'e': 'f'}],
            'three': [{'e': 'f'}, {'e': 'f'}, {'e': 'f'}]
        }, result)

    @mock.patch('subprocess.Popen')
    def test_list_configs_podman(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree', '', 0)
        self.podman_runner.inspect = mock.Mock(
            return_value={'e': 'f'})
        self.podman_runner.containers_in_config = mock.Mock(
            return_value=['a', 'b', 'c'])

        result = self.podman_runner.list_configs()

        self.assert_execute(
            popen, ['podman', 'ps', '-a', '--filter',
                    'label=managed_by=tester',
                    '--format', '{{.Labels.config_id}}']
        )
        self.podman_runner.containers_in_config.assert_has_calls([
            mock.call('one'), mock.call('two'), mock.call('three')
        ], any_order=True)
        self.podman_runner.inspect.assert_has_calls([
            mock.call('a'), mock.call('b'), mock.call('c'),
            mock.call('a'), mock.call('b'), mock.call('c'),
            mock.call('a'), mock.call('b'), mock.call('c')
        ])
        self.assertEqual({
            'one': [{'e': 'f'}, {'e': 'f'}, {'e': 'f'}],
            'two': [{'e': 'f'}, {'e': 'f'}, {'e': 'f'}],
            'three': [{'e': 'f'}, {'e': 'f'}, {'e': 'f'}]
        }, result)

    @mock.patch('subprocess.Popen')
    def test_remove_containers(self, popen):
        self.mock_execute(popen, 'one\ntwo\nthree', '', 0)
        self.runner.remove_container = mock.Mock()

        self.runner.remove_containers('foo')

        self.assert_execute(
            popen, ['docker', 'ps', '-q', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--filter', 'label=config_id=foo']
        )
        self.runner.remove_container.assert_has_calls([
            mock.call('one'), mock.call('two'), mock.call('three')
        ])

    @mock.patch('subprocess.Popen')
    def test_remove_container(self, popen):
        self.mock_execute(popen, '', '', 0)

        self.runner.remove_container('one')
        self.assert_execute(
            popen, ['docker', 'rm', '-f', 'one']
        )

    @mock.patch('subprocess.Popen')
    def test_stop_container(self, popen):
        self.mock_execute(popen, '', '', 0)

        self.runner.stop_container('one')
        self.assert_execute(
            popen, ['docker', 'stop', 'one']
        )

    @mock.patch('subprocess.Popen')
    def test_stop_container_override(self, popen):
        self.mock_execute(popen, '', '', 0)

        self.runner.stop_container('one', 'podman')
        self.assert_execute(
            popen, ['podman', 'stop', 'one']
        )

    @mock.patch('subprocess.Popen')
    def test_container_names_docker(self, popen):
        ps_result = '''one one
two-12345678 two
two two
three-12345678 three
four-12345678 four
'''

        self.mock_execute(popen, ps_result, '', 0)

        names = list(self.runner.container_names())

        self.assert_execute(
            popen, ['docker', 'ps', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--format', '{{.Names}} {{.Label "container_name"}}']
        )
        self.assertEqual([
            ['one', 'one'],
            ['two-12345678', 'two'],
            ['two', 'two'],
            ['three-12345678', 'three'],
            ['four-12345678', 'four']
        ], names)

    @mock.patch('subprocess.Popen')
    def test_container_names_podman(self, popen):
        ps_result = '''one one
two-12345678 two
two two
three-12345678 three
four-12345678 four
'''

        self.mock_execute(popen, ps_result, '', 0)

        names = list(self.podman_runner.container_names())

        self.assert_execute(
            popen, ['podman', 'ps', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--format', '{{.Names}} {{.Labels.container_name}}']
        )
        self.assertEqual([
            ['one', 'one'],
            ['two-12345678', 'two'],
            ['two', 'two'],
            ['three-12345678', 'three'],
            ['four-12345678', 'four']
        ], names)

    @mock.patch('subprocess.Popen')
    def test_container_names_by_conf_id_docker(self, popen):
        ps_result = '''one one
two-12345678 two
'''

        self.mock_execute(popen, ps_result, '', 0)

        names = list(self.runner.container_names('abc'))

        self.assert_execute(
            popen, ['docker', 'ps', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--filter', 'label=config_id=abc',
                    '--format', '{{.Names}} {{.Label "container_name"}}']
        )
        self.assertEqual([
            ['one', 'one'],
            ['two-12345678', 'two']
        ], names)

    @mock.patch('subprocess.Popen')
    def test_container_names_by_conf_id_podman(self, popen):
        ps_result = '''one one
two-12345678 two
'''

        self.mock_execute(popen, ps_result, '', 0)

        names = list(self.podman_runner.container_names('abc'))

        self.assert_execute(
            popen, ['podman', 'ps', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--filter', 'label=config_id=abc',
                    '--format', '{{.Names}} {{.Labels.container_name}}']
        )
        self.assertEqual([
            ['one', 'one'],
            ['two-12345678', 'two']
        ], names)


class TestDockerRunner(TestBaseRunner):

    @mock.patch('subprocess.Popen')
    def test_rename_containers(self, popen):
        ps_result = '''one one
two-12345678 two
two two
three-12345678 three
four-12345678 four
'''

        self.mock_execute(popen, ps_result, '', 0)
        self.runner.rename_container = mock.Mock()

        self.runner.rename_containers()

        self.assert_execute(
            popen, ['docker', 'ps', '-a',
                    '--filter', 'label=managed_by=tester',
                    '--format', '{{.Names}} {{.Label "container_name"}}']
        )
        # only containers three-12345678 and four-12345678 four will be renamed
        self.runner.rename_container.assert_has_calls([
            mock.call('three-12345678', 'three'),
            mock.call('four-12345678', 'four')
        ], any_order=True)


class PodmanRunner(TestBaseRunner):

    @mock.patch('subprocess.Popen')
    def test_image_exist(self, popen):
        self.mock_execute(popen, '', '', 0)

        self.runner = runner.PodmanRunner('tester')
        self.runner.image_exist('one')
        self.assert_execute(
            popen, ['podman', 'image', 'exists', 'one']
        )
