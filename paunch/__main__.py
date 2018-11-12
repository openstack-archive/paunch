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

import sys

from cliff.app import App
from cliff.commandmanager import CommandManager

import paunch


"""Utility to launch and manage containers using
YAML based configuration data"""


class PaunchApp(App):

    def __init__(self):
        super(PaunchApp, self).__init__(
            description=__doc__,
            version=paunch.__version__,
            command_manager=CommandManager('paunch'),
            deferred_help=True,
            )


def main(argv=sys.argv[1:]):
    myapp = PaunchApp()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
