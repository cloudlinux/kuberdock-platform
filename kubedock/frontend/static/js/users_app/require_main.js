requirejs.config({
    baseUrl: '/static/js',
    paths: {
        backbone: 'lib/backbone',
        jquery: 'lib/jquery',
        underscore: 'lib/underscore',
        marionette: 'lib/backbone.marionette',
        bootstrap: 'lib/bootstrap',
        paginator: 'lib/backbone.paginator',
        tpl: 'lib/tpl',
        text: 'lib/text',
        notify: 'lib/notify.min',
        utils: 'utils'
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
        notify: {
            deps: ["jquery"],
            exports: 'jQuery.fn.notify'
        },
        utils: {
            deps: ['backbone'],
            exports: "utils"
        }
    }
});
require(['jquery', 'users_app/app', 'notify'], function(jQuery, UsersApp){
    UsersApp.Data.users = new UsersApp.Data.UsersPageableCollection(usersCollection);
    UsersApp.Data.onlineUsers = new UsersApp.Data.UsersPageableCollection(onlineUsersCollection);
    UsersApp.Data.userActivity = new UsersApp.Data.ActivitiesCollection(userActivity);

    UsersApp.start();

    $.notify('User app started', {
        autoHideDelay: 5000,
        globalPosition: 'top center',
        className: 'info'
    });


});