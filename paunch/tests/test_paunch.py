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

import paunch
from paunch.tests import base


class TestPaunch(base.TestCase):

    @mock.patch('paunch.builder.compose1.ComposeV1Builder', autospec=True)
    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_apply(self, runner, builder):
        paunch.apply('foo', {'bar': 'baz'}, 'tester')
        runner.assert_called_once_with('tester', docker_cmd=None)
        builder.assert_called_once_with(
            config_id='foo',
            config={'bar': 'baz'},
            runner=runner.return_value,
            labels=None
        )
        builder.return_value.apply.assert_called_once_with()

    @mock.patch('paunch.builder.compose1.ComposeV1Builder', autospec=True)
    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_apply_labels(self, runner, builder):
        paunch.apply(
            config_id='foo',
            config={'bar': 'baz'},
            managed_by='tester',
            labels={'bink': 'boop'})

        runner.assert_called_once_with('tester', docker_cmd=None)
        builder.assert_called_once_with(
            config_id='foo',
            config={'bar': 'baz'},
            runner=runner.return_value,
            labels={'bink': 'boop'}
        )
        builder.return_value.apply.assert_called_once_with()

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_cleanup(self, runner):
        paunch.cleanup(['foo', 'bar'], 'tester')
        runner.assert_called_once_with('tester', docker_cmd=None)
        runner.return_value.delete_missing_configs.assert_called_once_with(
            ['foo', 'bar'])
        runner.return_value.rename_containers.assert_called_once_with()

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_list(self, runner):
        paunch.list('tester')
        runner.assert_called_once_with('tester', docker_cmd=None)
        runner.return_value.list_configs.assert_called_once_with()

    @mock.patch('paunch.runner.DockerRunner', autospec=True)
    def test_delete(self, runner):
        paunch.delete(['foo', 'bar'], 'tester')
        runner.assert_called_once_with('tester', docker_cmd=None)
        runner.return_value.remove_containers.assert_has_calls([
            mock.call('foo'), mock.call('bar')
        ])

    @mock.patch('paunch.builder.compose1.ComposeV1Builder', autospec=True)
    @mock.patch('paunch.runner.DockerRunner')
    def test_debug(self, runner, builder):
        paunch.debug('foo', 'testcont', 'run', {'bar': 'baz'}, 'tester',
                     docker_cmd='docker')
        builder.assert_called_once_with(
            config_id='foo',
            config={'bar': 'baz'},
            runner=runner.return_value,
            labels=None
        )
        runner.assert_called_once_with('tester', docker_cmd='docker')
