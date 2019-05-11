from pykube.objects import NamespacedAPIObject, ReplicatedMixin, ScalableMixin


class Stack(NamespacedAPIObject, ReplicatedMixin, ScalableMixin):
    """
    Support the Stack resource (https://github.com/zalando-incubator/stackset-controller)
    """

    version = "zalando.org/v1"
    endpoint = "stacks"
    kind = "Stack"
