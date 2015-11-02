define(['marionette', 'utils'], function (Marionette, utils) {

    var PVolumesApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    /** default delay to hide popup notifications (ms) */
    var defaultHideDelay = 4000;

    PVolumesApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        Data.PersistentStorageModel = utils.BaseModel.extend({
            defaults: {
                name   : 'Nameless',
                size   : 0,
                in_use : false,
                pod    : ''
            },
        });

        Data.PersistentStorageCollection = utils.BaseCollection.extend({
            url: '/api/pstorage',
            model: Data.PersistentStorageModel,
        });

    });


    PVolumesApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        /* Persistent volumes empty view */
        Views.PersistentVolumesEmptyView = Marionette.ItemView.extend({
            template: '#persistent-volumes-empty-template',
            tagName: 'tr',
        });

        /* Persistent volumes entry view */
        Views.PersistentVolumesItemView = Marionette.ItemView.extend({
            template: '#persistent-volumes-item-template',
            tagName: 'tr',

            ui: {
                terminate: 'span.terminate-btn'
            },

            events: {
                'click @ui.terminate': 'terminateVolume'
            },

            terminateVolume: function(){
                var that = this,
                    preloader = $('#page-preloader');

                if (this.model.get('in_use')) {
                    utils.notifyWindow('Persistent volume in use');
                } else {
                    preloader.show();
                    utils.modalDialogDelete({
                        title: "Delete persistent volume?",
                        body: "Are you sure want to delete this persistent volume?",
                        small: true,
                        show: true,
                        footer: {
                            buttonOk: function(){
                                that.model.destroy({
                                    wait: true,
                                    success: function(){
                                        preloader.hide();
                                        that.remove();
                                    },
                                    error: function(){
                                        preloader.hide();
                                    }
                                });
                            },
                            buttonCancel: true
                        }
                    });
                }
            }
        });

        /* Persistent volumes Views */
        Views.PersistentVolumesView = Marionette.CompositeView.extend({
            template           : '#persistent-volumes-template',
            childView          : Views.PersistentVolumesItemView,
            emptyView          : Views.PersistentVolumesEmptyView,
            childViewContainer : 'tbody',
        });


        Views.SettingsLayout = Marionette.LayoutView.extend({
            template: '#settings-layout-template',
            regions: {
                main: 'div#details_content'
            },
        });
    });

    PVolumesApp.module('PVolumesCRUD', function(
        PVolumesCRUD, App, Backbone, Marionette, $, _){

        PVolumesCRUD.Controller = Marionette.Controller.extend({

            showPersistentVolumes: function(){
                var layout_view = new App.Views.SettingsLayout(),
                    collection = new App.Data.PersistentStorageCollection(),
                    persistent_volumes_view = new App.Views.PersistentVolumesView({
                        collection: collection
                    }),
                    promise = collection.fetch();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(persistent_volumes_view);
                });
                promise.done(function(data){
                    App.contents.show(layout_view);
                });

            },
        });

        PVolumesCRUD.addInitializer(function(){
            var controller = new PVolumesCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    ''     : 'showPersistentVolumes',
                }
            });
        });

    });

    PVolumesApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/persistent_volumes/', pushState: true});
        }
    });

    return PVolumesApp;
});
