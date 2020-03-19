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

import glob
import logging
import os
import psutil
import re
import sys
import yaml

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


def get_cpus_allowed_list(**args):
    """Returns the process's Cpus_allowed on which CPUs may be scheduled.

    :return: Value for Cpus_allowed, e.g. '0-3'
    """
    return ','.join([str(c) for c in psutil.Process().cpu_affinity()])


def load_config(config, name=None, overrides=None):
    container_config = {}
    if overrides is None:
        overrides = {}
    if os.path.isdir(config):
        # When the user gives a config directory and specify a container name,
        # we return the container config for that specific container.
        if name:
            cf = 'hashed-' + name + '.json'
            with open(os.path.join(config, cf), 'r') as f:
                container_config[name] = {}
                container_config[name].update(yaml.safe_load(f))
        # When the user gives a config directory and without container name,
        # we return all container configs in that directory.
        else:
            config_files = glob.glob(os.path.join(config, 'hashed-*.json'))
            for cf in config_files:
                with open(os.path.join(config, cf), 'r') as f:
                    name = os.path.basename(os.path.splitext(
                        cf.replace('hashed-', ''))[0])
                    container_config[name] = {}
                    container_config[name].update(yaml.safe_load(f))
    else:
        # Backward compatibility so our users can still use the old path,
        # paunch will recognize it and find the right container config.
        old_format = '/var/lib/tripleo-config/hashed-container-startup-config'
        if config.startswith(old_format):
            step = re.search('/var/lib/tripleo-config/'
                             'hashed-container-startup-config-step'
                             '_(.+).json', config).group(1)
            # If a name is specified, we return the container config for that
            # specific container.
            if name:
                new_path = os.path.join(
                    '/var/lib/tripleo-config/container_startup_config',
                    'step_' + step, 'hashed-' + name + '.json')
                with open(new_path, 'r') as f:
                    c_config = yaml.safe_load(f)
                    container_config[name] = {}
                    container_config[name].update(c_config[name])
            # When no name is specified, we return all container configs in
            # the file.
            else:
                new_path = os.path.join(
                    '/var/lib/tripleo-config/container_startup_config',
                    'step_' + step)
                config_files = glob.glob(os.path.join(new_path,
                                                      'hashed-*.json'))
                for cf in config_files:
                    with open(os.path.join(new_path, cf), 'r') as f:
                        name = os.path.basename(os.path.splitext(
                            cf.replace('hashed-', ''))[0])
                        c_config = yaml.safe_load(f)
                        container_config[name] = {}
                        container_config[name].update(c_config[name])
        # When the user gives a file path, that isn't the old format,
        # we consider it's the new format so the file name is the container
        # name.
        else:
            if not name:
                # No name was given, we'll guess it with file name
                name = os.path.basename(os.path.splitext(
                    config.replace('hashed-', ''))[0])
            with open(os.path.join(config), 'r') as f:
                container_config[name] = {}
                container_config[name].update(yaml.safe_load(f))

    # Overrides
    for k in overrides.keys():
        if k in container_config:
            for mk, mv in overrides[k].items():
                container_config[k][mk] = mv

    return container_config
