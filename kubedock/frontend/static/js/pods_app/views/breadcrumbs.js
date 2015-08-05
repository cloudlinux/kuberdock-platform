define(['pods_app/app',
        'tpl!pods_app/templates/breadcrumbs.tpl'],
    function(Pods, breadcrumbsTpl){
        
        Pods.module('Views.Misc', function(Misc, App, Backbone, Marionette, $, _){
            
            Misc.Breadcrumbs = Backbone.Marionette.ItemView.extend({
                template: breadcrumbsTpl,
                tagName: 'div',
                className: 'breadcrumbs-wrapper',
                
                ui: {
                    'node_search' : 'input#nav-search-input'
                },
                
                events: {
                    'keyup @ui.node_search' : 'filterCollection'
                },
                
                filterCollection: function(evt){
                    evt.stopPropagation();
                    this.trigger('collection:filter', evt.target.value);
                }
                
            });
            
        });
        
        return Pods.Views.Misc;
});