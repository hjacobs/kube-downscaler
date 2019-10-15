=====================
Kubernetes Downscaler
=====================

.. image:: https://travis-ci.org/hjacobs/kube-downscaler.svg?branch=master
   :target: https://travis-ci.org/hjacobs/kube-downscaler
   :alt: Travis CI Build Status

.. image:: https://coveralls.io/repos/github/hjacobs/kube-downscaler/badge.svg?branch=master;_=1
   :target: https://coveralls.io/github/hjacobs/kube-downscaler?branch=master
   :alt: Code Coverage

.. image:: 	https://img.shields.io/docker/pulls/hjacobs/kube-downscaler.svg
   :target: https://hub.docker.com/r/hjacobs/kube-downscaler
   :alt: Docker pulls

.. image:: https://img.shields.io/badge/calver-YY.MM.MICRO-22bfda.svg
   :target: http://calver.org/
   :alt: CalVer

Scale down Kubernetes deployments and/or statefulsets during non-work hours.

Deployments are interchangeable by statefulset for this whole guide.

It will scale down the deployment's replicas if all of the following conditions are met:

* current time is not part of the "uptime" schedule or current time is part of the "downtime" schedule. The schedules are being evaluated in following order:
    * ``downscaler/downscale-period`` or ``downscaler/downtime`` annotation on the deployment/stateful set
    * ``downscaler/upscale-period`` or ``downscaler/uptime`` annotation on the deployment/stateful set
    * ``downscaler/downscale-period`` or ``downscaler/downtime`` annotation on the deployment/stateful set's namespace
    * ``downscaler/upscale-period`` or ``downscaler/uptime`` annotation on the deployment/stateful set's namespace
    * ``--upscale-period`` or ``--default-uptime`` cli argument
    * ``--downscale-period`` or ``--default-downtime`` cli argument
    * ``UPSCALE_PERIOD`` or ``DEFAULT_UPTIME`` environment variable
    * ``DOWNSCALE_PERIOD`` or ``DEFAULT_DOWNTIME`` environment variable
* the deployment's namespace is not part of the exclusion list (``kube-system`` is excluded by default)
* the deployment's name is not part of the exclusion list
* the deployment is not marked for exclusion (annotation ``downscaler/exclude: "true"``)
* there are no active pods that force the whole cluster into uptime (annotation ``downscaler/force-uptime: "true"``)

The deployment by default will be scaled down to zero replicas. This can be configured with a deployment or its namespace's annotation of ``downscaler/downtime-replicas`` (e.g. ``downscaler/downtime-replicas: "1"``) or via CLI with ``--downtime-replicas``.

Example use cases:

* Deploy the downscaler to a test (non-prod) cluster with a default uptime or downtime time range to scale down all deployments during the night and weekend.
* Deploy the downscaler to a production cluster without any default uptime/downtime setting and scale down specific deployments by setting the ``downscaler/uptime`` (or ``downscaler/downtime``) annotation.
  This might be useful for internal tooling frontends which are only needed during work time.

You need to combine the downscaler with an elastic cluster autoscaler to actually **save cloud costs**.
The `official cluster autoscaler <https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler>`_ and the `kube-aws-autoscaler <https://github.com/hjacobs/kube-aws-autoscaler>`_ were tested to work fine with the downscaler.

Usage
=====

Deploy the downscaler into your cluster via (also works with kind_ or Minikube_):

.. code-block:: bash

    $ kubectl apply -f deploy/

In case you are deploying ``kube-downscaler`` to another namespace than ``default``, for example if your context is pointing to ``my-namespace``. Make
sure you change the ``deploy/rbac.yaml`` Service Account configuration ``namespace: default`` to the destination namespace ``my-namespace``, instead of ``default``.

The example configuration uses the ``--dry-run`` as a safety flag to prevent downscaling --- remove it to enable the downscaler, e.g. by editing the deployment:

.. code-block:: bash

    $ kubectl edit deploy kube-downscaler

The example deployment manifests come with a configured uptime (``deploy/config.yaml`` sets it to "Mon-Fri 07:30-20:30 CET"), you can overwrite this per namespace or deployment, e.g.:

.. code-block:: bash

    $ kubectl run nginx --image=nginx
    $ kubectl annotate deploy nginx 'downscaler/uptime=Mon-Fri 09:00-17:00 America/Buenos_Aires'

