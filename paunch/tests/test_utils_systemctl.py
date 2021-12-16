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

from unittest import mock

from paunch.tests import base
from paunch.utils import systemctl


class TestUtilsSystemctl(base.TestCase):
    def setUp(self):
        super(TestUtilsSystemctl, self).setUp()
        self.r = mock.MagicMock()
        self.r.returncode = 0
        self.r.stdout = ''
        self.r.stderr = ''

    def test_format_service_name(self):
        expected = 'test.service'
        self.assertEqual(expected, systemctl.format_name('test'))
        self.assertEqual(expected, systemctl.format_name(expected))

    @mock.patch('subprocess.run', autospec=True)
    def test_stop(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        test = 'test'
        systemctl.stop(test)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'stop', test],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_daemon_reload(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        systemctl.daemon_reload()
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'daemon-reload'],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_is_active(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        self.assertTrue(systemctl.is_active('foo'))
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-active', '-q', 'foo'],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_is_active_inactive(self, mock_subprocess_run):
        self.r.returncode = 1
        mock_subprocess_run.return_value = self.r
        self.assertFalse(systemctl.is_active('foo'))
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-active', '-q', 'foo'],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_is_enabled(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        self.assertTrue(systemctl.is_enabled('foo'))
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', '-q', 'foo'],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_is_enabled_disabled(self, mock_subprocess_run):
        self.r.returncode = 1
        mock_subprocess_run.return_value = self.r
        self.assertFalse(systemctl.is_enabled('foo'))
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', '-q', 'foo'],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_enable(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        test = 'test'
        systemctl.enable(test, now=True)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', 'test'],
                      stderr=-1, stdout=-1, universal_newlines=True),
            mock.call(['systemctl', 'enable', '--now', test],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])
        mock_subprocess_run.reset_mock()
        systemctl.enable(test)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', 'test'],
                      stderr=-1, stdout=-1, universal_newlines=True),
            mock.call(['systemctl', 'enable', '--now', test],
                      stderr=-1, stdout=-1, universal_newlines=True),
        ])
        mock_subprocess_run.reset_mock()
        systemctl.enable(test, now=False)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', 'test'],
                      stderr=-1, stdout=-1, universal_newlines=True),
            mock.call(['systemctl', 'enable', test],
                      stderr=-1, stdout=-1, universal_newlines=True),
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_enable_masked(self, mock_subprocess_run):
        f = mock.MagicMock()
        f.returncode = 42
        f.stdout = 'masked-runtime'
        f.stderr = ''
        mock_subprocess_run.return_value = f
        test = 'test'
        self.assertRaises(systemctl.SystemctlMaskedException,
                          systemctl.enable, test, True)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', 'test'],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])

    @mock.patch('subprocess.run', autospec=True)
    @mock.patch('tenacity.wait.wait_random_exponential.__call__',
                return_value=0)
    def test_enable_failed(self, mock_wait, mock_subprocess_run):
        f = mock.MagicMock()
        f.returncode = 42
        f.stdout = 'foo'
        f.stderr = 'fail fail fail'
        mock_subprocess_run.side_effect = f
        test = 'test'
        self.assertRaises(systemctl.SystemctlException,
                          systemctl.enable, test)

    @mock.patch('subprocess.run', autospec=True)
    def test_disable(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        test = 'test'
        systemctl.disable(test)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'disable', test],
                      stderr=-1, stdout=-1, universal_newlines=True),
        ])

    @mock.patch('subprocess.run', autospec=True)
    def test_add_requires(self, mock_subprocess_run):
        mock_subprocess_run.return_value = self.r
        test = 'test'
        requires = "foo"
        systemctl.add_requires(test, requires)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', 'test'],
                      stderr=-1, stdout=-1, universal_newlines=True),
            mock.call(['systemctl', 'add-requires', test, requires],
                      stderr=-1, stdout=-1, universal_newlines=True),
        ])
        requires = ["foo", "bar"]
        mock_subprocess_run.reset_mock()
        systemctl.add_requires(test, requires)
        mock_subprocess_run.assert_has_calls([
            mock.call(['systemctl', 'is-enabled', 'test'],
                      stderr=-1, stdout=-1, universal_newlines=True),
            mock.call(['systemctl', 'add-requires', test, "foo", "bar"],
                      stderr=-1, stdout=-1, universal_newlines=True)
        ])
