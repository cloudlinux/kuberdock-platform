define(['app_data/app', 'jquery-spin'], function(App){
    var loading = {};
    loading.LoadingView = Backbone.Marionette.ItemView.extend({
        template: _.template('<div id="spinner"></div>'),
        ui: {
            spinner: '#spinner'
        },
        onRender: function(){
            this.ui.spinner.spin({color: '#437A9E'});
        }
    });
    return loading;
});