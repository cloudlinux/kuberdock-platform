define(['nodes_app/app', 'backbone', 'backbone-paginator'], function(App, Backbone){
    
    var data = {},
        unwrapper = function(data){
            if (_.has(data, 'data')) return data['data'];
            return data;
        };
    
    data.NodeModel = Backbone.Model.extend({
        urlRoot: '/api/nodes/',
        parse: unwrapper,
        defaults: {
            'ip': ''
        }
    });
    
    data.NodesCollection = Backbone.PageableCollection.extend({
        url: '/api/nodes/',
        model: data.NodeModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        }
    });
    
    data.NodeStatsModel = Backbone.Model.extend({
        parse: unwrapper,
    });
    
    data.NodeStatsCollection = Backbone.Collection.extend({
        url: '/api/stats/',
        model: data.NodeStatsModel,
        parse: unwrapper
    });
    
    return data;
});