define(['app_data/app', 'backbone', 'app_data/utils',
        'backbone-paginator', 'backbone-associations', 'notify'], function(App, Backbone, utils){
    'use strict';

    var data = {},
        unwrapper = function(response) {
            var data = response.hasOwnProperty('data') ? response['data'] : response;
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

    /**
     * Smart sorting for Backbone.PageableCollection
     */
    data.SortableCollectionMixin = {
        /**
         * If you need to sort by some attribute that is not present in model's
         * fields directly, define getForSort in your collection class.
         */
        getForSort: function(model, key){ return model.get(key); },
        /**
         * Call initSortable() when you need to add comparator to the .fullCollection
         */
        initSortable: function(){
            this.fullCollection.comparator = function(a, b){
                var order = this.pageableCollection.order;
                for (var i = 0; i < order.length; i++) {
                    var term = order[i],
                        aVal = this.pageableCollection.getForSort(a, term.key),
                        bVal = this.pageableCollection.getForSort(b, term.key);
                    if (aVal == bVal) continue;
                    return term.order * (aVal > bVal ? 1 : -1);
                }
                return 0;
            };
        },
        /**
         * List of pairs "key-order" for sorting. Next key will be used only if
         * items are equal by previous key.
         */
        order: [{key: 'id', order: 1}],
        orderAsDict: function(){
            return _.mapObject(_.indexBy(this.order, 'key'),
                               function(field){ return field.order; });
        },
        toggleSort: function(key) {
            var term = _.findWhere(this.order, {key: key}) || {key: key, order: -1};
            term.order = term.order === 1 ? -1 : 1;
            // sort by this field first, then by others
            this.order = _.without(this.order, term);
            this.order.unshift(term);

            this.fullCollection.sort();
        },
    };

    data.Container = Backbone.Model.extend({
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
                logs: [],
                logsError: null,
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
            var pod_id = this.getPod().id,
                name = this.get('name');
            return $.ajax({
                url: '/api/logs/container/' + pod_id + '/' + name + '?size=' + size,
                context: this,
                success: function(data){
                    var seriesByTime = _.indexBy(this.get('logs'), 'start');
                    _.each(data.data.reverse(), function(serie) {
                        var lines = serie.hits.reverse(),
                            oldSerie = seriesByTime[serie.start];
                        _.each(lines, function(line){
                            line['@timestamp'] = App.currentUser.localizeDatetime(line['@timestamp']);
                        });
                        serie.start = App.currentUser.localizeDatetime(serie.start);
                        if (serie.end)
                            serie.end = App.currentUser.localizeDatetime(serie.end);
                        if (lines.length && oldSerie && oldSerie.hits.length) {
                            // if we have some logs, append only new lines
                            var first = lines[0],
                                index = _.sortedIndex(oldSerie.hits, first, 'time_nano');
                            lines.unshift.apply(lines, _.first(oldSerie.hits, index));
                        }
                    });
                    this.set('logs', data.data);
                    this.set('logsError', data.data.length ? null : 'Logs not found');
                },
                error: function(xhr) {
                    var data = xhr.responseJSON;
                    if (data && data.data !== undefined)
                        this.set('logsError', data.data);
                },
            });
        },
    }, {  // Class Methods
        fromImage: function(image){
            var _data = _.clone(image instanceof data.Image ? image.attributes : image);
            _data.ports = _.map(_data.ports || [], function(port){
                return {
                    containerPort: port.number,
                    protocol: port.protocol,
                    hostPort: null,
                    isPublic: false
                };
            });
            _data.volumeMounts = _.map(_data.volumeMounts || [], function(vm){
                return {name: null, mountPath: vm};
            });
            return new this(_data);
        }
    });

    data.Pod = Backbone.AssociatedModel.extend({
        urlRoot: '/api/podapi/',
        relations: [{
            type: Backbone.Many,
            key: 'containers',
            relatedModel: data.Container,
        }],

        defaults: function(){
            var kubeTypes = new data.KubeTypeCollection(
                    App.userPackage.getKubeTypes().where({available: true})),
                default_kube = kubeTypes.findWhere({is_default: true}) ||
                    kubeTypes.at(0) || data.KubeType.noAvailableKubeTypes;
            return {
                name: 'Nameless',
                containers: [],
                volumes: [],
                replicas: 1,
                restartPolicy: "Always",
                node: null,
                kube_type: default_kube.id,
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

        recalcInfo: function(pkg) {
            var containers = this.get('containers'),
                volumes = this.get('volumes'),
                kube = App.kubeTypeCollection.get(this.get('kube_type')) ||
                    data.KubeType.noAvailableKubeTypes,
                kubePrice = pkg.priceFor(kube.id) || 0,
                totalKubes = this.getKubes();

            this.limits = {
                cpu: (totalKubes * kube.get('cpu')).toFixed(2) +
                    ' ' + kube.get('cpu_units'),
                ram: totalKubes * kube.get('memory') +
                    ' ' + kube.get('memory_units'),
                hdd: totalKubes * kube.get('disk_space') +
                    ' ' + kube.get('disk_space_units'),
            };

            var allPorts = _.flatten(containers.pluck('ports'), true),
                allPersistentVolumes = _.filter(_.pluck(volumes, 'persistentDisk')),
                total_size = _.reduce(allPersistentVolumes,
                    function(sum, v) { return sum + (v.pdSize || 1); }, 0);
            this.isPublic = _.any(_.pluck(allPorts, 'isPublic'));
            this.isPerSorage = !!allPersistentVolumes.length;

            var rawContainerPrices = containers.map(
                function(c) { return kubePrice * c.get('kubes'); });
            this.containerPrices = _.map(rawContainerPrices,
                function(price) { return pkg.getFormattedPrice(price); });

            var totalPrice = _.reduce(rawContainerPrices,
                function(sum, p) { return sum + p; });
            if (this.isPublic)
                totalPrice += pkg.get('price_ip');
            if (this.isPerSorage)
                totalPrice += pkg.get('price_pstorage') * total_size;
            this.totalPrice = pkg.getFormattedPrice(totalPrice);
        },

        save: function(attrs, options){
            attrs || (attrs = _.clone(this.attributes));

            if (attrs.containers){
                attrs.containers = attrs.containers.toJSON();
                _.each(attrs.containers, function(container){
                    delete container.logs;
                    delete container.logsError;
                });
            }

            return Backbone.Model.prototype.save.call(this, attrs, options);
        },
    });

    data.Image = Backbone.Model.extend({

        defaults: {
            image: 'Imageless'
        },

        parse: unwrapper
    });

    data.Stat = Backbone.Model.extend({
        parse: unwrapper
    });

    data.PodCollection = Backbone.PageableCollection.extend({
        url: '/api/podapi/',
        model: data.Pod,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 8
        },
        initialize: function(){ this.once('reset', this.initSortable); },
        getForSort: function(model, key){
            if (key === 'name')
                return (model.get(key) || '').toLowerCase();
            if (key === 'kubes')
                return model.get('containers').reduce(
                    function(sum, c){ return sum + c.get('kubes'); }, 0);
            return model.get(key);
        },
        searchIn: function(val){
            return this.fullCollection.models.filter(function(i){
                return i.get('name').indexOf(val) === 0;
            });
        },
    });
    _.defaults(data.PodCollection.prototype, data.SortableCollectionMixin);

    data.ImageCollection = Backbone.Collection.extend({
        url: '/api/images/',
        model: data.Image,
        parse: unwrapper
    });

    data.ImagePageableCollection = Backbone.PageableCollection.extend({
        url: '/api/images/',
        model: data.Image,
        parse: unwrapper,
        mode: 'infinite',
        state: {
            pageSize: 10
        }
    });

    data.NodeModel = Backbone.Model.extend({
        logsLimit: 1000,  // max number of lines in logs
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

                    _.each(lines, function(line){
                        line['@timestamp'] = App.currentUser.localizeDatetime(line['@timestamp']);
                    });
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
        appendLogs: function(data){
            this.set('install_log', this.get('install_log') + data + '\n');
            this.trigger('update_install_log');
        }
    });

    data.NodeCollection = Backbone.PageableCollection.extend({
        url: '/api/nodes/',
        model: data.NodeModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        }
    });

    data.StatsCollection = Backbone.Collection.extend({
        url: '/api/stats',
        model: data.Stat,
        parse: unwrapper
    });

    // TODO: Fixed code duplication by moving models from settings_app to a common file
    data.PersistentStorageModel = Backbone.Model.extend({
        defaults: {
            name   : 'Nameless',
            size   : 0,
            in_use : false,
            pod_id : '',
            pod_name : '',
        },
        parse: unwrapper,
    });

    // TODO: Fixed code duplication by moving models from settings_app to a common file
    data.PersistentStorageCollection = Backbone.Collection.extend({
        url: '/api/pstorage',
        model: data.PersistentStorageModel,
        parse: unwrapper
    });

    data.UserModel = Backbone.Model.extend({
        urlRoot: '/api/users/all',
        parse: unwrapper,

        deleteUserConfirmDialog: function(options, text, force){
            var that = this;
            text = text || ('Are you sure you want to delete user "' +
                            this.get('username') + '"?');

            utils.modalDialog({
                title: 'Delete ' + this.get('username') + '?',
                body: text,
                small: true,
                show: true,
                type: force ? 'deleteAnyway' : 'delete' ,
                footer: {
                    buttonOk: function(){ that.deleteUser(options, force); },
                    buttonCancel: true
                }
            });
        },
        deleteUser: function(options, force){
            var that = this;
            utils.preloader.show();
            return this.destroy(_.extend({
                wait:true,
                data: JSON.stringify({force: !!force}),
                contentType: 'application/json; charset=utf-8',
                statusCode: {400: null},  // prevent default error message
            }, options))
            .always(function(){ utils.preloader.hide(); })
            .fail(function(response){
                var responseData = response.responseJSON || {};
                if (!force && responseData.type === 'ResourceReleaseError') {
                    // initiate force delete dialog
                    var message = responseData.data + ' You can try again ' +
                                  'later or delete ignoring these problems."';
                    that.deleteUserConfirmDialog(options, message, true);
                } else {
                    utils.notifyWindow(response);
                }
            });
        },
        loginConfirmDialog: function(options){
            var that = this;
            utils.modalDialog({
                title: "Authorize by " + this.get('username'),
                body: "Are you sure you want to authorize by user '" +
                    this.get('username') + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){ that.login(options); },
                    buttonCancel: true
                }
            });
        },
        login: function(options){
            utils.preloader.show();
            return $.ajax(_.extend({
                url: '/api/users/loginA',
                type: 'POST',
                data: {user_id: this.id},
                success: function(){ window.location.href = '/'; },
                complete: utils.preloader.hide,
                error: utils.notifyWindow,
            }, options));
        },
    });

    data.UsersCollection = Backbone.Collection.extend({
        url: '/api/users/all',
        model: data.UserModel,
        parse: unwrapper
    });

    data.UserActivitiesModel = Backbone.Model.extend({
        urlRoot: '/api/users/a/:id',
        parse: unwrapper
    });

    data.UsersPageableCollection = Backbone.PageableCollection.extend({
        url: '/api/users/all',
        model: data.UserModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 20
        }
    });

    data.ActivitiesCollection = Backbone.PageableCollection.extend({
        url: '/api/users/a/:id',
        model: data.UserActivitiesModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 100
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

    data.AppModel = Backbone.Model.extend({
        defaults: {
            name: '',
            template: '',
            qualifier: '',
            origin: 'kuberdock'
        },
        urlRoot: '/api/predefined-apps',
        parse: unwrapper
    });

    data.AppCollection = Backbone.PageableCollection.extend({
        url: '/api/predefined-apps',
        model: data.AppModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 8
        },
        initialize: function(models){
            this.filtered = new Backbone.PageableCollection(
                null, {mode: 'client', state: this.state});
            _.defaults(this.filtered, data.SortableCollectionMixin);
            this.filtered.getForSort = function(model, key){
                if (key === 'name')
                    return (model.get(key) || '').toLowerCase();
                return model.get(key);
            },
            this.filtered.once('reset', this.filtered.initSortable);
            this.listenTo(this, 'add', this.refilter);
            this.listenTo(this, 'remove', this.refilter);
        },
        filterByOrigin: function(){
            var filtered = this.fullCollection.filter(function(model){
                return _.contains(['kuberdock', 'unknown'], model.get('origin'));
            });
            this.filtered.fullCollection.reset(filtered);
            return this.filtered;
        },
        refilter: function(){
            this.filterByOrigin();
        }
    });

    data.CurrentUserModel = Backbone.Model.extend({
        url: function(){ return '/api/users/editself'; },
        parse: unwrapper,
        localizeDatetime: function(dt, formatString){
            return utils.localizeDatetime({dt: dt, tz: this.get('timezone'),
                                           formatString: formatString});
        },
    });

    data.PermissionModel = Backbone.Model.extend({
        urlRoot: '/api/settings/permissions',
        parse: unwrapper
    });

    data.PermissionsCollection = Backbone.Collection.extend({
        url: '/api/settings/permissions',
        model: data.PermissionModel,
        parse: unwrapper
    });

    data.NotificationModel = Backbone.Model.extend({
        urlRoot: '/api/settings/notifications',
        parse: unwrapper
    });

    data.NotificationsCollection = Backbone.Collection.extend({
        url: '/api/settings/notifications',
        model: data.NotificationModel,
        parse: unwrapper
    });

    data.SettingsModel = Backbone.Model.extend({
        urlRoot: '/api/settings/sysapi',
        parse: unwrapper
    });

    data.SettingsCollection = Backbone.Collection.extend({
        url: '/api/settings/sysapi',
        model: data.SettingsModel,
        parse: unwrapper
    });

    data.NetworkModel = Backbone.Model.extend({
        urlRoot: '/api/ippool/',
        parse: unwrapper
    });

    data.NetworkCollection = Backbone.Collection.extend({
        url: '/api/ippool/',
        model: data.NetworkModel,
        parse: unwrapper
    });

    data.UserAddressModel = Backbone.Model.extend({
        defaults: {
            pod    : ''
        },
        parse: unwrapper
    });

    data.UserAddressCollection = Backbone.Collection.extend({
        url: '/api/ippool/userstat',
        model: data.UserAddressModel,
        parse: unwrapper
    });

    data.MenuModel = Backbone.Model.extend({
        defaults: function(){
            return { children: [], path: '#' };
        }
    });

    data.MenuCollection = Backbone.Collection.extend({
        model: data.MenuModel
    });

    data.LicenseModel = Backbone.Model.extend({
        parse: unwrapper,
        url: '/api/pricing/license'
    });


    // Billing & resources

    data.Package = Backbone.AssociatedModel.extend({
        defaults: function(){
            return {
                currency: 'USD',
                first_deposit: 0,
                id: 0,
                name: 'No name',
                period: 'month',
                prefix: '$',
                price_ip: 0,
                price_over_traffic: 0,
                price_pstorage: 0,
                suffix: ' USD',
            };
        },
        getKubeTypes: function() {
            var kubes = _.chain(this.parents)
                .filter(function(model){ return model instanceof data.PackageKube; })
                .map(function(packageKube){ return packageKube.get('kubeType'); })
                .value();
            return new data.KubeTypeCollection(kubes);
        },
        priceFor: function(kubeID) {
            var packageKube = _.find(this.parents, function(model){
                return model instanceof data.PackageKube &&
                    model.get('kubeType').id == kubeID;
            });
            return packageKube ? packageKube.get('price') : undefined;
        },
        getFormattedPrice: function(price, format) {
            return this.get('prefix') +
                numeral(price).format(format || '0.00') +
                this.get('suffix');
        },
    });

    data.KubeType = Backbone.AssociatedModel.extend({
        defaults: function(){
            return {
                available: false,
                cpu: 0,
                cpu_units: 'Cores',
                disk_space: 0,
                disk_space_units: 'GB',
                id: null,
                included_traffic: 0,
                is_default: null,
                memory: 0,
                memory_units: 'MB',
                name: 'No name',
            };
        },
    });
    data.KubeType.noAvailableKubeTypes = new data.KubeType(
        {name: 'No available kube types', id: 'noAvailableKubeTypes'});
    data.KubeType.noAvailableKubeTypes.notify = function(){
        utils.notifyWindow('There are no available kube types in your package.');
    };
    data.KubeTypeCollection = Backbone.Collection.extend({
        model: data.KubeType,
        comparator: function(kubeType) {
            return !kubeType.get('available');
        },
    });

    data.PackageKube = Backbone.AssociatedModel.extend({
        relations: [{
            type: Backbone.One,
            key: 'kubeType',
            relatedModel: data.KubeType,
        }, {
            type: Backbone.One,
            key: 'package',
            relatedModel: data.Package,
        }],
        defaults: {price: 0},
    });

    return data;
});
