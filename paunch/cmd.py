#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import collections

from cliff import command
from cliff import lister
import json
import yaml

import paunch

from paunch import utils


class Apply(command.Command):

    log = None

    def get_parser(self, prog_name):
        parser = super(Apply, self).get_parser(prog_name)
        parser.add_argument(
            '--file',
            metavar='<file>',
            required=True,
            help=('YAML or JSON file containing configuration data'),
        )
        parser.add_argument(
            '--label',
            metavar='<label=value>',
            dest='labels',
            default=[],
            action='append',
            help=('Extra labels to apply to containers in this config, in the '
                  'form --label label=value --label label2=value2.'),
        )
        parser.add_argument(
            '--managed-by',
            metavar='<name>',
            dest='managed_by',
            default='paunch',
            help=('Override the name of the tool managing the containers'),
        )
        parser.add_argument(
            '--config-id',
            metavar='<name>',
            dest='config_id',
            required=True,
            help=('ID to assign to containers'),
        )
        parser.add_argument(
            '--default-runtime',
            dest='default_runtime',
            default='podman',
            choices=['docker', 'podman'],
            help=('Default runtime for containers. Can be docker or podman.'),
        )
        parser.add_argument(
            '--container-log-path',
            dest='cont_log_path',
            default=None,
            help=('Absolute directory path for container log. Works only for '
                  'podman container engine')
        )
        parser.add_argument(
            '--healthcheck-disabled',
            dest='healthcheck_disabled',
            action='store_true',
            default=False,
            help=('Whether or not we disable the containers healthchecks')
        )
        return parser

    def take_action(self, parsed_args):
        (self.log, log_file, log_level) = \
            utils.common.configure_logging_from_args(__name__, self.app_args)
        labels = collections.OrderedDict()
        for l in parsed_args.labels:
            k, v = l.split(('='), 1)
            labels[k] = v

        with open(parsed_args.file, 'r') as f:
            config = yaml.safe_load(f)

        stdout, stderr, rc = paunch.apply(
            parsed_args.config_id,
            config,
            managed_by='paunch',
            labels=labels,
            cont_cmd=parsed_args.default_runtime,
            log_level=log_level,
            log_file=log_file,
            cont_log_path=parsed_args.cont_log_path,
            healthcheck_disabled=parsed_args.healthcheck_disabled
        )

        return rc


class Cleanup(command.Command):

    log = None

    def get_parser(self, prog_name):
        parser = super(Cleanup, self).get_parser(prog_name)
        parser.add_argument(
            'config_id',
            metavar='<config_id>',
            nargs='*',
            help=('Identifiers for the configs which still apply, all others '
                  'will be deleted.'),
        )
        parser.add_argument(
            '--managed-by',
            metavar='<name>',
            dest='managed_by',
            default='paunch',
            help=('Override the name of the tool managing the containers'),
        )
        parser.add_argument(
            '--default-runtime',
            dest='default_runtime',
            default='podman',
            choices=['docker', 'podman'],
            help=('Default runtime for containers. Can be docker or podman.'),
        )
        return parser

    def take_action(self, parsed_args):
        (self.log, log_file, log_level) = \
            utils.common.configure_logging_from_args(__name__, self.app_args)
        paunch.cleanup(
            parsed_args.config_id,
            managed_by=parsed_args.managed_by,
            cont_cmd=parsed_args.default_runtime,
            log_level=log_level,
            log_file=log_file
        )


class Delete(command.Command):

    log = None

    def get_parser(self, prog_name):
        parser = super(Delete, self).get_parser(prog_name)
        parser.add_argument(
            'config_id',
            nargs='*',
            metavar='<config_id>',
            help=('Identifier for the config to delete the containers for'),
        )
        parser.add_argument(
            '--managed-by',
            metavar='<name>',
            dest='managed_by',
            default='paunch',
            help=('Override the name of the tool managing the containers'),
        )
        parser.add_argument(
            '--default-runtime',
            dest='default_runtime',
            default='podman',
            choices=['docker', 'podman'],
            help=('Default runtime for containers. Can be docker or podman.'),
        )
        return parser

    def take_action(self, parsed_args):
        (self.log, log_file, log_level) = \
            utils.common.configure_logging_from_args(__name__, self.app_args)
        paunch.delete(
            parsed_args.config_id,
            parsed_args.managed_by,
            cont_cmd=parsed_args.default_runtime,
            log_level=log_level,
            log_file=log_file
        )


