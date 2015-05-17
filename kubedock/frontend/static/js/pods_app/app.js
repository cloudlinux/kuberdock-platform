define(['backbone', 'marionette'], function(Backbone, Marionette){
    
    var Pods = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });
    
    Pods.navigate = function(route, options){
        options || (options = {});
        Backbone.history.navigate(route, options);
    };
    
    Pods.getCurrentRoute = function(){
        return Backbone.history.fragment;
    };
    
    Pods.on('start', function(){
        require(['pods_app/controllers/pods'], function(){
            if (Backbone.history) {
                Backbone.history.start({root: '/'});
            
                if (Pods.getCurrentRoute() === "") {
                    Pods.trigger('pods:list');
                }
            }
        });
    });
    
    return Pods;
});