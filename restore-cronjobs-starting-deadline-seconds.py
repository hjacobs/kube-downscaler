#!/usr/bin/env python3
"""Restore the startingDeadlineSeconds value from last-applied-configuration for all CronJobs."""
import argparse
import json

import pykube
from pykube import CronJob

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

api = pykube.HTTPClient(pykube.KubeConfig.from_env())
for cronjob in CronJob.objects(api).filter(namespace=pykube.all):
    if cronjob.obj["spec"].get("startingDeadlineSeconds") == 0:
        last_applied_config_json = cronjob.annotations.get(
            "kubectl.kubernetes.io/last-applied-configuration"
        )
        if last_applied_config_json:
            last_applied_config = json.loads(last_applied_config_json)
            original_value = last_applied_config["spec"].get("startingDeadlineSeconds")
            if original_value is None or original_value != 0:
                cronjob.obj["spec"]["startingDeadlineSeconds"] = original_value
                print(
                    f"Updating startingDeadlineSeconds for {cronjob.namespace}/{cronjob.name} to {original_value}.."
                )
                if not args.dry_run:
                    cronjob.update()
                else:
                    print("** DRY-RUN **")
