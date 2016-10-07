import App from 'app_data/app';
import * as utils from 'app_data/utils';
import navListTpl from 'app_data/menu/templates/list.tpl';
import navListItemTpl from 'app_data/menu/templates/item.tpl';

export const NavListItem = Backbone.Marionette.ItemView.extend({
    template    : navListItemTpl,
    tagName     : 'li',
    className   : 'dropdown',
    initialize: function(){
        this.model.set('active', window.location.hash === this.model.get('path'));
    }
});

export const NavList = Backbone.Marionette.CompositeView.extend({
    template : navListTpl,
    childView : NavListItem,
    childViewContainer : 'ul#menu-items',
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
