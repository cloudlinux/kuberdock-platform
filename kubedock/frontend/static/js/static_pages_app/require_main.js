requirejs.config({
    baseUrl: '/static/js',
    paths: {
        backbone: 'lib/backbone',
        jquery: 'lib/jquery',
        'jquery-ui': 'lib/jquery-ui',
        cookie: 'lib/jquery.cookie',
        underscore: 'lib/underscore',
        marionette: 'lib/backbone.marionette',
        bootstrap: 'lib/bootstrap',
        paginator: 'lib/backbone.paginator',
        tpl: 'lib/tpl',
        text: 'lib/text',
        dynatree: 'lib/jquery.dynatree',
        ckeditor: 'lib/ckeditor/ckeditor',
        treetable: 'lib/jquery.treetable'
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
        dynatree: {
            deps: ["jquery", 'cookie', 'jquery-ui'],
            exports: "DynATree"
        },
        bootstrap: {
            deps: ['jquery'],
            exports: 'bootstrap'
        }
    }
});
require(["jquery", 'jquery-ui', "bootstrap", 'dynatree', 'lib/navbarr', 'static_pages_app/app'],
function(jQuery, jQueryUI, bs, DynATree, nb, StaticPagesApp){
    StaticPagesApp.start();
});