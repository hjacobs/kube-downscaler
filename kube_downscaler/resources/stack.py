from pykube.objects import NamespacedAPIObject
from pykube.objects import ReplicatedMixin


class Stack(NamespacedAPIObject, ReplicatedMixin):

    """Support the Stack resource (https://github.com/zalando-incubator/stackset-controller)."""

    version = "zalando.org/v1"
    endpoint = "stacks"
    kind = "Stack"

    def get_autoscaling_max_replicas(self):
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
        if "replicas" in self.obj["spec"]:
            return self.obj["spec"]["replicas"]
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
                    del self.obj["spec"]["replicas"]
            else:
                self.obj["spec"]["replicas"] = value
        else:
            # no autoscaling configured
            self.obj["spec"]["replicas"] = value
