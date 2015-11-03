define(['marionette', 'utils'], function (Marionette, utils) {

    var PublicIPsApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    /** default delay to hide popup notifications (ms) */
    var defaultHideDelay = 4000;

    PublicIPsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        Data.UserAddressModel = utils.BaseModel.extend({
            defaults: {
                pod    : ''
            },
        });

        Data.UserAddressCollection = utils.BaseCollection.extend({
            url: '/api/ippool/userstat',
            model: Data.UserAddressModel,
        });

    });

    PublicIPsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        /* Public IPs Views */
        Views.PublicIPsItemView = Marionette.ItemView.extend({
            template: '#publicIPs-item-template',
            tagName: 'tr'
        });

        /* Public IPs Empty Views */
        Views.PublicIPsEmptyView = Marionette.ItemView.extend({
            template: '#publicIPs-item-empty-template',
            tagName: 'tr'
        });

        /* Public IPs Views */
        Views.PublicIPsView = Marionette.CompositeView.extend({
            template            : '#publicIPs-template',
            childView           : Views.PublicIPsItemView,
            emptyView           : Views.PublicIPsEmptyView,
            childViewContainer  : 'tbody',
        });

        Views.SettingsLayout = Marionette.LayoutView.extend({
            template: '#settings-layout-template',
            regions: {
                main: 'div#details_content'
            },
        });
    });

    PublicIPsApp.module('PublicIPsCRUD', function(
        PublicIPsCRUD, App, Backbone, Marionette, $, _){

        PublicIPsCRUD.Controller = Marionette.Controller.extend({

            showIPs: function(){
                var layout_view = new App.Views.SettingsLayout(),
                    collection = new App.Data.UserAddressCollection(),
                    public_ips_view = new App.Views.PublicIPsView({
                        collection: collection
                    }),
                    promise = collection.fetch();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(public_ips_view);
                });
                promise.done(function(data){
                    App.contents.show(layout_view);
                });
            },
        });

        PublicIPsCRUD.addInitializer(function(){
            var controller = new PublicIPsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    ''                        : 'showIPs',
                }
            });
        });

    });

    PublicIPsApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/publicIPs/', pushState: true});
        }
    });

    return PublicIPsApp;
});
