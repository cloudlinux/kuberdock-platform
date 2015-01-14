/**
 * This module provides data for pods
 */
KubeDock.module('Data', function(Data, App, Backbone, Marionette, $, _){
    
    var unwrapper = function(response) {
        if (response.hasOwnProperty('data'))
            return response['data'];
        return response;
    };
    
    Data.Pod = Backbone.Model.extend({
        
        defaults: {
            name: 'Nameless',
            containers: [],
            volumes: [],
            cluster: false,
            replicas: 1,
            service: false,
            portalIP: null,
            port: null
        },
        
        parse: unwrapper,
        
        getContainerByImage: function(image){
            var filtered = _.filter(this.get('containers'), function(c){
                return c['image'] === this.image;
            }, {image: image});
            return (filtered.length !== 0) ? filtered[0] : null;
        },
        
        fillContainer: function(container, data){
            if (data.hasOwnProperty('ports')) {
                _.each(data['ports'], function(p){
                    container['ports'].push({containerPort: parseInt(p), protocol: 'tcp'})
                });
            }
            if (data.hasOwnProperty('volumeMounts')) {
                _.each(data['volumeMounts'], function(m){
                    container['volumeMounts'].push({name: null, mountPath: m, readOnly: false})
                });
            }
            _.each(['workingDir', 'command'], function(i){
                if (data.hasOwnProperty(i)) {
                    container[i] = data[i];
                }
            });
        }
    });
    
    Data.Image = Backbone.Model.extend({
        
        defaults: {
            image: 'Imageless'
        },
        
        parse: unwrapper
    });
    
    Data.Stat = Backbone.Model.extend({
        parse: unwrapper
    });
    
    Data.PodCollection = Backbone.PageableCollection.extend({
        url: '/api/pods',
        model: Data.Pod,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 2
        }
    });
    
    Data.ImageCollection = Backbone.PageableCollection.extend({
        url: '/api/images',
        model: Data.Image,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 5
        }
    });
    
    Data.StatsCollection = Backbone.Collection.extend({
        url: '/api/stats',
        model: Data.Stat,
        parse: unwrapper
    });
});