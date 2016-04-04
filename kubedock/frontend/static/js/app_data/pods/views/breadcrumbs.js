define(['app_data/app',
        'tpl!app_data/pods/templates/breadcrumbs.tpl'],
    function(App, breadcrumbsTpl){

        var misc = {};

        misc.Breadcrumbs = Backbone.Marionette.ItemView.extend({
            template: breadcrumbsTpl,
            tagName: 'div',
            className: 'breadcrumbs-wrapper',

            ui: {
                'pod_search'  : 'input#nav-search-input',
                'navSearch'   : '.nav-search'
            },

            events: {
                'keyup @ui.pod_search'  : 'filterCollection',
                'click @ui.navSearch'   : 'showSearch',
                'blur @ui.pod_search'   : 'closeSearch',
            },

            templateHelpers: function(){ return {user: App.currentUser}; },

            filterCollection: function(evt){
                evt.stopPropagation();
                this.trigger('collection:filter', evt.target.value);
            },

            showSearch: function(){
                this.ui.navSearch.addClass('active');
                this.ui.pod_search.focus();
            },

            closeSearch: function(){
                if (this.ui.pod_search.val().trim() === '')
                    this.ui.navSearch.removeClass('active');
            }
        });

        return misc;
});
