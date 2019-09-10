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

import psutil


def get_cpus_allowed_list(**args):
    """Returns the process's Cpus_allowed on which CPUs may be scheduled.

    :return: Value for Cpus_allowed, e.g. '0-3'
    """
    return ','.join([str(c) for c in psutil.Process().cpu_affinity()])


def get_all_cpus(**args):
    """Returns a single list of all CPUs.

    :return: Value computed by psutil, e.g. '0-3'
    """
    return "0-" + str(psutil.cpu_count() - 1)
