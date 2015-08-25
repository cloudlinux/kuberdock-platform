define(['pods_app/app',
        'tpl!pods_app/templates/breadcrumbs.tpl'],
    function(Pods, breadcrumbsTpl){

        Pods.module('Views.Misc', function(Misc, App, Backbone, Marionette, $, _){

            Misc.Breadcrumbs = Backbone.Marionette.ItemView.extend({
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

                filterCollection: function(evt){
                    evt.stopPropagation();
                    this.trigger('collection:filter', evt.target.value);
                },

                showSearch: function(){
                    this.ui.navSearch.addClass('active');
                    this.ui.pod_search.focus();
                },

                closeSearch: function(){
                    this.ui.navSearch.removeClass('active');
                }
            });
        });

        return Pods.Views.Misc;
});