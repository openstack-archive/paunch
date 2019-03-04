======
paunch
======

Utility to launch and manage containers using YAML based configuration data

* Free software: Apache license
* Documentation: https://docs.openstack.org/developer/paunch
* Source: https://git.openstack.org/cgit/openstack/paunch
* Bugs: https://bugs.launchpad.net/paunch
* Release Notes: https://docs.openstack.org/releasenotes/paunch

Features
--------

* Single host only, operations are performed via the podman client.
* Zero external state, only labels on running containers are used when
  determining which containers an operation will perform on.
* Single threaded and blocking, containers which are not configured to detach
  will halt further configuration until they exit.
* Co-exists with other container configuration tools. Only containers created
  by paunch will be modified by paunch. Unique container names are assigned if
  the desired name is taken, and containers are renamed when the desired name
  becomes available.
* Accessable via the ``paunch`` command line utility, or by importing python
  package ``paunch``.
* Builtin ``debug`` command lets you see how individual containers are run,
  get configuration information for them, and run them any way you need to.

Running Paunch Commands
-----------------------

The only state that paunch is aware of is the labels that it sets on running
containers, so it is up to the user to keep track of what paunch configs
*should* be running so that others can be deleted on cleanup. For these
examples we're going to store that state in a simple text file:

::

    $ touch paunch-state.txt

We'll start of by deleting any containers that were started by previous calls
to ``paunch apply``:

::

    $ paunch --verbose cleanup $(cat paunch-state.txt)

Next we'll apply a simple hello-world config found in
``examples/hello-world.yml`` which contains the following:

::

    hello:
      image: hello-world
      detach: false

Applied by running:

::

    $ paunch --verbose apply --file examples/hello-world.yml --config-id hi
    $ echo hi >> paunch-state.txt

A container called ``hello`` will be created, print a Hello World message, then
exit. You can confirm that it still exists by running ``podman ps -a``.

Now lets try running the exact same ``paunch apply`` command:

::

    $ paunch --verbose apply --file examples/hello-world.yml --config-id hi

This will not make any changes at all due to the idempotency behaviour of
paunch.

Lets try again with a unique --config-id:

::

    $ paunch --verbose apply --file examples/hello-world.yml --config-id hi-again
    $ echo hi-again >> paunch-state.txt

Doing a ``podman ps -a`` now will show that there are now 2 containers, one
called ``hello`` and the other called ``hello-(random suffix)``. Lets delete the
one associated with the ``hi`` config-id:

::

    $ cat paunch-state.txt
    $ echo hi-again > paunch-state.txt
    $ cat paunch-state.txt
    $ paunch --verbose cleanup $(cat paunch-state.txt)

Doing a ``podman ps -a`` will show that the original ``hello`` container has been
deleted and ``hello-(random suffix)`` has been renamed to ``hello``

Generally ``paunch cleanup`` will be run first to delete containers for configs
that are no longer apply. Then a series of ``paunch apply`` commands can be run.
If these ``apply`` calls are part of a live upgrade where a mixture of old and
new containers are left running, the upgrade can be completed in the next run
to ``paunch cleanup`` with the updated list of config-id state.

Paunch can also be used as a library by other tools. By default running the
``paunch`` command won't affect these other containers due to the different ``managed_by``
label being set on those containers. For example if you wanted to run paunch
commands masquerading as the
`heat-agents <https://git.openstack.org/cgit/openstack/heat-agents/tree/>`_
`docker-cmd hook <https://git.openstack.org/cgit/openstack/heat-agents/tree/heat-config-docker-cmd>`_
then you can run:

::

  paunch --verbose apply --file examples/hello-world.yml --config-id hi --managed-by docker-cmd

This will result in a ``hello`` container being run, which will be deleted the
next time the ``docker-cmd`` hook does its own ``cleanup`` run since it won't
be aware of a ``config_id`` called ``hi``.

Idempotency Behaviour
---------------------

In many cases the user will want to use the same --config-id with changed
config data.  The aim of the idempotency behaviour is to leave containers
running when their config has not changed, but replace containers which have
modified config.

When ``paunch apply`` is run with the same ``--config-id`` but modified config
data, the following logic is applied:

* For each existing container with a matching config_id and managed_by:
  * delete containers which no longer exist in config
  * delete containers with missing config_data label
  * delete containers where config_data label differs from current config
