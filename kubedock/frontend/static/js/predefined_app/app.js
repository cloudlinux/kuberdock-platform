define(['marionette', 'backbone'], function(Marionette){
    "use strict";
    var Apps = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });
    
    Apps.navigate = function(route, options){
        options || (options = {});
        Backbone.history.navigate(route, options);
    };
    
    Apps.getCurrentRoute = function(){
        return Backbone.history.fragment;
    };
    
    Apps.on('start', function(){
        require(['predefined_app/controller', 'predefined_app/router'],
                function(Controller, Router){
            var controller = new Controller();
            new Router({controller: controller});
            
            if (Backbone.history) {
                Backbone.history.start({root: '/predefined-apps/'});
                
                if (Apps.getCurrentRoute() === "") {
                    Apps.navigate('list');
                    controller.listApps();
                }
            }
        });
    });

    return Apps;
});