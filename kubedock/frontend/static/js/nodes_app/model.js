define(['nodes_app/app', 'backbone', 'backbone-paginator'], function(App, Backbone){

    var data = {},
        unwrapper = function(data){
            if (_.has(data, 'data')) return data['data'];
            return data;
        };

    data.NodeModel = Backbone.Model.extend({
        logsLimit: 5000,  // max number of line in logs
        urlRoot: '/api/nodes/',
        parse: unwrapper,
        defaults: function() {
            return {
                'ip': '',
                'logs': [],
                'logsError': null,
            };
        },

        getLogs: function(size){
            size = size || 100;
            return $.ajax({
                url: '/api/logs/node/' + this.get('hostname') + '?size=' + size,
                context: this,
                success: function(data) {
                    var oldLines = this.get('logs'),
                        lines = data.data.hits.reverse();

                    if (lines.length && oldLines.length) {
                        // if we have some logs, append only new lines
                        var first = lines[0],
                            index_to = _.sortedIndex(oldLines, first, 'time_nano'),
                            index_from = Math.max(0, index_to + lines.length - this.logsLimit);
                        lines.unshift.apply(lines, oldLines.slice(index_from, index_to));
                    }

                    this.set('logs', lines);
                    this.set('logsError', null);
                },
                error: function(xhr) {
                    var data = xhr.responseJSON;
                    if (data && data.data !== undefined)
                        this.set('logsError', data.data);
                },
                statusCode: null,
            });
        },
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