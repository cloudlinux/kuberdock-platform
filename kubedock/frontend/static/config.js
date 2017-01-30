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

/* eslint-env node */
'use strict';
var process = require('process');

// default config
var conf = {
    VERSION: '1.2.1-4',
    PROD: false,
    TEST: false,
    LOCAL_PORT: 3000,
    // BUILD_PREFIX: `prepared-build${Math.random().toString(36).substr(2, 8)}`,
    BUILD_PREFIX: 'prepared',
};

// local config
try {
    var localConfig = require('./local-config');
    for (var key in localConfig){
        conf[key] = localConfig[key];
    }
} catch (e) { /* ok, there is no local config */ }

// env vars
if (process.env.PROD_ENV) conf.PROD = JSON.parse(process.env.PROD_ENV);
if (process.env.ENABLE_TESTS) conf.TEST = JSON.parse(process.env.ENABLE_TESTS);
if (process.env.FAST_DEV_BUILD) conf.FAST_DEV_BUILD = JSON.parse(process.env.FAST_DEV_BUILD);
if (process.env.API_HOST) conf.API_HOST = process.env.API_HOST;

conf.SOURCE_MAPS = conf.SOURCE_MAPS || !conf.PROD && !conf.FAST_DEV_BUILD;


module.exports = conf;
