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
if (process.env.API_HOST) conf.API_HOST = process.env.API_HOST;


module.exports = conf;
