class ClusterAlreadyCreated(Exception):
    pass


class PublicPortWaitTimeoutException(Exception):
    pass


class StatusWaitException(Exception):

    def __init__(self, expected, actual, timeout):
        super(StatusWaitException, self).__init__()
        self.expected = expected
        self.actual = actual
        self.timeout = timeout

    def __str__(self):
        return "Wait {} but get {} status ({}s)".format(
            self.expected, self.actual, self.timeout)


class UnexpectedKubectlResponse(Exception):
    pass


class NonZeroRetCodeException(Exception):
    def __init__(self, message='', stdout=None, stderr=None, ret_code=None):
        self.stdout, self.stderr, self.ret_code = stdout, stderr, ret_code
        super(NonZeroRetCodeException, self).__init__(message)

    def __str__(self):
        return '\n'.join([self.message, str(self.stdout), str(self.stderr)])


class OpenNebulaError(Exception):
    pass


class NotEnoughFreeIPs(OpenNebulaError):
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


class NodeWasNotRemoved(Exception):
    pass


class IncorrectPodDescription(Exception):
    pass


class CannotRestorePodWithMoreThanOneContainer(Exception):
    pass


class NodeIsNotPresent(Exception):
    pass


class ContainerNotRunningException(Exception):
    pass


class FileTransferValidationFailed(Exception):
    pass


class ServicePodsNotReady(Exception):
    pass


class VmCreateError(Exception):
    pass


class VmProvisionError(Exception):
    pass


class VmNotFoundError(Exception):
    pass


class ClusterUpgradeError(Exception):
    pass


class WrongCLICommand(Exception):

    """Be risen if wrong cli command is called.

     For example, PA-pod can be created by both kdctl and kcli2 commands.
     The one is chosen by specifying parameter "command", when calling
     pods.create_pa() method. If some other (not kdctl or kcli2) is
     specified as "command" for create_pa(), this exception should be risen.

    """

    pass


class KDIsNotSane(Exception):
    """ Will be rised if some of sanity checks will fail.
    For example, if pods list gathering API not responding for 2 sec.
    """
    pass
