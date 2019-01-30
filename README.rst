=====================
Kubernetes Downscaler
=====================

.. image:: https://travis-ci.org/hjacobs/kube-downscaler.svg?branch=master
   :target: https://travis-ci.org/hjacobs/kube-downscaler
   :alt: Travis CI Build Status

.. image:: https://coveralls.io/repos/github/hjacobs/kube-downscaler/badge.svg?branch=master;_=1
   :target: https://coveralls.io/github/hjacobs/kube-downscaler?branch=master
   :alt: Code Coverage

Scale down Kubernetes deployments and/or statefulsets during non-work hours.

Deployments are interchangeable by statefulset for this whole guide.

It will scale the deployment's replicas to zero if all of the following conditions are met:

* current time is not part of the "uptime" schedule or current time is part of the "downtime" schedule. The schedules are being evaluated in following order: 
    * ``downscaler/downtime`` annotation on the deployment/stateful set
    * ``downscaler/uptime`` annotation on the deployment/stateful sett
    * ``downscaler/downtime`` annotation on the deployment/stateful set's namespace
    * ``downscaler/uptime`` annotation on th deployment/stateful set's namespace
    * ``--default-uptime`` cli argument
    * ``--default-downtime`` cli argument
    * ``DEFAULT_UPTIME``environment variable
    * ``DEFAULT_DOWNTIME``environment variable
* the deployment's namespace is not part of the exclusion list (``kube-system`` is excluded by default)
* the deployment's name is not part of the exclusion list
* the deployment is not marked for exclusion (annotation ``downscaler/exclude: "true"``)
* there are no active pods that force the whole cluster into uptime (annotation ``downscaler/force-uptime: "true"``)



Example use cases:

* Deploy the downscaler to a test (non-prod) cluster with a default uptime or downtime time range to scale down all deployments during the night and weekend.
* Deploy the downscaler to a production cluster without any default uptime/downtime setting and scale down specific deployments by setting the ``downscaler/uptime`` (or ``downscaler/downtime``) annotation.
  This might be useful for internal tooling frontends which are only needed during work time.

You need to combine the downscaler with an elastic cluster autoscaler to actually **save cloud costs**.
The `official cluster autoscaler <https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler>`_ and the `kube-aws-autoscaler <https://github.com/hjacobs/kube-aws-autoscaler>`_ were tested to work fine with the downscaler.

Usage
=====

Deploy the downscaler into your cluster via (also works with Minikube):

.. code-block:: bash

    $ kubectl apply -f deploy/

The example configuration uses the ``--dry-run`` as a safety flag to prevent downscaling --- remove it to enable the downscaler, e.g. by editing the deployment:

.. code-block:: bash

    $ kubectl edit deploy kube-downscaler


Configuration
=============

The downscaler is configured via command line args, environment variables and/or Kubernetes annotations.

Time definitions (e.g. ``DEFAULT_UPTIME``) accept a comma separated list of specifications, e.g. the following configuration would downscale all deployments for non-work hours:

.. code-block:: bash

    DEFAULT_UPTIME="Mon-Fri 07:30-20:30 Europe/Berlin"

To only downscale during the weekend and already Friday after 20:00:

.. code-block:: bash

    DEFAULT_DOWNTIME="Sat-Sun 00:00-24:00 CET,Fri-Fri 20:00-24:00 CET'

Each time specification must have the format ``<WEEKDAY-FROM>-<WEEKDAY-TO-INCLUSIVE> <HH>:<MM>-<HH>:<MM> <TIMEZONE>``. The timezone value can be any `Olson timezone <https://en.wikipedia.org/wiki/Tz_database>`_, e.g. "US/Eastern", "PST" or "UTC".

Available command line options:

``--dry-run``
    Dry run mode: do not change anything, just print what would be done
``--debug``
    Debug mode: print more information
``--once``
    Run loop only once and exit
``--interval``
    Loop interval (default: 30s)
``--namespace``
    Namespace (default: all namespaces)
``--kind``
    Downscale resources of this kind (default: deployment)
``--default-uptime``
    Default time range to scale up for (default: always), can also be configured via environment variable ``DEFAULT_UPTIME`` or via the annotation ``downscaler/uptime`` on each deployment
``--default-downtime``
    Default time range to scale down for (default: never), can also be configured via environment variable ``DEFAULT_DOWNTIME`` or via the annotation ``downscaler/downtime`` on each deployment
``--exclude-namespaces``
    Exclude namespaces from downscaling (default: kube-system), can also be configured via environment variable ``EXCLUDE_NAMESPACES``
``--exclude-deployments``
    Exclude specific deployments from downscaling (default: kube-downscaler, downscaler), can also be configured via environment variable ``EXCLUDE_DEPLOYMENTS``
``--exclude-statefulsets``
    Exclude specific statefulsets from statefulsets, can also be configured via environment variable ``EXCLUDE_STATEFULSETS``

Namespace Defaults
==================

``DEFAULT_UPTIME``, ``DEFAULT_DOWNTIME`` and ``FORCE_UPTIME`` can also be configured using Namespace annotations. Where configured these values supersede the other global default values.

.. code-block:: yaml

    apiVersion: v1
    kind: Namespace
    metadata:
        name: foo
        labels:
            name: foo
        annotations:
            downscaler/uptime: Mon-Sun 06:00-21:00 Europe/Berlin

Following annotations are supported on the Namespace level: ``downscaler/uptime``, ``downscaler/downtime`` and ``downscaler/force-uptime``

Contributing
============

Easiest way to contribute is to provide feedback! We would love to hear what you like and what you think is missing.
Create an issue or `ping try_except_ on Twitter`_.

PRs are welcome. Please also have a look at `issues labeled with "help wanted"`_.


License
=======

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see http://www.gnu.org/licenses/.

.. _ping try_except_ on Twitter: https://twitter.com/try_except_
.. _issues labeled with "help wanted": https://github.com/hjacobs/kube-downscaler/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22
