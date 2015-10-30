define(['marionette', 'backbone'], function(Marionette){
    "use strict";
    var App = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents'
        },
        
        initialize: function(){
            var that = this;
            require(['nodes_app/model'], function(Model){
                that.nodesCollection = new Model.NodesCollection(nodesCollection);
            });
        }
    });
    
    App.navigate = function(route, options){
        options || (options = {});
        Backbone.history.navigate(route, options);
    };
    
    App.getCurrentRoute = function(){
        return Backbone.history.fragment;
    };
    
    App.on('start', function(){
        require(['nodes_app/controller', 'nodes_app/router'],
                function(Controller, Router){
            var controller = new Controller();
            new Router({controller: controller});
            
            if (Backbone.history) {
                Backbone.history.start({root: '/nodes-apps/'});
                
                if (App.getCurrentRoute() === "") {
                    controller.showNodes();
                }
            }
        });
    });

    return App;
});