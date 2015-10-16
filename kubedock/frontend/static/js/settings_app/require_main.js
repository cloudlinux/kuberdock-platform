requirejs.config({
    waitSeconds: 200,
    baseUrl: '/static/js',
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone               : 'lib/backbone',
        jquery                 : 'lib/jquery',
        'jquery-ui'            : 'lib/jquery-ui',
        underscore             : 'lib/underscore-min',
        marionette             : 'lib/backbone.marionette',
        bootstrap              : 'lib/bootstrap',
        'bootstrap3-typeahead' : 'lib/bootstrap3-typeahead.min',
        moment                 : 'lib/moment.min',
        'moment-timezone'      : 'lib/moment-timezone-with-data.min',
        paginator              : 'lib/backbone.paginator',
        tpl                    : 'lib/tpl',
        text                   : 'lib/text',
        notify                 : 'lib/notify.min',
        mask                   : 'lib/jquery.mask',
        utils                  : 'utils',
        dde                    : 'lib/dropdowns-enhancement',
        selectpicker           : 'lib/bootstrap-select.min',
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
        },
        'moment-timezone': {
            deps: ['moment']
        },
        selectpicker: {
            deps: ['jquery', 'bootstrap']
        }
    }
});
require(['jquery', 'settings_app/app', 'moment', 'notify', 'jquery-ui', 'bootstrap3-typeahead', 'moment-timezone', 'selectpicker'],
function(jQuery, SettingsApp, moment){
    SettingsApp.Data.permissions = new SettingsApp.Data.PermissionsCollection(permissions);
    SettingsApp.Data.notifications = new SettingsApp.Data.NotificationsCollection(notifications);
    SettingsApp.Data.this_user = new SettingsApp.Data.CurrentUserModel(this_user);
    SettingsApp.start();
});