Note that the default grace period of 15 minutes applies to the new nginx deployment, i.e. if the current time is not within Mon-Fri 9-17 (Buenos Aires timezone), it will downscale not immediately, but after 15 minutes.
The downscaler will eventually log something like:

::

    INFO: Scaling down Deployment default/nginx from 1 to 0 replicas (uptime: Mon-Fri 09:00-17:00 America/Buenos_Aires, downtime: never)


Configuration
=============

The downscaler is configured via command line args, environment variables and/or Kubernetes annotations.

Time definitions (e.g. ``DEFAULT_UPTIME``) accept a comma separated list of specifications, e.g. the following configuration would downscale all deployments for non-work hours:

.. code-block:: bash

    DEFAULT_UPTIME="Mon-Fri 07:30-20:30 Europe/Berlin"

To only downscale during the weekend and Friday after 20:00:

.. code-block:: bash

    DEFAULT_DOWNTIME="Sat-Sun 00:00-24:00 CET,Fri-Fri 20:00-24:00 CET'

Each time specification can be in one of two formats:
- Recurring specifications have the format ``<WEEKDAY-FROM>-<WEEKDAY-TO-INCLUSIVE> <HH>:<MM>-<HH>:<MM> <TIMEZONE>``. The timezone value can be any `Olson timezone <https://en.wikipedia.org/wiki/Tz_database>`_, e.g. "US/Eastern", "PST" or "UTC".
- Absolute specifications have the format ``<TIME_FROM>-<TIME_TO>`` where each ``<TIME>`` is an ISO 8601 date
  and time of the format ``<YYYY>-<MM>-<DD>T<HH>:<MM>:<SS>[+-]<TZHH>:<TZMM>``.

Alternative logic, based on periods
===================================

Instead of strict uptimes or downtimes, you can chose time periods for upscaling or downscaling. The time definitions are the same. In this case, the upscale or downscale happens only on time periods, rest of times will be ignored.

If upscale or downscale periods are configured, uptime and downtime will be ignored. This means that some options are mutually exclusive, e.g. you can either use ``--downscale-period`` or ``--default-downtime``, but not both.

This definition will downscale your cluster between 19:00 and 20:00. If you upscale your cluster manually, it won't be scaled down until next day 19:00-20:00.

.. code-block:: bash

    DOWNSCALE_PERIOD="Mon-Sun 19:00-20:00 Europe/Berlin"

Command Line Options
====================

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
    Restrict the downscaler to work only in a single namespace (default: all namespaces). This is mainly useful for deployment scenarios where the deployer of kube-downscaler only has access to a given namespace (instead of cluster access).
``--include-resources``
    Downscale resources of this kind as comma separated list. [deployments, statefulsets, stacks] (default: deployments)
``--grace-period``
    Grace period in seconds for new deployments before scaling them down (default: 15min). The grace period counts from time of creation of the deployment, i.e. updated deployments will immediately be scaled down regardless of the grace period.
``--upscale-period``
    Alternative logic to scale up only in given period of time (default: never), can also be configured via environment variable ``UPSCALE_PERIOD`` or via the annotation ``downscaler/upscale-period`` on each deployment
``--downscale-period``
    Alternative logic to scale down only in given period of time (default: never), can also be configured via environment variable ``DOWNSCALE_PERIOD`` or via the annotation ``downscaler/downscale-period`` on each deployment
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
``--downtime-replicas``
    Default value of replicas to downscale to, the annotation ``downscaler/downtime-replicas`` takes precedence over this value.

Namespace Defaults
==================

``DEFAULT_UPTIME``, ``DEFAULT_DOWNTIME``, ``FORCE_UPTIME`` and exclusion can also be configured using Namespace annotations. Where configured these values supersede the other global default values.

.. code-block:: yaml

    apiVersion: v1
    kind: Namespace
    metadata:
        name: foo
        labels:
            name: foo
        annotations:
            downscaler/uptime: Mon-Sun 07:30-18:00 CET

The following annotations are supported on the Namespace level:

* ``downscaler/upscale-period``
* ``downscaler/downscale-period``
* ``downscaler/uptime``
* ``downscaler/downtime``
* ``downscaler/force-uptime``
* ``downscaler/exclude``
* ``downscaler/downtime-replicas``

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
.. _kind: https://kind.sigs.k8s.io/
.. _Minikube: https://github.com/kubernetes/minikube
