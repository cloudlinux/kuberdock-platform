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

require('bootstrap/dist/js/bootstrap.min');
require('entry.less');

window.jQuery = window.$ = require('jquery');  // required for integration tests

const init = function(){
    if (!PROD){  // NOTE: UglifyJs will cut whole block if PROD is false
        // make those vars available in browser console for debugging
        window._ = _;
        window.Backbone = Backbone;

        if (/^https?:\/\/[^\/]+\/test(?:\?.*)?$/.test(window.location.href)){
            if (TEST){  // just run tests
                // for correct tracebacks in mocha
                require('stack-source-map')();
                const chai = require('chai');
                chai.use(require('chai-jquery'));
                chai.use(require('sinon-chai'));
                chai.use(require('chai-datetime'));

                // import tests using mocha-loader; run; exit
                require('mocha!app_data/tests/specs');
            } else {
                alert(  // eslint-disable-line no-alert
                    'You need to enable tests in config.js or build with ' +
                    '"ENABLE_TESTS=true"');
                window.location.href = '/';
            }
            return;
        }
    }

    var App = require('app_data/app');
    require('app_data/model');  // load all models and add resourcePremisers to App

    App.start();
};

init();
