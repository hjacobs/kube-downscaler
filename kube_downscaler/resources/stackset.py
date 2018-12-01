from pykube.objects import NamespacedAPIObject

from .scalable import Scalable


class StackSet(NamespacedAPIObject, Scalable):
    """
    Use latest workloads API version (apps/v1), pykube is stuck with old version
    """

    version = "zalando.org/v1"
    endpoint = "stacksets"
    kind = "StackSet"

    def set_replicas(self, count):
        self.obj['spec']['stackTemplate']['spec']['replicas'] = count

    def get_replicas(self):
        return int(self.obj['spec']['stackTemplate']['spec']['replicas'])
