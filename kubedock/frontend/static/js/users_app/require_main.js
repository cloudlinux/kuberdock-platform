requirejs.config({
    waitSeconds: 200,
    baseUrl: '/static/js',
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        jquery                 : 'lib/jquery',
        backbone               : 'lib/backbone',
        'jquery-ui'            : 'lib/jquery-ui',
        underscore             : 'lib/underscore',
        marionette             : 'lib/backbone.marionette',
        bootstrap              : 'lib/bootstrap',
        'bootstrap3-typeahead' : 'lib/bootstrap3-typeahead.min',
        paginator              : 'lib/backbone.paginator',
        tpl                    : 'lib/tpl',
        text                   : 'lib/text',
        notify                 : 'lib/notify.min',
        utils                  : 'utils',
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
        utils: {
            deps: ['backbone'],
            exports: "utils"
        },
        selectpicker: {
            deps: ['jquery', 'bootstrap']
        }
    }
});
require(['jquery', 'users_app/app', 'notify', 'jquery-ui', 'selectpicker', 'bootstrap3-typeahead'],
function(jQuery, UsersApp){
    UsersApp.Data.users = new UsersApp.Data.UsersPageableCollection(usersCollection);
    UsersApp.Data.onlineUsers = new UsersApp.Data.UsersPageableCollection(onlineUsersCollection);
    UsersApp.Data.userActivity = new UsersApp.Data.ActivitiesCollection(userActivity);

    UsersApp.start();
});