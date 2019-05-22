# Copyright 2018 Red Hat, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock

from paunch.tests import base
from paunch.utils import systemctl


class TestUtilsSystemctl(base.TestCase):

    def test_format_service_name(self):
        expected = 'test.service'
        self.assertEqual(expected, systemctl.format_name('test'))
        self.assertEqual(expected, systemctl.format_name(expected))

    @mock.patch('subprocess.check_call', autospec=True)
    def test_stop(self, mock_subprocess_check_call):
        test = 'test'
        systemctl.stop(test)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'stop', test]),
        ])

    @mock.patch('subprocess.check_call', autospec=True)
    def test_daemon_reload(self, mock_subprocess_check_call):
        systemctl.daemon_reload()
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'daemon-reload']),
        ])

    @mock.patch('subprocess.check_call', autospec=True)
    def test_enable(self, mock_subprocess_check_call):
        test = 'test'
        systemctl.enable(test, now=True)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'enable', '--now', test]),
        ])
        systemctl.enable(test)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'enable', '--now', test]),
        ])
        systemctl.enable(test, now=False)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'enable', test]),
        ])

    @mock.patch('subprocess.check_call', autospec=True)
    def test_disable(self, mock_subprocess_check_call):
        test = 'test'
        systemctl.disable(test)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'disable', test]),
        ])

    @mock.patch('subprocess.check_call', autospec=True)
    def test_add_requires(self, mock_subprocess_check_call):
        test = 'test'
        requires = "foo"
        systemctl.add_requires(test, requires)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'add-requires', test, requires]),
        ])
        requires = ["foo", "bar"]
        systemctl.add_requires(test, requires)
        mock_subprocess_check_call.assert_has_calls([
            mock.call(['systemctl', 'add-requires', test, "foo", "bar"]),
        ])
