
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

import hashlib
import logging


class RequestsLogger(object):
    logger = logging.getLogger('requests_logger')

    @classmethod
    def turn_on_logging(cls):
        cls.logger.setLevel(logging.DEBUG)

    @classmethod
    def turn_off_logging(cls):
        cls.logger.setLevel(logging.ERROR)

    def __init__(self, session):
        self.session = session

    def log_curl_request(self, request):
        logger = self.logger
        if logger.level > logging.DEBUG:
            return
        session = self.session

        logger.debug('#################### Request ####################')
        curl = ['curl -i -L -X %s' % request.method]

        for (key, value) in request.headers.items():
            header = '-H \'%s: %s\'' % self._process_header(key, value)
            curl.append(header)

        if not session.verify:
            curl.append('-k')
        elif isinstance(session.verify, basestring):
            curl.append('--cacert %s' % session.verify)

        if session.cert:
            curl.append('--cert %s' % session.cert[0])
            curl.append('--key %s' % session.cert[1])

        if request.body:
            curl.append('-d \'%s\'' % request.body)

        curl.append('"%s"' % request.url)
        logger.debug(' '.join(curl))

    def log_http_response(self, resp):
        logger = self.logger
        if logger.level > logging.DEBUG:
            return

        logger.debug('#################### Response ###################')
        status = (resp.raw.version / 10.0, resp.status_code, resp.reason)
        dump = ['\nHTTP/%.1f %s %s' % status]
        dump.extend(['%s: %s' % (k, v) for k, v in resp.headers.items()])
        dump.append('')
        dump.extend([resp.text, ''])
        logger.debug('\n'.join(dump))
        logger.debug('###################### End ######################')

    @staticmethod
    def _process_header(name, value):
        if name in ('X-Auth-Token',):
            v = value.encode('utf-8')
            h = hashlib.sha1(v)
            d = h.hexdigest()
            return name, "{SHA1}%s" % d
        else:
            return name, value
