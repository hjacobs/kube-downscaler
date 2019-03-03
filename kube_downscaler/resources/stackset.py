from pykube.objects import NamespacedAPIObject


class StackSet(NamespacedAPIObject):
    """
    Support the StackSet resource (https://github.com/zalando-incubator/stackset-controller)
    """

    version = "zalando.org/v1"
    endpoint = "stacksets"
    kind = "StackSet"

    @property
    def replicas(self):
        return int(self.obj['spec']['stackTemplate']['spec']['replicas'])

    @replicas.setter
    def replicas(self, count):
        self.obj['spec']['stackTemplate']['spec']['replicas'] = count
