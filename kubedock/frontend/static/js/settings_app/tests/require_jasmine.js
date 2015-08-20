requirejs.config({
    baseUrl: "/static/js",
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone             : "/static/js/lib/backbone",
        marionette           : "/static/js/lib/backbone.marionette.min",
        bootstrap            : "/static/js/lib/bootstrap",
        paginator            : '/static/js/lib/backbone.paginator',
        jquery               : "/static/js/lib/jquery",
        underscore           : "/static/js/lib/underscore",
        text                 : "/static/js/lib/text",
        tpl                  : "/static/js/lib/underscore-tpl",
        "bootstrap-editable" : "/static/js/lib/bootstrap-editable.min",
        selectpicker         : "/static/js/lib/bootstrap-select.min",
        notify               : "/static/js/lib/notify.min",
        jasmine              : "/static/js/lib/jasmine",
        "jasmine-html"       : "/static/js/lib/jasmine-html",
        "jasmine-boot"       : "/static/js/lib/boot",
        "jasmine-jquery"     : "/static/js/lib/jasmine-jquery",
        sinon                : "/static/js/lib/sinon",
        "jasmine-sinon"      : "/static/js/lib/jasmine-sinon"
    },
    shim: {
        jquery:{
            exports: "$"
        },
        underscore: {
            exports: "_"
        },
        backbone: {
            deps: ['jquery', 'underscore'],
            exports: 'Backbone'
        },
        marionette: {
            deps: ['backbone']
        },
        paginator: {
            deps: ["backbone"]
        },
        tpl: {
            deps: ['text']
        },
        notify: {
            deps: ['jquery']
        },
        bootstrap: {
            deps: ['jquery']
        },
        'bootstrap-editable': {
            deps: ['bootstrap']
        },
        "jasmine-html": {
            deps: ["jasmine"],
        },
        "jasmine-boot": {
            deps: ["jasmine-html"],
            exports: 'jasmine'
        },
        "jasmine-jquery": {
            deps: ["jquery"]
        },
        "jasmine-sinon": {
            deps: ["sinon"]
        },
    }
});

require(['jasmine-boot', 'backbone'], function(jasmine, backbone){
    require(['settings_app/tests/app'], function(){
        window.onload();
    });
});