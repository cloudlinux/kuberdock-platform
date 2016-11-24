import 'bootstrap/dist/js/bootstrap.min';
import 'isv/entry.less';

import App from 'isv/app';
import 'isv/model';  // load all models and add resourcePremisers to App

window.jQuery = window.$ = require('jquery');  // required for integration tests

if (!PROD){  // NOTE: UglifyJs will cut whole block if PROD is false
    // make those vars available in browser console for debugging
    window._ = _;
    window.Backbone = Backbone;
}

App.start();
