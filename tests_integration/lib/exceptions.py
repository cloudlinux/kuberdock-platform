
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

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


class PANotFoundInCatalog(Exception):
    pass


class PodResizeError(Exception):
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


class NoSpaceLeftOnPersistentVolume(Exception):
    pass
