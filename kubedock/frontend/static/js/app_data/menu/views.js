define(['app_data/app', 'marionette',
        'tpl!app_data/menu/templates/nav_list.tpl',
        'tpl!app_data/menu/templates/nav_list_item.tpl',
        'bootstrap'],
       function(App, Marionette, navListTpl, navListItemTpl){

    var views = {};

    views.NavListItem = Backbone.Marionette.ItemView.extend({
        template    : navListItemTpl,
        tagName     : 'li',
        className   : 'dropdown',

        events: {
            'click a:not(.dropdown-toggle)': 'processLink'
        },

        processLink: function(evt){
            evt.stopPropagation();
            evt.preventDefault();
            var tgt = $(evt.target),
                dest = tgt.attr('href').replace(/(?:^\/|\/$)/g, '');
            App.navigate(dest, {trigger: true});
        }
    });

    views.NavList = Backbone.Marionette.CompositeView.extend({
        template            : navListTpl,
        childView           : views.NavListItem,
        childViewContainer  : 'ul#menu-items',

        events: {
            'click a.routable': 'processLink'
        },

        processLink: function(evt){
            evt.stopPropagation();
            evt.preventDefault();
            console.log($(evt.target));
            var tgt = $(evt.target),
                dest = tgt.attr('href').replace(/(?:^\/|\/$)/g, '');
            App.navigate(dest, {trigger: true});
        }
    });

    return views;
});