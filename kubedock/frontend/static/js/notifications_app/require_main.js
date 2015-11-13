requirejs.config({
    waitSeconds: 200,
    baseUrl: '/static/js',
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone         : 'lib/backbone',
        jquery           : 'lib/jquery',
        underscore       : 'lib/underscore-min',
        marionette       : 'lib/backbone.marionette',
        bootstrap        : 'lib/bootstrap',
        paginator        : 'lib/backbone.paginator',
        tpl              : 'lib/tpl',
        text             : 'lib/text',
        dde              : 'lib/dropdowns-enhancement',
        moment           : "lib/moment.min",
        "moment-timezone": "lib/moment-timezone-with-data.min",
    },
    shim: {
        jquery: {
            exports: "$"
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
        dde: {
            deps: ['jquery', 'bootstrap']
        }
    }
});
require(['jquery', 'notifications_app/app', 'dde'], function(jQuery, NotificationsApp){
    NotificationsApp.Data.templates = new NotificationsApp.Data.TemplatesCollection(templatesCollection);
    NotificationsApp.start();
});