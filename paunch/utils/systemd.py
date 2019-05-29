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

import os
import shutil

from paunch import constants
from paunch.utils import common
from paunch.utils import systemctl


def service_create(container, cconfig, sysdir=constants.SYSTEMD_DIR, log=None):
    """Create a service in systemd

    :param container: container name
    :type container: String

    :param cconfig: container configuration
    :type cconfig: Dictionary

    :param sysdir: systemd unit files directory
    :type sysdir: String

    :param log: optional pre-defined logger for messages
    :type log: logging.RootLogger
    """
    log = log or common.configure_logging(__name__)
    # We prefix the SystemD service so we can identify them better:
    # e.g. systemctl list-unit-files | grep tripleo_
    # It'll help to not conflict when rpms are installed on the host and
    # have the same service name as their container name.
    # For example haproxy rpm and haproxy container would have the same
    # service name so the prefix will help to not having this conflict
    # when removing the rpms during a cleanup by the operator.
    service = 'tripleo_' + container

    wants = " ".join(systemctl.format_name(str(x)) for x in
                     cconfig.get('depends_on', []))

    restart = cconfig.get('restart', 'always')
    stop_grace_period = cconfig.get('stop_grace_period', '10')

    # Please refer to systemd.exec documentation for those entries
    # https://www.freedesktop.org/software/systemd/man/systemd.exec.html
    sys_exec = cconfig.get('systemd_exec_flags', {})

    # SystemD doesn't have the equivalent of docker unless-stopped.
    # Let's force 'always' so containers aren't restarted when stopped by
    # systemd, but restarted when in failure. Also this code is only for
    # podman now, so nothing changed for Docker deployments.
    if restart == 'unless-stopped':
        restart = 'always'

    sysd_unit_f = sysdir + systemctl.format_name(service)
    log.debug('Creating systemd unit file: %s' % sysd_unit_f)
    s_config = {
        'name': container,
        'wants': wants,
        'restart': restart,
        'stop_grace_period': stop_grace_period,
        'sys_exec': '\n'.join(['%s=%s' % (x, y) for x, y in sys_exec.items()]),
    }
    # Ensure we don't have some trailing .requires directory and content for
    # this service
    if os.path.exists(sysd_unit_f + '.requires'):
        shutil.rmtree(sysd_unit_f + '.requires')

    with open(sysd_unit_f, 'w') as unit_file:
        os.chmod(unit_file.name, 0o644)
        unit_file.write("""[Unit]
Description=%(name)s container
After=paunch-container-shutdown.service
Wants=%(wants)s
[Service]
Restart=%(restart)s
ExecStart=/usr/bin/podman start %(name)s
ExecStop=/usr/bin/podman stop -t %(stop_grace_period)s %(name)s
KillMode=none
Type=forking
PIDFile=/var/run/%(name)s.pid
%(sys_exec)s
[Install]
WantedBy=multi-user.target""" % s_config)
    try:
        systemctl.daemon_reload()
        systemctl.enable(service, now=True)
    except systemctl.SystemctlException:
        log.exception("systemctl failed")
        raise


def service_delete(container, sysdir=constants.SYSTEMD_DIR, log=None):
    """Delete a service in systemd

    :param container: container name
    :type container: String

    :param sysdir: systemd unit files directory
    :type sysdir: string

    :param log: optional pre-defined logger for messages
    :type log: logging.RootLogger
    """
    log = log or common.configure_logging(__name__)
    # prefix is explained in the service_create().
    service = 'tripleo_' + container

    sysd_unit_f = systemctl.format_name(service)
    sysd_health_f = systemctl.format_name(service + '_healthcheck')
    sysd_timer_f = service + '_healthcheck.timer'
    sysd_health_req_d = sysd_unit_f + '.requires'

    for sysd_f in sysd_unit_f, sysd_health_f, sysd_timer_f:
        if os.path.isfile(sysdir + sysd_f):
            log.debug('Stopping and disabling systemd service for %s' %
                      service)
            try:
                systemctl.stop(sysd_f)
                systemctl.disable(sysd_f)
            except systemctl.SystemctlException:
                log.exception("systemctl failed")
                raise
            log.debug('Removing systemd unit file %s' % sysd_f)
            os.remove(sysdir + sysd_f)
        else:
            log.info('No systemd unit file was found for %s' % sysd_f)

    # Now that the service is removed, we can remove its ".requires"
    if os.path.exists(os.path.join(sysdir, sysd_health_req_d)):
            log.info('Removing healthcheck require for %s' % service)
            shutil.rmtree(os.path.join(sysdir, sysd_health_req_d))


def healthcheck_create(container, sysdir='/etc/systemd/system/',
                       log=None, test='/openstack/healthcheck'):
    """Create a healthcheck for a service in systemd

    :param container: container name
    :type container: String

    :param sysdir: systemd unit files directory
    :type sysdir: String

    :param log: optional pre-defined logger for messages
    :type log: logging.RootLogger

    :param test: optional test full command
    :type test: String
    """

    log = log or common.configure_logging(__name__)

    service = 'tripleo_' + container
    healthcheck = systemctl.format_name(service + '_healthcheck')
    sysd_unit_f = sysdir + healthcheck
    log.debug('Creating systemd unit file: %s' % sysd_unit_f)
    s_config = {
        'name': container,
        'service': service,
        'restart': 'restart',
        'test': test,
    }
    with open(sysd_unit_f, 'w') as unit_file:
        os.chmod(unit_file.name, 0o644)
        unit_file.write("""[Unit]
Description=%(name)s healthcheck
After=paunch-container-shutdown.service %(service)s.service
Requisite=%(service)s.service
[Service]
Type=oneshot
ExecStart=/usr/bin/podman exec %(name)s %(test)s
[Install]
WantedBy=multi-user.target
""" % s_config)


def healthcheck_timer_create(container, cconfig, sysdir='/etc/systemd/system/',
                             log=None):
    """Create a systemd timer for a healthcheck

    :param container: container name
    :type container: String

    :param cconfig: container configuration
    :type cconfig: Dictionary

    :param sysdir: systemd unit files directory
    :type sysdir: string

    :param log: optional pre-defined logger for messages
    :type log: logging.RootLogger
    """

    log = log or common.configure_logging(__name__)

    service = 'tripleo_' + container
    healthcheck_timer = service + '_healthcheck.timer'
    sysd_timer_f = sysdir + healthcheck_timer
    log.debug('Creating systemd timer file: %s' % sysd_timer_f)
    interval = cconfig.get('check_interval', 60)
    s_config = {
        'name': container,
        'service': service,
        'interval': interval,
        'randomize': int(interval) * 3 / 4
    }
    with open(sysd_timer_f, 'w') as timer_file:
        os.chmod(timer_file.name, 0o644)
        timer_file.write("""[Unit]
Description=%(name)s container healthcheck
PartOf=%(service)s.service
[Timer]
OnActiveSec=120
OnUnitActiveSec=%(interval)s
RandomizedDelaySec=%(randomize)s
[Install]
WantedBy=timers.target""" % s_config)
    try:
        systemctl.enable(healthcheck_timer, now=True)
        systemctl.add_requires(systemctl.format_name(service),
                               healthcheck_timer)
        systemctl.daemon_reload()
    except systemctl.SystemctlException:
        log.exception("systemctl failed")
        raise
