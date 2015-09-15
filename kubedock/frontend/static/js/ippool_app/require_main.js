requirejs.config({
    waitSeconds: 200,
    baseUrl: '/static/js',
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone: 'lib/backbone',
        jquery: 'lib/jquery',
        'jquery-ui': 'lib/jquery-ui',
        underscore: 'lib/underscore-min',
        marionette: 'lib/backbone.marionette',
        bootstrap: 'lib/bootstrap',
        paginator: 'lib/backbone.paginator',
        tpl: 'lib/tpl',
        text: 'lib/text',
        notify: 'lib/notify.min',
        mask: 'lib/jquery.mask',
        utils: 'utils',
        dde: 'lib/dropdowns-enhancement'
    },
    shim: {
        jquery: {
            exports: "$"
        },
        'jquery-ui': {
            deps: ["jquery"]
        },
        'bootstrap': {
            deps: ["jquery"]
        },
        underscore: {
            exports: "_"
        },
        paginator: {
            deps: ["backbone"]
        },
        backbone: {
            deps: ["jquery", "bootstrap", "underscore", "text", "tpl"],
            exports: "Backbone"
        },
        marionette: {
            deps: ["jquery", "bootstrap", "underscore", "backbone"],
            exports: "Marionette"
        },
        notify: {
            deps: ["jquery"],
            exports: 'jQuery.fn.notify'
        },
        mask: {
            deps: ["jquery"],
            exports: 'jQuery.fn.mask'
        },
        utils: {
            deps: ['backbone'],
            exports: "utils"
        },
        dde: {
            deps: ['jquery', 'bootstrap']
        }
    }
});
require(['jquery', 'ippool_app/app', 'notify', 'jquery-ui', 'mask', 'dde'], function(jQuery, IPPoolApp){
    //IPPoolApp.Data.networks = new IPPoolApp.Data.NetworksCollection(networksCollection);
    IPPoolApp.start();
});