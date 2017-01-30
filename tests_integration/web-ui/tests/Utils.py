
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

import os
import shutil
from robot.libraries.BuiltIn import BuiltIn


class Utils(object):
    """
    Contains some useful keywords that are better handled with python.
    """

    def __init__(self):
        self.selenium = BuiltIn().get_library_instance('Selenium2Library')

    def _connect_to_selenium_hub(self, browser, url):
        hub_ip = BuiltIn().get_variable_value(
            '${SELENIUM_HUB_IP}', '127.0.0.1')
        self.selenium.open_browser(
            url, browser, None, 'http://{0}:4444/wd/hub'.format(hub_ip))

    def _open_local_browser(self, browser, url, browser_args):
        if browser.lower() == 'phantomjs':
            phantomjs_cache_dir = '~/.local/share/Ofi Labs/PhantomJS'
            shutil.rmtree(os.path.expanduser(phantomjs_cache_dir), True)
            browser_args.append('--ignore-ssl-errors=true')
        elif browser.lower() == 'chrome':
            browser_args.append('--ignore-certificate-errors')
        if browser_args:
            self.selenium.create_webdriver(browser, service_args=browser_args)
        else:
            self.selenium.create_webdriver(browser)
        self.selenium.go_to(url)

    def prepare_and_open_browser(self, browser, url, browser_args=None,
                                 width=None, height=None, timeout=None,
                                 delay=None):
        if browser_args is None:
            browser_args = []
        if width is None:
            width = BuiltIn().get_variable_value('${SCREEN_WIDTH}', 1024)
        if height is None:
            height = BuiltIn().get_variable_value('${SCREEN_HEIGHT}', 768)
        if timeout is None:
            timeout = BuiltIn().get_variable_value('${TIMEOUT}', '8 s')
        if delay is None:
            delay = BuiltIn().get_variable_value('${DELAY}', 0)

        env = BuiltIn().get_variable_value('${TEST_ENV}', 'local')
        if env == 'docker':
            self._connect_to_selenium_hub(browser, url)
        elif env == 'local':
            self._open_local_browser(browser, url, browser_args)
        else:
            raise ValueError('Invalid TEST_ENV: {0}'.format(env))

        self.selenium.set_window_size(width, height)
        self.selenium.set_selenium_timeout(timeout)
        self.selenium.set_selenium_implicit_wait(timeout)
        self.selenium.set_selenium_speed(delay)
        self.selenium.set_browser_implicit_wait(0)
        # need to wait until jQuery is loaded, before using "jquery=" locators
        self.selenium.wait_for_condition('return !!window.jQuery')

    def close_all_error_messages(self):
        try:
            elements = self.selenium.get_webelements('css=.notify-close')
        except ValueError:
            return  # no error messages
        map(self.selenium.click_element, elements)
        self.selenium.wait_until_page_does_not_contain_element(
            'css=.notify-close')

    def delete_user(self, username):
        """Go through all pages on the "Users" view, find and delete user."""
        delete_button = (
            'jquery=#userslist-table tr td:first-of-type:contains("{0}") '
            '~ td.actions .deleteUser'.format(username))
        while True:
            try:
                self.selenium.page_should_contain_element(delete_button)
            except Exception:
                BuiltIn().run_keyword(
                    'Click', 'jquery=.pager li:contains(Next):not(.disabled)')
            else:
                BuiltIn().run_keyword('Click', delete_button)
                BuiltIn().run_keyword('Click "Delete" In Modal Dialog')
                break
