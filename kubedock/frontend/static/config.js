/* eslint-env node */
'use strict';
var process = require('process');

// default config
var conf = {
    VERSION: '1.2.1-4',
    PROD: true,
    TEST: false,
    LOCAL_PORT: 3000,
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