* Do a full rename to desired names since deletes have occured
* Only create containers from config if there is no container running with that name
* ``exec`` actions will be run regardless, so commands they run may require
  their own idempotency behaviour

Only configuration data is used to determine whether something has changed to
trigger replacing the container during ``apply``. This means that changing the
contents of a file referred to in ``env_file`` will *not* trigger replacement
unless something else changes in the configuration data (such as the path
specified in ``env_file``).

The most common reason to restart containers is to have them running with an
updated image. As such it is recommended that stable image tags such as
``latest`` are not used when specifying the ``image``, and that changing the
release version tag in the configuration data is the recommended way of
propagating image changes to the running containers.

Debugging with Paunch
---------------------

The ``paunch debug`` command allows you to perform specific actions on a given
container.  This can be used to:

* Run a container with a specific configuration.
* Dump the configuration of a given container in either json or yaml.
* Output the podman command line used to start the container.
* Run a container with any configuration additions you wish such that you can
  run it with a shell as any user etc.

The configuration options you will likely be interested in here include:

::

  --file <file>         YAML or JSON file containing configuration data
  --action <name>       Action can be one of: "dump-json", "dump-yaml",
                        "print-cmd", or "run"
  --container <name>    Name of the container you wish to manipulate
  --interactive         Run container in interactive mode - modifies config
                        and execution of container
  --shell               Similar to interactive but drops you into a shell
  --user <name>         Start container as the specified user
  --overrides <name>    JSON configuration information used to override
                        default config values

``file`` is the name of the configuration file to use
containing the configuration for the container you wish to use.

Here is an example of using ``paunch debug`` to start a root shell inside the
test container:

::

  # paunch debug --file examples/hello-world.yml --interactive --shell --user root --container hello --action run

This will drop you an interactive session inside the hello world container
starting /bin/bash running as root.

To see how this container is started normally:

::

  # paunch debug --file examples/hello-world.yml --container hello --action print-cmd

You can also dump the configuration of this to a file so you can edit
it and rerun it with different a different configuration.  This is more
useful when there are multiple configurations in a single file:

::

  # paunch debug --file examples/hello-world.yml --container hello --action dump-json > hello.json

You can then use ``hello.json`` as your ``--file`` argument after
editing it to your liking.

You can also add any configuration elements you wish on the command line
to test paunch or debug containers etc.  In this example I'm running
the hello container with ``net=host``.

::

  # paunch debug --file examples/hello-world.yml --overrides '{"net": "host"}' --container hello --action run


Configuration Format
--------------------

The current format is loosely based on a subset of the `docker-compose v1
format <https://docs.docker.com/compose/compose-file/compose-file-v1/>`_ with
modifications. The intention is for the format to evolve to faithfully
implement existing formats such as the
`Kubernetes Pod format <https://kubernetes.io/docs/concepts/workloads/pods/pod/>`_.

The top-level of the YAML format is a dict where the keys (generally)
correspond to the name of the container to be created.  The following config
creates 2 containers called ``hello1`` and ``hello2``:

::

    hello1:
      image: hello-world
    hello2:
      image: hello-world

The values are a dict which specifies the arguments that are used when the
container is launched. Supported keys which comply with the docker-compose v1
format are as follows:

command:
  String or list. Overrides the default command.

detach:
  Boolean, defaults to true. If true the container is run in the background. If
  false then paunch will block until the container has exited.

environment:
  List of the format ['KEY1=value1', 'KEY2=value2']. Sets environment variables
  that are available to the process launched in the container.

env_file:
  List of file paths containing line delimited environment variables.

image:
  String, mandatory. Specify the image to start the container from. Can either
  be a repositorys/tag or a partial image ID.

net:
  String. Set the network mode for the container.

pid:
  String. Set the PID mode for the container.

uts:
  String. Set the UTS namespace for the container.

privileged:
  Boolean, defaults to false. If true, give extended privileges to this container.

restart:
  String. Restart policy to apply when a container exits.

remove:
  Boolean: Remove container after running.

interactive:
  Boolean: Run container in interactive mode.

tty:
  Boolean: Allocate a tty to interact with the container.

user:
  String. Sets the username or UID used and optionally the groupname or GID for
  the specified command.

volumes:
  List of strings. Specify the bind mount for this container.

volumes_from:
  List of strings. Mount volumes from the specified container(s).

log_tag:
  String. Set the log tag for the specified container.
