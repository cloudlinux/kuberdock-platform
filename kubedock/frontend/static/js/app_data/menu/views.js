define(['app_data/app', 'app_data/utils', 'marionette',
        'app_data/menu/templates/nav_list.tpl',
        'app_data/menu/templates/nav_list_item.tpl',
], function(App, utils, Marionette, navListTpl, navListItemTpl){

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
            var nextURL = 'users/profile/' + App.currentUser.id + '/general';
            return new Backbone.Model().fetch({url: '/api/users/logoutA'})
                .done(function(){ App.navigate(nextURL).cleanUp(/*keepToken*/true).initApp(); })
                .always(utils.preloader.hide)
                .fail(utils.notifyWindow);
        },
        logout: function(evt){
            evt.stopPropagation();
            utils.preloader.show();
            return new Backbone.Model().fetch({url: '/api/users/logout'})
                .done(function(){ App.navigate('').cleanUp().initApp(); })
                .always(utils.preloader.hide)
                .fail(utils.notifyWindow);
        }
    });

    return views;
});
