/*
 * KuberDock - is a platform that allows users to run applications using Docker
 * container images and create SaaS / PaaS based on these applications.
 * Copyright (C) 2017 Cloud Linux INC
 *
 * This file is part of KuberDock.
 *
 * KuberDock is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * KuberDock is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
 */

/* eslint-env node, es6 */
/* eslint no-console: off */

var ERRORS_THRESHOLD = 52;

var CLIEngine = require('eslint').CLIEngine;
var process = require('process');

var cli = new CLIEngine({configFile: '.eslintrc'});
var formatter = cli.getFormatter();

var report = cli.executeOnFiles(['./js/app_data/', './js/isv/']),
    errorCount = report.errorCount + report.warningCount;

console.log(formatter(report.results));
console.log(`
####################### Linter results ############################
Found errors   : ${errorCount}
Errors treshold: ${ERRORS_THRESHOLD}
`);
process.exit(errorCount > ERRORS_THRESHOLD);
