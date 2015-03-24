define(['marionette', 'utils'],
       function (Marionette, utils) {

    var SettingsApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    SettingsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

    });

    SettingsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        Views.SettingsLayout = Marionette.LayoutView.extend({
            template: '#settings-layout-template',
            regions: {
                main: 'div#main'
            }
        });
    });

    SettingsApp.module('SettingsCRUD', function(SettingsCRUD, App, Backbone, Marionette, $, _){

        SettingsCRUD.Controller = Marionette.Controller.extend({
            showSettings: function(){
                var layout_view = new App.Views.SettingsLayout();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show();
                });
                App.contents.show(layout_view);
            }
        });

        SettingsCRUD.addInitializer(function(){
            var controller = new SettingsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    '': 'showSettings'
                }
            });
        });

    });

    SettingsApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/settings', pushState: true});
        }
    });

    return SettingsApp;
});
