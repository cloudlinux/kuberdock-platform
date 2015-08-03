requirejs.config({
    baseUrl: "static/js",
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone             : "lib/backbone",
        marionette           : "lib/backbone.marionette.min",
        bootstrap            : "lib/bootstrap",
        "backbone-paginator" : "lib/backbone.paginator",
        jquery               : "lib/jquery",
        underscore           : "lib/underscore",
        text                 : "lib/text",
        tpl                  : "lib/underscore-tpl",
        "bootstrap-editable" : "lib/bootstrap-editable.min",
        selectpicker         : 'lib/bootstrap-select.min',
        notify               : "lib/notify.min",
        jasmine              : "lib/jasmine",
        "jasmine-html"       : "lib/jasmine-html",
        "jasmine-boot"       : "lib/boot",
        "jasmine-jquery"     : "lib/jasmine-jquery",
        sinon                : "lib/sinon",
        "jasmine-sinon"      : "lib/jasmine-sinon"
        //blanket              : "lib/blanket.min",
        //"blanket-jasmine"    : "lib/blanket_jasmine.min"
    },
    shim: {
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
        //"blanket-jasmine": {
        //    deps: ["blanket", "jasmine-boot"],
        //    exports: 'blanket'
        //}
    }
});

require(['jasmine-boot'], function(jasmine){
    require(['pods_app/tests/specs'], function(){
        window.onload();
    });
});