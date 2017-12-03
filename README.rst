=====================
Kubernetes Downscaler
=====================

.. image:: https://travis-ci.org/hjacobs/kube-downscaler.svg?branch=master
   :target: https://travis-ci.org/hjacobs/kube-downscaler
   :alt: Travis CI Build Status

.. image:: https://coveralls.io/repos/github/hjacobs/kube-downscaler/badge.svg?branch=master;_=1
   :target: https://coveralls.io/github/hjacobs/kube-downscaler?branch=master
   :alt: Code Coverage

Scale down Kubernetes deployments during non-work hours.
The downscaler checks all deployments in the cluster every 5 minutes.
It will scale the deployment's replicas to zero if all of the following conditions are met:

* current time is not part of the "uptime" schedule (annotation ``downscaler/uptime``) or current time is part of the "downtime" schedule (``downscaler/downtime``)
* the deployment's namespace is not part of the exclusion list (``kube-system`` is excluded by default)
* the deployment's name is not part of the exclusion list
* the deployment is not marked for exclusion (annotation ``downscaler/exclude: "true"``)


Usage
=====

Deploy the downscaler into your cluster via:

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
    Loop interval (default: 300s)
``--namespace``
    Namespace (default: all namespaces)
``--default-uptime``
    Default time range to scale up for (default: always), can also be configured via environment variable ``DEFAULT_UPTIME`` or via the annotation ``downscaler/uptime`` on each deployment
``--default-downtime``
    Default time range to scale down for (default: never), can also be configured via environment variable ``DEFAULT_DOWNTIME`` or via the annotation ``downscaler/downtime`` on each deployment
``--exclude-namespaces``
    Exclude namespaces from downscaling (default: kube-system), can also be configured via environment variable ``EXCLUDE_NAMESPACES``
``--exclude-deployments``
    Exclude specific deployments from downscaling (default: kube-downscaler,downscaler), env var ``EXCLUDE_DEPLOYMENTS``
