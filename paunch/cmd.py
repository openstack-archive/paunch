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
import logging

from cliff import command
from cliff import lister
import yaml

import paunch


class Apply(command.Command):

    log = logging.getLogger(__name__)

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
            help=('Extra labels to apply to containers in this config, in the '
                  'form label=value.'),
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
        return parser

    def take_action(self, parsed_args):

        labels = collections.OrderedDict()
        for l in parsed_args.labels:
            k, v = l.split(('='), 1)
            labels[k] = v

        with open(parsed_args.file, 'r') as f:
            config = yaml.safe_load(f)

        paunch.apply(
            parsed_args.config_id,
            config,
            managed_by='paunch',
            labels=labels
        )


class Cleanup(command.Command):

    log = logging.getLogger(__name__)

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
        return parser

    def take_action(self, parsed_args):
        paunch.cleanup(
            parsed_args.config_id,
            managed_by=parsed_args.managed_by
        )


class Delete(command.Command):

    log = logging.getLogger(__name__)

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
        return parser

    def take_action(self, parsed_args):
        paunch.delete(parsed_args.config_id, parsed_args.managed_by)


class List(lister.Lister):

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(List, self).get_parser(prog_name)
        parser.add_argument(
            '--managed-by',
            metavar='<name>',
            dest='managed_by',
            default='paunch',
            help=('Override the name of the tool managing the containers'),
        )
        return parser

    def take_action(self, parsed_args):
        configs = paunch.list(parsed_args.managed_by)
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
                name = i.get('Name', '/')[1:]  # strip the leading slash
                cmd = ' '.join(i.get('Config', {}).get('Cmd', []))
                image = i.get('Config', {}).get('Image')
                status = i.get('State', {}).get('Status')
                data.append((k, name, image, cmd, status))
        return columns, data
