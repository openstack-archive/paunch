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
import os
import sys

from paunch import constants
from paunch import utils


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
    handler = logging.StreamHandler(sys.stderr)
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


def configure_logging_from_args(name, app_args):
    # takes 1, or 2 if --verbose, or 4 - 5 if --debug
    log_level = (app_args.verbose_level +
                 int(app_args.debug) * 3)

    # if executed as root log to specified file or default log file
    if os.getuid() == 0:
        log_file = app_args.log_file or constants.LOG_FILE
    else:
        log_file = app_args.log_file

    log = utils.common.configure_logging(
        __name__, log_level, log_file)
    return (log, log_file, log_level)
