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
        var that = this;
        require(['nodes_app/controller', 'nodes_app/router'],
                function(Controller, Router){
            var controller = new Controller();
            new Router({controller: controller});

            function eventHandler(){
                var source = new EventSource("/api/stream");
                if (typeof(EventSource) === 'undefined') {
                    console.log('ERROR: EventSource is not supported by browser');
                } else {
                    source.addEventListener('pull_nodes_state', function (ev) {
                        that.nodesCollection.fetch()
                    }, false);

                    source.addEventListener('install_logs', function (ev) {
                        var decoded = JSON.parse(ev.data),
                            node = that.nodesCollection.findWhere({'hostname': decoded.for_node});

                        if (typeof(node) !== 'undefined') {
                            node.set('install_log', node.get('install_log') + decoded.data + '\n');
                            App.vent.trigger('update_console_log');
                        }
                    }, false);
                    source.onerror = function () {
                        console.info('SSE Error');
                        source.close();
                        setTimeout(eventHandler, 5 * 1000);
                    };
                }
            }

            if (Backbone.history) {
                Backbone.history.start({root: '/nodes-apps/'});

                eventHandler();

                if (App.getCurrentRoute() === "") {
                    controller.showNodes();
                }
            }
        });
    });

    return App;
});