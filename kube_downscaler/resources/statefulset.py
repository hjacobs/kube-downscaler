from pykube.objects import NamespacedAPIObject

from .scalable import Scalable


class StatefulSet(NamespacedAPIObject, Scalable):
    """
    Use latest workloads API version (apps/v1), pykube is stuck with old version
    """

    version = "apps/v1"
    endpoint = "statefulsets"
    kind = "StatefulSet"

    def set_replicas(self, count):
        self.obj['spec']['replicas'] = count

    def get_replicas(self):
        return int(self.obj['spec']['replicas'])
