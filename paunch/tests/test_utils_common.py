# Copyright 2019 Red Hat, Inc.
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
from paunch.utils import common


class TestUtilsCommonCpu(base.TestCase):

    @mock.patch("psutil.Process.cpu_affinity", return_value=[0, 1, 2, 3])
    def test_get_cpus_allowed_list(self, mock_cpu):
        expected_list = '0,1,2,3'
        actual_list = common.get_cpus_allowed_list()
        self.assertEqual(actual_list, expected_list)


class TestUtilsCommonConfig(base.TestCase):

    def setUp(self):
        super(TestUtilsCommonConfig, self).setUp()
        self.config_content = "{'image': 'docker.io/haproxy'}"
        self.config_override = {'haproxy': {'image': 'quay.io/haproxy'}}
        self.open_func = 'paunch.utils.common.open'
        self.expected_config = {'haproxy': {'image': 'docker.io/haproxy'}}
        self.expected_config_over = {'haproxy': {'image': 'quay.io/haproxy'}}
        self.container = 'haproxy'
        self.old_config_file = '/var/lib/tripleo-config/' + \
                               'hashed-container-startup-config-step_1.json'
        self.old_config_content = "{'haproxy': {'image': 'docker.io/haproxy'}}"

    @mock.patch('os.path.isdir')
    def test_load_config_dir_with_name(self, mock_isdir):
        mock_isdir.return_value = True
        mock_open = mock.mock_open(read_data=self.config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config,
                common.load_config('/config_dir', self.container))

    @mock.patch('os.path.isdir')
    @mock.patch('glob.glob')
    def test_load_config_dir_without_name(self, mock_glob, mock_isdir):
        mock_isdir.return_value = True
        mock_glob.return_value = ['hashed-haproxy.json']
        mock_open = mock.mock_open(read_data=self.config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config,
                common.load_config('/config_dir'))

    @mock.patch('os.path.isdir')
    def test_load_config_file_with_name(self, mock_isdir):
        mock_isdir.return_value = False
        mock_open = mock.mock_open(read_data=self.config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config,
                common.load_config('/config_dir/haproxy.json', self.container))

    @mock.patch('os.path.isdir')
    def test_load_config_file_without_name(self, mock_isdir):
        mock_isdir.return_value = False
        mock_open = mock.mock_open(read_data=self.config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config,
                common.load_config('/config_dir/haproxy.json'))

    @mock.patch('os.path.isdir')
    def test_load_config_file_backward_compat_with_name(self, mock_isdir):
        mock_isdir.return_value = False
        mock_open = mock.mock_open(read_data=self.old_config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config,
                common.load_config(self.old_config_file, self.container))

    @mock.patch('os.path.isdir')
    @mock.patch('glob.glob')
    def test_load_config_file_backward_compat_without_name(self, mock_glob,
                                                           mock_isdir):
        mock_isdir.return_value = False
        mock_glob.return_value = ['hashed-haproxy.json']
        mock_open = mock.mock_open(read_data=self.old_config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config,
                common.load_config(self.old_config_file))

    @mock.patch('os.path.isdir')
    def test_load_config_dir_with_name_and_override(self, mock_isdir):
        mock_isdir.return_value = True
        mock_open = mock.mock_open(read_data=self.config_content)
        with mock.patch(self.open_func, mock_open):
            self.assertEqual(
                self.expected_config_over,
                common.load_config('/config_dir', self.container,
                                   self.config_override))
