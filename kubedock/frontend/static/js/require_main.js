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
        text: 'lib/text'
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
        }
    }
});
require(['jquery', 'users_app'], function(jQuery, UsersApp){
    $.ajax({
        url: '/api/users/',
        success: function(rs){
            UsersApp.Data.users = new UsersApp.Data.UsersCollection(rs.data);
            UsersApp.start();
        }
    });
});