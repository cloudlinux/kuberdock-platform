import 'isv/entry.less';

import App from 'isv/app';
import 'isv/model';  // load all models and add resourcePremisers to App
import * as utils from 'app_data/utils';

window.jQuery = window.$ = require('jquery');  // required for integration tests

utils.promiseDOMReady().then(function(){
    let bootstrapLoaded = typeof $().modal === 'function';
    if (!bootstrapLoaded){
        $('head').append(`
            <link rel="stylesheet"
                href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css"
                integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u"
                crossorigin="anonymous">
            <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"
                integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa"
                crossorigin="anonymous"></script>
        `);
    }

    if (!PROD){  // NOTE: UglifyJs will cut whole block if PROD is false
        // make those vars available in browser console for debugging
        window._ = _;
        window.Backbone = Backbone;
    }

    App.start();
});
