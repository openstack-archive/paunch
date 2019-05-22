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
import subprocess

from paunch.utils import common


class SystemctlException(Exception):
    pass


def systemctl(cmd, log=None):
    log = log or common.configure_logging(__name__)
    if not isinstance(cmd, list):
        raise SystemctlException("systemctl cmd passed must be a list")
    cmd.insert(0, 'systemctl')
    log.debug("Executing: {}".format(" ".join(cmd)))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as err:
        raise SystemctlException(str(err))


def format_name(name):
    return name if name.endswith('.service') else name + ".service"


def stop(service, log=None):
    systemctl(['stop', service], log)


def daemon_reload(log=None):
    systemctl(['daemon-reload'], log)


def enable(service, now=True, log=None):
    cmd = ['enable']
    if now:
        cmd.append('--now')
    cmd.append(service)
    systemctl(cmd, log)


def disable(service, log=None):
    systemctl(['disable', service], log)


def add_requires(target, units, log=None):
    cmd = ['add-requires', target]
    if isinstance(units, list):
        cmd.extend(units)
    else:
        cmd.append(units)
    systemctl(cmd, log)
