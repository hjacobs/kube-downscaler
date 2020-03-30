from pykube.objects import NamespacedAPIObject
from pykube.objects import ReplicatedMixin


class Stack(NamespacedAPIObject, ReplicatedMixin):

    """Support the Stack resource (https://github.com/zalando-incubator/stackset-controller)."""

    version = "zalando.org/v1"
    endpoint = "stacks"
    kind = "Stack"

    def get_autoscaling_max_replicas(self):
        """Return the Stack's HPA maxReplicas property or None if no autoscaling is configured."""
        spec = self.obj["spec"]
        if "autoscaler" in spec:
            # see https://github.com/zalando-incubator/stackset-controller/blob/2baddca617e2b76e34976357765206280cfd382e/pkg/apis/zalando.org/v1/types.go#L116
            return int(spec["autoscaler"].get("maxReplicas", 0))
        elif "horizontalPodAutoscaler" in spec:
            # see https://github.com/zalando-incubator/stackset-controller/blob/2baddca617e2b76e34976357765206280cfd382e/pkg/apis/zalando.org/v1/types.go#L139
            return int(spec["horizontalPodAutoscaler"].get("maxReplicas", 0))
        return None

    @property
    def replicas(self):
        replicas = self.obj["spec"].get("replicas")
        if replicas is not None:
            return replicas
        else:
            return self.get_autoscaling_max_replicas()

    @replicas.setter
    def replicas(self, value):
        max_replicas = self.get_autoscaling_max_replicas()
        if max_replicas is not None:
            if value == max_replicas:
                # reset to autoscaling
                if "replicas" in self.obj["spec"]:
                    # => remove manual replica count
                    # note that we set 'None' instead of deleting the property
                    # (because of strategic object merge)
                    self.obj["spec"]["replicas"] = None
            else:
                # downscale to the given value
                self.obj["spec"]["replicas"] = value
        else:
            # no autoscaling configured
            # => we can use the replicas property directly
            self.obj["spec"]["replicas"] = value
