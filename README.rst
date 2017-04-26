===============================
paunch
===============================

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
* Accessable via the `paunch` command line utility, or by importing python
  package `paunch`.

Configuration Format
--------------------

The current format is loosely based on a subset of the `docker-compose v1
format <https://docs.docker.com/compose/compose-file/compose-file-v1/>`_ with
modifications. The intention is for the format to evolve to faithfully
implement existing formats such as the
`Kubernetes Pod format <https://kubernetes.io/docs/concepts/workloads/pods/pod/>`_.


