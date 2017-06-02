======
paunch
======

Utility to launch and manage containers using YAML based configuration data

* Free software: Apache license
* Documentation: https://docs.openstack.org/developer/paunch
* Source: http://git.openstack.org/cgit/openstack/paunch
* Bugs: http://bugs.launchpad.net/paunch

Features
--------

* Single host only, operations are performed via the docker client on the
  currently configured docker service.
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
exit. You can confirm that it still exists by running ``docker ps -a``.

Now lets try running the exact same ``paunch apply`` command:

::

    $ paunch --verbose apply --file examples/hello-world.yml --config-id hi

This will not make any changes at all due to the idempotency behaviour of
paunch.

Lets try again with a unique --config-id:

::

    $ paunch --verbose apply --file examples/hello-world.yml --config-id hi-again
    $ echo hi-again >> paunch-state.txt

Doing a ``docker ps -a`` now will show that there are now 2 containers, one
called ``hello`` and the other called ``hello-(random suffix)``. Lets delete the
one associated with the ``hi`` config-id:

::

    $ cat paunch-state.txt
    $ echo hi-again > paunch-state.txt
    $ cat paunch-state.txt
    $ paunch --verbose cleanup $(cat paunch-state.txt)

Doing a ``docker ps -a`` will show that the original ``hello`` container has been
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
`heat-agents <http://git.openstack.org/cgit/openstack/heat-agents/tree/>`_
`docker-cmd hook <http://git.openstack.org/cgit/openstack/heat-agents/tree/heat-config-docker-cmd>`_
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

privileged:
  Boolean, defaults to false. If true, give extended privileges to this container.

restart:
  String. Restart policy to apply when a container exits.

user:
  String. Sets the username or UID used and optionally the groupname or GID for
  the specified command.

volumes:
  List of strings. Specify the bind mount for this container.

volumes_from:
  List of strings. Mount volumes from the specified container(s).
