define(['app_data/app', 'app_data/controller', 'marionette', 'utils',
        'tpl!app_data/pstorage/templates/pv_list.tpl',
        'tpl!app_data/pstorage/templates/pv_list_empty.tpl',
        'tpl!app_data/pstorage/templates/pv_list_item.tpl',
        'tpl!app_data/pstorage/templates/pv_layout.tpl',
        'bootstrap', 'jquery-ui', 'selectpicker', 'bootstrap3-typeahead', 'mask'],
       function(App, Controller, Marionette, utils,
                pvListTpl,
                pvListEmptyTpl,
                pvListItemTpl,
                pvLayoutTpl){

    var views = {};

    views.PersistentVolumesEmptyView = Marionette.ItemView.extend({
        template: pvListEmptyTpl,
        tagName: 'tr',
    });

    views.PersistentVolumesItemView = Marionette.ItemView.extend({
        template: pvListItemTpl,
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
                utils.notifyWindow('Persistent volume is used');
            } else {
                utils.modalDialogDelete({
                    title: "Delete persistent volume?",
                    body: "Are you sure want to delete this persistent volume?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
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

    views.PersistentVolumesView = Marionette.CompositeView.extend({
        template           : pvListTpl,
        childView          : views.PersistentVolumesItemView,
        emptyView          : views.PersistentVolumesEmptyView,
        childViewContainer : 'tbody',
    });


    views.SettingsLayout = Marionette.LayoutView.extend({
        template: pvLayoutTpl,
        regions: {
            nav : 'div#nav',
            main: 'div#details_content'
        },
    });
    
    return views;
});
