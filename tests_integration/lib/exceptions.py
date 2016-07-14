class PublicPortWaitTimeoutException(Exception):
    pass


class StatusWaitException(Exception):
    pass


class UnexpectedKubectlResponse(Exception):
    pass


class NonZeroRetCodeException(Exception):
    def __init__(self, message='', stdout=None, stderr=None, ret_code=None):
        self.stdout, self.stderr, self.ret_code = stdout, stderr, ret_code
        super(NonZeroRetCodeException, self).__init__(message)

    def __str__(self):
        return '\n'.join([self.message, self.stdout, self.stderr])


class NotEnoughFreeIPs(Exception):
    pass


class DiskNotFound(Exception):
    pass


class PipelineNotFound(Exception):
    pass


class PipelineInvalidName(Exception):
    pass


class PodNotFound(Exception):
    pass


class PodIsNotRunning(Exception):
    pass


class IncorrectPodDescription(Exception):
    pass


class PodIsNotRunning(Exception):
    pass


class CannotRestorePodWithMoreThanOneContainer(Exception):
    pass
