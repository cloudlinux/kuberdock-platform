define(['pods_app/app', 'backbone', 'backbone-paginator', 'notify'], function(Pods, Backbone){

    Pods.module('Data', function(Data, App, Backbone, Marionette, $, _){

        var unwrapper = function(response) {
            var data = response.hasOwnProperty('data') ? response['data'] : response
            if (response.hasOwnProperty('status')) {
                if(response.status == 'error' || response.status == 'warning') {
                    var err = data;
                    if(typeof data !== 'string') err = JSON.stringify(data);
                    $.notify(err, {
                        autoHideDelay: 5000,
                        globalPosition: 'top center',
                        className: response.status == 'error' ? 'danger' : 'warning'
                    });
                }
            }
            return data;
        };

        Data.Pod = Backbone.Model.extend({

            defaults: {
                name: 'Nameless',
                containers: [],
                volumes: [],
                replicationController: true,
                replicas: 1,
                restartPolicy: "Always",
                node: null
            },

            parse: unwrapper,

            fillContainer: function(container, data){
                if (data.hasOwnProperty('ports')) {
                    _.each(data['ports'], function(p){
                        container['ports'].push({
                            containerPort: p['number'],
                            protocol: p['protocol'],
                            hostPort: null,
                            isPublic: false
                        })
                    });
                }
                if (data.hasOwnProperty('volumeMounts')) {
                    _.each(data['volumeMounts'], function(m){
                        container['volumeMounts'].push({name: null, mountPath: m, readOnly: false})
                    });
                }
                _.each(['workingDir', 'args', 'env', 'secret'], function(i){
                    if (data.hasOwnProperty(i)) {
                        container[i] = data[i];
                    }
                });
            },
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
            url: '/api/podapi/',
            model: Data.Pod,
            parse: unwrapper,
            mode: 'client',
            state: {
                pageSize: 8
            },
            searchIn: function(val){
                return this.fullCollection.models.filter(function(i){
                    return i.get('name').indexOf(val) === 0;
                });
            }
        });

        Data.ImageCollection = Backbone.Collection.extend({
            url: '/api/images/',
            model: Data.Image,
            parse: unwrapper
        });

        Data.ImagePageableCollection = Backbone.PageableCollection.extend({
            url: '/api/images/',
            model: Data.Image,
            parse: unwrapper,
            mode: 'infinite',
            state: {
                pageSize: 10
            }
        });

        Data.StatsCollection = Backbone.Collection.extend({
            url: '/api/stats',
            model: Data.Stat,
            parse: unwrapper
        });

        // TODO: Fixed code duplication by moving models from settings_app to a common file
        Data.PersistentStorageModel = Backbone.Model.extend({
            defaults: {
                name   : 'Nameless',
                size   : 0,
                in_use : false,
                pod    : ''
            },
            parse: unwrapper
        });

        // TODO: Fixed code duplication by moving models from settings_app to a common file
        Data.PersistentStorageCollection = Backbone.Collection.extend({
            url: '/api/pstorage',
            model: Data.PersistentStorageModel,
            parse: unwrapper
        });

    });

    return Pods.Data;
});
