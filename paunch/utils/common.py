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

import logging
import psutil
import sys


def get_cpus_allowed_list(**args):
    """Returns the process's Cpus_allowed on which CPUs may be scheduled.

    :return: Value for Cpus_allowed, e.g. '0-3'
    """
    return ','.join([str(c) for c in psutil.Process().cpu_affinity()])


def configure_logging(name, level=3, log_file=None):
    '''Mimic oslo_log default levels and formatting for the logger. '''
    log = logging.getLogger(name)

    if level and level > 2:
        ll = logging.DEBUG
    elif level and level == 2:
        ll = logging.INFO
    else:
        ll = logging.WARNING

    log.setLevel(ll)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(ll)
    if log_file:
        fhandler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d %(process)d %(levelname)s '
            '%(name)s [  ] %(message)s',
            '%Y-%m-%d %H:%M:%S')
        fhandler.setLevel(ll)
        fhandler.setFormatter(formatter)
        log.addHandler(fhandler)
        log.addHandler(handler)
        log.propagate = False

    return log
