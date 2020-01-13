from pykube.objects import NamespacedAPIObject
from pykube.objects import ReplicatedMixin
from pykube.objects import ScalableMixin


class Stack(NamespacedAPIObject, ReplicatedMixin, ScalableMixin):

    """Support the Stack resource (https://github.com/zalando-incubator/stackset-controller)."""

    version = "zalando.org/v1"
    endpoint = "stacks"
    kind = "Stack"
