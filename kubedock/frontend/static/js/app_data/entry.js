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
