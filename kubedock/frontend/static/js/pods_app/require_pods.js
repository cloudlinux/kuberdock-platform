requirejs.config({
    baseUrl: "static/js",
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        jquery                 : "lib/jquery",
        underscore             : "lib/underscore",
        backbone               : "lib/backbone",
        marionette             : "lib/backbone.marionette.min",
        bootstrap              : "lib/bootstrap",
        "backbone-paginator"   : "lib/backbone.paginator",
        text                   : "lib/text",
        tpl                    : "lib/underscore-tpl",
        "jquery-spin"          : "lib/jquery.spin",
        spin                   : "lib/spin.min",
        "bootstrap-editable"   : "lib/bootstrap-editable.min",
        jqplot                 : "lib/jquery.jqplot.min",
        "jqplot-axis-renderer" : "lib/jqplot.dateAxisRenderer.min",
        "dropdowns-enhancement": "lib/dropdowns-enhancement",
        "scroll-model"         : "lib/scroll-model",
        "scroll-view"          : "lib/scroll-view",
        "notify"               : "lib/notify.min",
        moment                 : "lib/moment.min",
        "moment-timezone"      : "lib/moment-timezone-with-data.min"
    },
    shim: {
        underscore: {
            exports: "_"
        },
        backbone: {
            deps: ['jquery', 'underscore'],
            exports: 'Backbone'
        },
        'backbone-paginator': ['backbone'],
        marionette: ['backbone'],
        'bootstrap-editable': ['bootstrap'],
        'jquery-spin': ['spin'],
        tpl: ['text'],
        'jqplot-axis-renderer': ['jqplot'],
    },
    config: {
        moment: {
            noGlobal: true
        }
    }
});

require(['pods_app/app'], function(Pods){
    Pods.start();
});