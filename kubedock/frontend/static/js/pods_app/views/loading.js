define(['pods_app/app', 'jquery-spin'], function(Pods){
    
    Pods.module('Views.Loading', function(Loading, App, Backbone, Marionette, $, _){
        
        Loading.LoadingView = Backbone.Marionette.ItemView.extend({
            template: _.template('<div id="spinner"></div>'),
            ui: {
                spinner: '#spinner'
            },
            onRender: function(){
                this.ui.spinner.spin({color: '#437A9E'});
            }
        });
        
    });
    
    return Pods.Views.Loading;
});