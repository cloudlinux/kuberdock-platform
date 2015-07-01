requirejs.config({
    waitSeconds: 200,
    baseUrl: '/static/js',
    urlArgs: "bust=" + (new Date()).getTime(),
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
        treetable: 'lib/jquery.treetable',
        dde: 'lib/dropdowns-enhancement'
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
        },
        dde: {
            deps: ['jquery', 'bootstrap']
        }
    }
});
require(["jquery", 'jquery-ui', "bootstrap", 'dynatree', 'static_pages_app/app', 'dde'],
function(jQuery, jQueryUI, bs, DynATree, StaticPagesApp){
    StaticPagesApp.start();
});