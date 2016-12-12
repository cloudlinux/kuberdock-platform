define(['app_data/app', 'app_data/controller', 'marionette', 'app_data/utils',
        'app_data/public_ips/templates/public_ips_list.tpl',
        'app_data/public_ips/templates/public_ips_empty.tpl',
        'app_data/public_ips/templates/public_ips_item.tpl',
        'app_data/public_ips/templates/public_ips_layout.tpl',
], function(App, Controller, Marionette, utils,
            publicIPsListTpl,
            publicIPsEmptyTpl,
            publicIPsItemTpl,
            publicIPsLayoutTpl){

    var views = {};

    views.PublicIPsItemView = Marionette.ItemView.extend({
        template: publicIPsItemTpl,
        tagName: 'tr'
    });

    views.PublicIPsEmptyView = Marionette.ItemView.extend({
        template: publicIPsEmptyTpl,
        tagName: 'tr'
    });

    views.PublicIPsView = Marionette.CompositeView.extend({
        template            : publicIPsListTpl,
        childView           : views.PublicIPsItemView,
        emptyView           : views.PublicIPsEmptyView,
        childViewContainer  : 'tbody',

        templateHelpers: function(){
            var hasIPs = !!this.collection.find(function(m){
                return /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:\/\d+)?/.test(m.id);
            });
            return {
                resourceName: hasIPs ? 'Public IP' : 'Public Name'
            };
        },

        onShow: function(){
            utils.preloader.hide();
        }
    });

    views.SettingsLayout = Marionette.LayoutView.extend({
        template: publicIPsLayoutTpl,
        regions: {
            breadcrumbs : '#breadcrumbs',
            main: 'div#details_content'
        },

        onBeforeShow: function(){
            utils.preloader.show();
        }
    });
    return views;
});
