requirejs.config({
    baseUrl: "/static/js",
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone             : "/static/js/lib/backbone",
        marionette           : "/static/js/lib/backbone.marionette.min",
        bootstrap            : "/static/js/lib/bootstrap",
        "backbone-paginator" : "/static/js/lib/backbone.paginator",
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
        //blanket              : "lib/blanket.min",
        //"blanket-jasmine"    : "lib/blanket_jasmine.min"
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
        tpl: {
            deps: ['text']
        },
        notify: {
            deps: ['jquery']
        },
        //selectpicker: {
        //    deps: ['jquery', 'bootstrap']
        //},
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
        //"blanket-jasmine": {
        //    deps: ["blanket", "jasmine-boot"],
        //    exports: 'blanket'
        //}
    }
});

require(['jasmine-boot', 'backbone'], function(jasmine, backbone){
    require(['ippool_app/tests/app'], function(){
        window.onload();
    });
});