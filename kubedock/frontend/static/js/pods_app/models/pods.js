define(['pods_app/app', 'pods_app/utils', 'backbone', 'backbone-paginator',
        'backbone-associations', 'notify'], function(Pods, Utils, Backbone){

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

        Data.Container = Backbone.Model.extend({
            idAttribute: 'name',
            defaults: function(){
                return {
                    image: null,
                    name: _.random(Math.pow(36, 8)).toString(36),
                    workingDir: null,
                    ports: [],
                    volumeMounts: [],
                    env: [],
                    args: [],
                    kubes: 1,
                    terminationMessagePath: null,
                    sourceUrl: null,
                };
            },
            getPod: function(){
                return ((this.collection || {}).parents || [])[0];
            },
            checkForUpdate: function(){
                return $.ajax({
                    url: this.getPod().url() + '/' + this.id + '/update',
                    context: this,
                }).done(function(rs){ this.updateIsAvailable = rs.data; });
            },
            update: function(){
                return $.ajax({
                    url: this.getPod().url() + '/' + this.id + '/update',
                    type: 'POST',
                    context: this,
                }).done(function(){ this.updateIsAvailable = undefined; });
            },
            getLogs: function(size){
                size = size || 100;
                return $.ajax({
                    url: '/api/logs/container/' + this.get('name') + '?size=' + size,
                    context: this,
                    success: function(data){
                        var seriesByTime = _.indexBy(this.get('logs'), 'start');
                        _.each(data.data.reverse(), function(serie) {
                            var lines = serie.hits.reverse(),
                                oldSerie = seriesByTime[serie.start];
                            if (lines.length && oldSerie && oldSerie.hits.length) {
                                // if we have some logs, append only new lines
                                var first = lines[0],
                                    index = _.sortedIndex(oldSerie.hits, first, 'time_nano');
                                lines.unshift.apply(lines, _.first(oldSerie.hits, index));
                            }
                        });
                        this.set('logs', data.data);
                    },
                });
            },
        }, {  // Class Methods
            fromImage: function(image){
                var data = _.clone(image instanceof Data.Image ? image.attributes : image);
                data.ports = _.map(data.ports || [], function(port){
                    return {
                        containerPort: port.number,
                        protocol: port.protocol,
                        hostPort: null,
                        isPublic: false
                    };
                });
                data.volumeMounts = _.map(data.volumeMounts || [], function(vm){
                    return {name: null, mountPath: vm};
                });
                return new this(data);
            }
        });

        Data.Pod = Backbone.AssociatedModel.extend({
            urlRoot: '/api/podapi/',
            relations: [{
                  type: Backbone.Many,
                  key: 'containers',
                  relatedModel: Data.Container,
            }],

            defaults: function(){
                return {
                    name: 'Nameless',
                    containers: [],
                    volumes: [],
                    replicas: 1,
                    restartPolicy: "Always",
                    node: null,
                };
            },

            parse: unwrapper,

            command: function(cmd, options){
                return this.save({command: cmd}, options);
            },

            // delete specified volumes from pod model, release Persistent Disks
            deleteVolumes: function(names){
                var volumes = this.get('volumes');
                this.set('volumes', _.filter(volumes, function(volume) {
                    if (!_.contains(names, volume.name))
                        return true;  // leave this volume

                    if (_.has(volume, 'persistentDisk')) {  // release PD
                        _.chain(this.persistentDrives || [])
                            .where({pdName: volume.persistentDisk.pdName})
                            .each(function(disk) { disk.used = false; });
                    }
                    return false;  // remove this volume
                }, this));
            },

            getKubes: function(){
                return this.get('containers').reduce(
                    function(sum, c){ return sum + c.get('kubes'); }, 0);
            },

            recalcInfo: function(package) {
                var containers = this.get('containers'),
                    volumes = this.get('volumes'),
                    kube = _.findWhere(kubeTypes, {id: this.get('kube_type')}),
                    kubePrice = _.findWhere(packageKubes,
                        {package_id: package.id, kube_id: kube.id}).kube_price,
                    totalKubes = this.getKubes();

                this.limits = {
                    cpu: (totalKubes * kube.cpu).toFixed(2) + ' ' + kube.cpu_units,
                    ram: totalKubes * kube.memory + ' ' + kube.memory_units,
                    hdd: totalKubes * kube.disk_space + ' ' + kube.disk_space_units,
                };

                var allPorts = _.flatten(containers.pluck('ports'), true),
                    allPersistentVolumes = _.filter(_.pluck(volumes, 'persistentDisk')),
                    total_size = _.reduce(allPersistentVolumes,
                        function(sum, v) { return sum + v.pdSize; }, 0);
                this.isPublic = _.any(_.pluck(allPorts, 'isPublic'));
                this.isPerSorage = !!allPersistentVolumes.length;

                var rawContainerPrices = containers.map(
                    function(c) { return kubePrice * c.get('kubes'); });
                this.containerPrices = _.map(rawContainerPrices,
                    function(price) { return Utils.getFormattedPrice(package, price); });

                var totalPrice = _.reduce(rawContainerPrices,
                    function(sum, p) { return sum + p; });
                if (this.isPublic)
                    totalPrice += package.price_ip;
                if (this.isPerSorage)
                    totalPrice += package.price_pstorage * total_size;
                this.totalPrice = Utils.getFormattedPrice(package, totalPrice);
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
