define(['backbone', 'marionette', 'nodes_app/app', 'nodes_app/views', 'nodes_app/model'],
       function(Backbone, Marionette, App, Views, Data){
    
    var controller = Marionette.Object.extend({
        
        showNodes: function(){
            var layout_view = new Views.NodesLayout(),
                nodes_list_view = new Views.NodesListView({ collection: App.nodesCollection }),
                node_list_pager = new Views.PaginatorView({ view: nodes_list_view });

            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(nodes_list_view);
                layout_view.pager.show(node_list_pager);
            });
            App.contents.show(layout_view);
        },
        
        showAddNode: function(){
            var layout_view = new Views.NodeAddWizardLayout(),
                node_add_step = new Views.NodeAddStep();

            this.listenTo(layout_view, 'show', function(){
                layout_view.node_add_step.show(node_add_step)
            });
            App.contents.show(layout_view);
        },
        
        showDetailedNode: function(nodeId, tab){
            var node = App.nodesCollection.get(nodeId),
                layout_view = new Views.NodeDetailedLayout({
                    tab: tab, node_id: nodeId, model: node
                });
                
            this.listenTo(layout_view, 'show', function(){
                switch (layout_view.tab) {
                    
                    case 'general': {
                        var node_general_tab_view = new Views.NodeGeneralTabView({ model: node });
                        layout_view.tab_content.show(node_general_tab_view);
                    } break;
                    
                    case 'stats': {
                        var node_stats_tab_view = new Views.NodeStatsTabView({ model: node });
                        layout_view.tab_content.show(node_stats_tab_view);
                    } break;
                    
                    case 'logs': {
                        var node_logs_tab_view = new Views.NodeLogsTabView({ model: node });
                        layout_view.tab_content.show(node_logs_tab_view);
                    } break;
                    
                    case 'monitoring': {
                        var hostname = node.get('hostname'),
                            graphCollection = new Data.NodeStatsCollection();
                        graphCollection.fetch({
                            wait: true,
                            data: {node: hostname},
                            success: function(){
                                var node_monitoring_tab_view = new Views.NodeMonitoringTabView({
                                    collection: graphCollection,
                                    hostname: hostname,
                                    nodeId: nodeId
                                });
                                layout_view.tab_content.show(node_monitoring_tab_view);
                            },
                            error: function(){
                                console.log('could not get graphs');
                            }
                        });
                    } break;
                    
                    case 'timelines': {
                        var node_timelines_tab_view = new Views.NodeTimelinesTabView({ model: node });
                        layout_view.tab_content.show(node_timelines_tab_view);
                    } break;

                    case 'configuration': {
                        var node_configuration_tab_view = new Views.NodeConfigurationTabView({ model: node });
                        layout_view.tab_content.show(node_configuration_tab_view);
                    } break;
                }
            });
            App.contents.show(layout_view);
        }
    });
    return controller;
});