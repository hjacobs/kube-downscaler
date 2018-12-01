import abc

DOWNSCALER_SAVED_ANNOTATION = 'kubedownscaler.org/saved'


class Scalable(abc.ABC):

    @abc.abstractmethod
    def set_replicas(self, count: int):
        pass

    @abc.abstractmethod
    def get_replicas(self):
        pass
