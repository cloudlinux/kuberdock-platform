define(['app_data/app', 'app_data/utils', 'marionette',
        'tpl!app_data/menu/templates/nav_list.tpl',
        'tpl!app_data/menu/templates/nav_list_item.tpl',
        'bootstrap'],
       function(App, utils, Marionette, navListTpl, navListItemTpl){

    var views = {};

    views.NavListItem = Backbone.Marionette.ItemView.extend({
        template    : navListItemTpl,
        tagName     : 'li',
        className   : 'dropdown',
    });

    views.NavList = Backbone.Marionette.CompositeView.extend({
        template            : navListTpl,
        childView           : views.NavListItem,
        childViewContainer  : 'ul#menu-items',
        templateHelpers: function(){ return {user: App.currentUser}; },
        ui: {
            loggerOutA: 'span#logout-a',
            loggerOut: 'span#logout'
        },
        events: {
            'click @ui.loggerOutA': 'logoutAs',
            'click @ui.loggerOut': 'logout'
        },
        logoutAs: function(evt){
            evt.stopPropagation();
            utils.preloader.show();
            return $.ajax(_.extend({  // TODO: use Backbone.Model
                authWrap: true,
                url: '/api/users/logoutA',
                type: 'GET',
            }))
            .done(function(){ window.location.href = '/'; })
            .always(utils.preloader.hide)
            .error(utils.notifyWindow);
        },
        logout: function(evt){
            evt.stopPropagation();
            utils.preloader.show();
            return $.ajax(_.extend({  // TODO: use Backbone.Model
                authWrap: true,
                url: '/api/users/logout',
                type: 'GET',
            }))
            .done(function(){
                delete App.storage.authData;
                window.location.href = '/';
            })
            .always(utils.preloader.hide)
            .error(utils.notifyWindow);
        }
    });

    return views;
});