class Debug(command.Command):

    log = None

    def get_parser(self, prog_name):
        parser = super(Debug, self).get_parser(prog_name)
        parser.add_argument(
            '--file',
            metavar='<file>',
            required=True,
            help=('YAML or JSON file containing configuration data')
        )
        parser.add_argument(
            '--label',
            metavar='<label=value>',
            dest='labels',
            default=[],
            action='append',
            help=('Extra labels to apply to containers in this config, in the '
                  'form --label label=value --label label2=value2.'),
        )
        parser.add_argument(
            '--managed-by',
            metavar='<name>',
            dest='managed_by',
            default='paunch',
            help=('Override the name of the tool managing the containers')
        )
        parser.add_argument(
            '--action',
            metavar='<name>',
            dest='action',
            default='print-cmd',
            help=('Action can be one of: "dump-json", "dump-yaml", '
                  '"print-cmd", or "run"')
        )
        parser.add_argument(
            '--container',
            metavar='<name>',
            dest='container_name',
            required=True,
            help=('Name of the container you wish to manipulate')
        )
        parser.add_argument(
            '--interactive',
            dest='interactive',
            action='store_true',
            default=False,
            help=('Run container in interactive mode - modifies config and '
                  'execution of container')
        )
        parser.add_argument(
            '--shell',
            dest='shell',
            action='store_true',
            default=False,
            help=('Similar to interactive but drops you into a shell')
        )
        parser.add_argument(
            '--user',
            metavar='<name>',
            dest='user',
            default='',
            help=('Start container as the specified user')
        )
        parser.add_argument(
            '--overrides',
            metavar='<name>',
            dest='overrides',
            default='',
            help=('JSON configuration information used to override default '
                  'config values')
        )
        parser.add_argument(
            '--config-id',
            metavar='<name>',
            dest='config_id',
            required=False,
            default='debug',
            help=('ID to assign to containers')
        )
        parser.add_argument(
            '--default-runtime',
            dest='default_runtime',
            default='podman',
            choices=['docker', 'podman'],
            help=('Default runtime for containers. Can be docker or podman.'),
        )
        return parser

    def take_action(self, parsed_args):
        (self.log, log_file, log_level) = \
            utils.common.configure_logging_from_args(__name__, self.app_args)
        labels = collections.OrderedDict()
        for l in parsed_args.labels:
            k, v = l.split(('='), 1)
            labels[k] = v

        with open(parsed_args.file, 'r') as f:
            config = yaml.safe_load(f)

        container_name = parsed_args.container_name
        cconfig = {}
        cconfig[container_name] = config[container_name]

        if parsed_args.interactive or parsed_args.shell:
            iconfig = {
                "interactive": True,
                "tty": True,
                "restart": "no",
                "detach": False,
                "remove": True
                }
            cconfig[container_name].update(iconfig)
        if parsed_args.shell:
            sconfig = {"command": "/bin/bash"}
            cconfig[container_name].update(sconfig)
        if parsed_args.user:
            rconfig = {"user": parsed_args.user}
            cconfig[container_name].update(rconfig)

        conf_overrides = []
        if parsed_args.overrides:
            conf_overrides = json.loads(parsed_args.overrides)

        cconfig[container_name].update(conf_overrides)

        paunch.debug(
            parsed_args.config_id,
            container_name,
            parsed_args.action,
            cconfig,
            parsed_args.managed_by,
            labels=labels,
            cont_cmd=parsed_args.default_runtime,
            log_level=log_level,
            log_file=log_file
        )


class List(lister.Lister):

    log = None

    def get_parser(self, prog_name):
        parser = super(List, self).get_parser(prog_name)
        parser.add_argument(
            '--managed-by',
            metavar='<name>',
            dest='managed_by',
            default='paunch',
            help=('Override the name of the tool managing the containers'),
        )
        parser.add_argument(
            '--default-runtime',
            dest='default_runtime',
            default='podman',
            choices=['docker', 'podman'],
            help=('Default runtime for containers. Can be docker or podman.'),
        )
        return parser

    def take_action(self, parsed_args):
        (self.log, log_file, log_level) = \
            utils.common.configure_logging_from_args(__name__, self.app_args)
        configs = paunch.list(
            parsed_args.managed_by,
            cont_cmd=parsed_args.default_runtime,
            log_level=log_level,
            log_file=log_file
        )
        columns = [
            'config',
            'container',
            'image',
            'command',
            'status',
        ]
        data = []
        for k, v in configs.items():
            for i in v:
                # docker has a leading slash in the name, strip it
                if parsed_args.default_runtime == 'docker':
                    name = i.get('Name', '/')[1:]
                else:
                    name = i.get('Name', '')
                cmd = ' '.join(i.get('Config', {}).get('Cmd', []))
                image = i.get('Config', {}).get('Image')
                status = i.get('State', {}).get('Status')
                data.append((k, name, image, cmd, status))
        return columns, data
