requirejs.config({
    baseUrl: "static/js",
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        jquery                 : "lib/jquery",
        'jquery-ui'            : 'lib/jquery-ui',
        underscore             : "lib/underscore-min",
        backbone               : "lib/backbone",
        marionette             : "lib/backbone.marionette.min",
        bootstrap              : "lib/bootstrap",
        "backbone-paginator"   : "lib/backbone.paginator",
        "backbone-associations": "lib/backbone-associations",
        text                   : "lib/text",
        tpl                    : "lib/underscore-tpl",
        "bootstrap-editable"   : "lib/bootstrap-editable.min",
        "bootstrap3-typeahead" : 'lib/bootstrap3-typeahead.min',
        jqplot                 : "lib/jquery.jqplot.min",
        "jqplot-axis-renderer" : "lib/jqplot.dateAxisRenderer.min",
        notify                 : "lib/notify.min",
        moment                 : "lib/moment.min",
        "moment-timezone"      : "lib/moment-timezone-with-data.min",
        selectpicker           : 'lib/bootstrap-select.min',
        numeral                : "lib/numeral/numeral.min",
        numeral_langs          : "lib/numeral/languages.min",
        jscrollpane            : 'lib/jquery.jscrollpane.min',
        mask                   : 'lib/jquery.mask',
        dde                    : 'lib/dropdowns-enhancement',
        nicescroll             : 'lib/jquery.nicescroll',
        bbcode                 : "lib/bbCodeParser.min"
    },
    shim: {
        jquery: {
            exports: "$"
        },
        'jquery-ui': {
            deps: ["jquery"]
        },
        underscore: {
            exports: "_"
        },
        backbone: {
            deps: ['jquery', 'underscore'],
            exports: 'Backbone'
        },
        'backbone-paginator' : ['backbone'],
        'backbone-associations' : ['backbone'],
        marionette: ['backbone'],
        'bootstrap-editable': ['bootstrap'],
        'bootstrap3-typeahead': ['bootstrap'],
        tpl: ['text'],
        'jqplot-axis-renderer': ['jqplot'],
        selectpicker: {
            deps: ['jquery', 'bootstrap']
        },
        notify: {
            deps: ["jquery"],
            exports: 'jQuery.fn.notify'
        }
    },
    config: {
        moment: {
            noGlobal: true
        }
    },
    waitSeconds: 30
});

require(['app_data/app', 'app_data/model'], function(App){
    App.start();
});
