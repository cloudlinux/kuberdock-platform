define(['backbone', 'numeral', 'app_data/app', 'app_data/utils',
        'backbone-paginator', 'backbone-associations', 'notify'],
       function(Backbone, numeral, App, utils){
    'use strict';

    Backbone.syncOrig = Backbone.sync;
    Backbone.sync = function(method, model, options){
        if (!model.noauth)  // by default all models require auth
            options.authWrap = true;
        return Backbone.syncOrig.apply(Backbone, arguments);
    };

    var data = {},
        unwrapper = function(response) {
            var data = response.hasOwnProperty('data') ? response.data : response;
            if (response.status === 'error' || response.status === 'warning')
                utils.notifyWindow(response);
            return data;
        },
        getParentWithType = function(model, typeOfPatent, throughCollection){
            return _.find(model.parents || [],
                          function(parent){ return parent instanceof typeOfPatent; });
        };

    data.DiffCollection = Backbone.Collection.extend({
        initialize: function(models, options){
            this.before = options.before || new Backbone.Collection();
            this.after = options.after || new Backbone.Collection();
            this.modelType = options.modelType || Backbone.Model;
            this.model = Backbone.AssociatedModel.extend({
                relations: [
                    {type: Backbone.One, key: 'before', relatedModel: this.modelType},
                    {type: Backbone.One, key: 'after', relatedModel: this.modelType}
                ],
                addNestedChangeListener: function(obj, callback){
                    if (this.get('before'))
                        obj.listenTo(this.get('before'), 'change', callback);
                    if (this.get('after'))
                        obj.listenTo(this.get('after'), 'change', callback);
                },
            });

            this.recalc();
            this.listenTo(this.before, 'update reset', this.recalc);
            this.listenTo(this.after, 'update reset', this.recalc);
            models.push.apply(models, this.models);
        },
        recalc: function(){
            this.reset([].concat(
                // models "after" change, each with corresponding "before" model or undefined
                this.after.chain().map(function(model){
                    return {id: model.id, before: this.before.get(model.id), after: model};
                }, this).value(),
                // remaining models "before" change (that do not have corresponding "after-model")
                this.before.chain().map(function(model){
                    return {id: model.id, before: model, after: this.after.get(model.id)};
                }, this).reject(_.property('after')).value()
            ));
        },
    });

    /**
     * Smart sorting for Backbone.PageableCollection
     */
    data.SortableCollection = Backbone.PageableCollection.extend({
        mode: 'client',
        constructor: function(){
            Backbone.PageableCollection.apply(this, arguments);
            this.initSortable();
        },
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
                for (var i = 0; i < order.length; i++){
                    var term = order[i],
                        aVal = this.pageableCollection.getForSort(a, term.key),
                        bVal = this.pageableCollection.getForSort(b, term.key);
                    if (aVal == bVal) continue;  // eslint-disable-line eqeqeq
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
        toggleSort: function(key){
            var term = _.findWhere(this.order, {key: key}) || {key: key, order: -1};
            term.order = term.order === 1 ? -1 : 1;
            // sort by this field first, then by others
            this.order = _.without(this.order, term);
            this.order.unshift(term);

            this.fullCollection.sort();
        },
        getFiltered: function(condition){
            var original = this,
                filtered = new this.constructor();
            filtered.refilter = function(){
                var page = this.state.currentPage;
                this.fullCollection.reset(
                    original.fullCollection.filter(condition, this));
                this.getPage(Math.min(page, this.state.lastPage));
            };
            filtered.listenTo(original, 'update reset change', filtered.refilter);
            filtered.refilter();
            return filtered;
        },
    });

    data.VolumeMount = Backbone.AssociatedModel.extend({
        idAttribute: 'mountPath',
        defaults: function(){
            return {name: this.generateName(this.get('mountPath')), mountPath: null};
        },
        generateName: function(){
            return _.map(_.range(10), function(){ return _.random(36).toString(36); }).join('');
        },
        getContainer: function(){ return getParentWithType(this.collection, data.Container); },
        getVolume: function(){
            return _.findWhere(this.getContainer().getPod().get('volumes'),
                               {name: this.get('name')});
        },
    });

    data.Port = Backbone.AssociatedModel.extend({
        defaults: {
            containerPort: null,
            hostPort: null,
            isPublic: false,
            protocol: 'tcp',
        },
        initialize: function(){
            this.on('change', this.resetID);
            this.resetID();
            if (!this.get('hostPort'))
                this.set('hostPort', this.get('containerPort'))
        },
        resetID: function(){
            // modelId works well for collections.get(ID), but it doesn't
            // set model.id attribute
            this.id = data.Ports.prototype.modelId(this.attributes);
        },
        getContainer: function(){ return getParentWithType(this.collection, data.Container); },
    });
    data.Ports = Backbone.Collection.extend({
        model: data.Port,
        modelId: function(attrs){
            return JSON.stringify(_.pick(attrs, 'containerPort', 'protocol'));
        },
    });

    data.EnvVar = Backbone.AssociatedModel.extend({
        idAttribute: 'name',
        defaults: {
            name: 'not set',
            value: '',
        },
        getContainer: function(){ return getParentWithType(this.collection, data.Container); },
    });

    data.Container = Backbone.AssociatedModel.extend({
        idAttribute: 'name',
        relations: [{
            type: Backbone.Many,
            key: 'ports',
            collectionType: data.Ports,
        }, {
            type: Backbone.Many,
            key: 'volumeMounts',
            relatedModel: data.VolumeMount,
        }, {
            type: Backbone.Many,
            key: 'env',
            relatedModel: data.EnvVar,
        }],
        defaults: function(){
            return {
                image: null,
                name: _.random(Math.pow(36, 8)).toString(36),
                ports: [],
                volumeMounts: [],
                env: [],
                command: [],
                args: [],
                kubes: 1,
                terminationMessagePath: null,
            };
        },
        editableAttributes: [  // difference in other attributes won't be interpreted as "change"
            'args', 'command', 'env', 'image', 'kubes', 'ports', 'sourceUrl',
            'volumeMounts', 'workingDir'
        ],
        isChanged: function(compareTo){
            if (!compareTo)
                return false;
            var before = _.partial(_.pick, this.toJSON()).apply(_, this.editableAttributes),
                after = _.partial(_.pick, compareTo.toJSON()).apply(_, this.editableAttributes);
            return !_.isEqual(before, after);
        },
        getPod: function(){ return getParentWithType(this.collection, data.Pod); },
        checkForUpdate: function(){
            var container = this;
            utils.preloader.show();
            return new data.ContainerUpdate({}, {container: container}).fetch()
                .always(utils.preloader.hide).fail(utils.notifyWindow)
                .done(function(rs){
                    container.updateIsAvailable = rs.data;
                    if (!rs.data)
                        utils.notifyWindow('No updates found', 'success');
                });
        },
        getPrettyStatus: function(options){
            options = options || {};
            var state = this.get('state'),
                podStatus = this.getPod().get('status'),
                fakeTransition = options.fakeTransition;

            if (fakeTransition && state === 'running' && podStatus === 'stopping')
                return 'stopping';
            else if (fakeTransition && state === 'stopped' && podStatus === 'preparing')
                return 'deploying';
            else if (state === 'running' && !this.get('ready'))
                return 'pending';
            return state || 'stopped';
        },
        update: function(){
            var model = this;
            utils.modalDialog({
                title: 'Update container',
                body: 'During update whole pod will be restarted. Continue?',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        new data.ContainerUpdate({}, {container: model}).save()
                            .always(utils.preloader.hide).fail(utils.notifyWindow)
                            .done(function(){ model.updateIsAvailable = undefined; });
                    },
                    buttonCancel: true,
                },
            });
        },
        getLogs: function(size){
            size = size || 100;
            var podID = this.getPod().id,
                name = this.get('name');
            return $.ajax({  // TODO: use Backbone.Model
                authWrap: true,
                url: '/api/logs/container/' + podID + '/' + name + '?size=' + size,
                context: this,
            }).done(function(data){
                var seriesByTime = _.indexBy(this.logs, 'start');
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
                this.logs = data.data;
                this.logsError = data.data.length ? null : 'Logs not found';
            }).fail(function(xhr) {
                var data = xhr.responseJSON;
                if (data && data.data !== undefined)
                    this.logsError = data.data;
            });
        },
    }, {  // Class Methods
        fromImage: function(image){
            var data = JSON.parse(JSON.stringify(image));
            data.ports = _.map(data.ports, function(port){
                return {
                    containerPort: port.number,
                    protocol: port.protocol,
                };
            });
            data.volumeMounts = _.map(data.volumeMounts,
                                       function(vm){ return {mountPath: vm}; });
            data.env = _.map(data.env, _.clone);
            data.command = data.command.slice(0);
            data.args = data.args.slice(0);
            return new this(data);
        },
        validateMountPath: function(mountPath){
            if (mountPath && mountPath.length < 2)
                return 'Mount path minimum length is 3 symbols';
            else if (mountPath.length > 30)
                return 'Mount path maximum length is 30 symbols';
            else if (!/^[\w/.-]*$/.test(mountPath))
                return 'Mount path should contain letters of Latin alphabet ' +
                       'or "/", "_", "-" symbols';
        },
    });

    data.ContainerUpdate = Backbone.Model.extend({
        url: function(){
            return this.container.getPod().url() + '/' + this.container.id + '/update';
        },
        initialize: function(attributes, options){
            this.container = options.container;
        },
    });

    data.Pod = Backbone.AssociatedModel.extend({
        urlRoot: '/api/podapi/',
        relations: [{
            type: Backbone.Many,
            key: 'containers',
            relatedModel: data.Container,
        }, {
            type: Backbone.One,
            key: 'edited_config',
            relatedModel: Backbone.Self,
        }],

        resetSshAccess: function(){
            var that = this;
            utils.preloader.show();
            $.ajax({
                url: '/api/podapi/' + that.id + '/reset_direct_access_pass',
                authWrap: true,
            })
            .done(function(response) {
                that.set('direct_access', response.data);
                utils.notifyWindow('SSH credentials are updated.' +
                ' See table below in column SSH.', 'success');
            })
            .always(utils.preloader.hide).fail(utils.notifyWindow);
        },

        defaults: function(){
            var kubeTypes = new data.KubeTypeCollection(
                    App.userPackage.getKubeTypes().where({available: true})),
                defaultKube = kubeTypes.findWhere({is_default: true}) ||
                    kubeTypes.at(0) || data.KubeType.noAvailableKubeTypes;
            return {
                name: 'Nameless',
                containers: [],
                volumes: [],
                replicas: 1,
                restartPolicy: 'Always',
                node: null,
                kube_type: defaultKube.id,
                status: 'stopped',
            };
        },
        editableAttributes: [
            // difference in other attributes won't be interpreted as "change"
            'kube_type', 'restartPolicy', 'volumes', 'containers',
            'kuberdock_resolve',
        ],
        persistentAttributes: [
            // only those attributes will be copied in a new `edited_config`
            // we don't need stuff like "status" there
            'kube_type', 'restartPolicy', 'volumes', 'containers',
            'kuberdock_resolve', 'domain',
        ],
        isChanged: function(compareTo){
            if (!compareTo){
                if (this.applyingChangesStarted &&
                        +new Date() - this.applyingChangesStarted < 120000)
                    return false;  // user hit "apply" less then 2 minutes ago
                compareTo = this.get('edited_config');
                if (!compareTo)
                    return false;
            }
            var attrs = _.without(this.editableAttributes, 'containers'),
                before = _.partial(_.pick, this.toJSON()).apply(_, attrs),
                after = _.partial(_.pick, compareTo.toJSON()).apply(_, attrs);
            return !_.isEqual(before, after) ||
                this.getContainersDiffCollection().any(function(container){
                    var before = container.get('before'),
                        after = container.get('after');
                    return !before || !after || before.isChanged(after);
                });
        },

        parse: unwrapper,

        initialize: function(){
            this.on('remove:containers', function(container){
                this.deleteVolumes(container.get('volumeMounts').pluck('name'));
            });
            this.on('change:containers[*].ports[*].isPublic', function(model, value){
                if (value && this.countPublicPorts() === 1)
                    this.trigger('change-public-access-need', true);
                if (this.countPublicPorts() === 0)
                    this.trigger('change-public-access-need', false);
            });
        },

        // if it's "edited_config" of some other pod, get that pod:
        // pod.editOf() === undefined || pod.editOf().get('edited_config') === pod
        editOf: function(){ return getParentWithType(this, data.Pod); },
        deepClone: function(){ return new data.Pod(utils.deepClone(this.toJSON())); },
        getContainersDiffCollection: function(){
            if (this._containersDiffCollection)
                return this._containersDiffCollection;
            var before = this,
                getAfter = function(){
                    return before.get('edited_config') || before.deepClone();
                },
                diff = new data.DiffCollection(
                    [], {modelType: data.Container, before: before.get('containers'),
                         after: getAfter().get('containers')}),
                resetDiff = function(){
                    diff.after = getAfter().get('containers');
                    diff.recalc();
                };
            diff.listenTo(this, 'change', resetDiff);
            this._containersDiffCollection = diff;
            return this._containersDiffCollection;
        },

        command: function(cmd, commandOptions){
            // patch should include previous `set`
            var data = _.extend(this.changedAttributes() || {},
                                {command: cmd, commandOptions: commandOptions || {}});
            return this.save(data, {wait: true, patch: true});
        },

        getPrettyStatus: function(){
            var status = this.get('status');
            if (status === 'running' && !this.get('ready'))
                return 'pending';
            else if (status === 'preparing')
                return 'deploying';
            return status || 'stopped';
        },

        ableTo: function(command){
            // 'unpaid', 'stopped', 'stopping', 'waiting', 'pending',
            // 'preparing', 'running', 'failed', 'succeeded'
            var status = this.get('status');
            if (command === 'start')
                return _.contains(['stopped'], status);
            if (command === 'redeploy')
                return _.contains(['stopping', 'waiting', 'pending', 'running',
                                   'failed', 'succeeded', 'preparing'], status);
            if (command === 'stop' || command === 'restart')
                return _.contains(['stopping', 'waiting', 'pending', 'running',
                                   'failed', 'succeeded', 'preparing'], status);
            if (command === 'pay-and-start')
                return _.contains(['unpaid'], status);
            if (command === 'delete')
                return _.contains(['unpaid', 'stopped', 'stopping', 'waiting',
                                   'running', 'failed', 'succeeded'], status);
        },

        /**
         * Add to kubeTypes info about conflicts with pod's PDs.
         * Also, if pod's kubeType conflicts with some of pod's PDs, reset it.
         */
        solveKubeTypeConflicts: function(){
            var kubeTypes = App.userPackage.getKubeTypes();
            kubeTypes.map(function(kt){ kt.conflicts = new data.PersistentStorageCollection(); });
            if (this.persistentDrives){
                _.each(this.get('volumes'), function(volume){
                    if (volume.persistentDisk){
                        var pd = this.persistentDrives
                                .findWhere({name: volume.persistentDisk.pdName});
                        if (pd){
                            var kubeType = pd.get('kube_type');
                            if (kubeType != null){
                                kubeTypes.each(function(kt){
                                    if (kt.id !== kubeType)
                                        kt.conflicts.add(pd);
                                });
                            }
                        }
                    }
                }, this);
            }
            kubeTypes = new data.KubeTypeCollection(kubeTypes.filter(
                function(kt){ return kt.get('available') && !kt.conflicts.length; }));

            if (!kubeTypes.get(this.get('kube_type'))){
                if (!kubeTypes.length)
                    this.set('kube_type', data.KubeType.noAvailableKubeTypes.id);
                else
                    this.unset('kube_type');  // no longer available
            }
        },

        // delete specified volumes from pod model, release Persistent Disks
        deleteVolumes: function(names){
            var volumes = this.get('volumes');
            this.set('volumes', _.filter(volumes, function(volume) {
                if (!_.contains(names, volume.name))
                    return true;  // leave this volume

                if (volume.persistentDisk && this.persistentDrives) {  // release PD
                    _.each(
                        this.persistentDrives.where({name: volume.persistentDisk.pdName}),
                        function(disk){ disk.set('in_use', false); });
                }
                return false;  // remove this volume
            }, this));
        },

        getKubes: function(){
            return this.get('containers').reduce(
                function(sum, c){ return sum + c.get('kubes'); }, 0);
        },

        getKubeType: function(){
            return App.kubeTypeCollection.get(this.get('kube_type')) ||
                data.KubeType.noAvailableKubeTypes;
        },

        getPublicPorts: function(){
            return this.get('containers').chain()
                .map(function(c){ return c.get('ports').toJSON(); })
                .flatten(true).where({isPublic: true}).value();
        },

        countPublicPorts: function(){ return this.getPublicPorts().length; },

        publicPortsShouldContain: function(){
            var portsList = _.toArray(arguments);
            return _.any(this.getPublicPorts(), function(port){
                return _.contains(portsList, port.hostPort || port.containerPort);
            });
        },

        recalcInfo: function(pkg){
            pkg = pkg || App.userPackage;
            var containers = this.get('containers'),
                volumes = this.get('volumes'),
                kube = this.getKubeType(),
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

            var allPersistentVolumes = _.filter(_.pluck(volumes, 'persistentDisk')),
                totalSize = _.reduce(allPersistentVolumes,
                    function(sum, v){ return sum + (v.pdSize || 1); }, 0),
                totalPrice = 0;
            this.isPublic = !!this.countPublicPorts();
            this.isPerSorage = !!allPersistentVolumes.length;

            containers.each(function(container){
                var kubes = container.get('kubes');
                container.limits = {
                    cpu: (kubes * kube.get('cpu')).toFixed(2) + ' ' + kube.get('cpu_units'),
                    ram: kubes * kube.get('memory') + ' ' + kube.get('memory_units'),
                    hdd: kubes * kube.get('disk_space') + ' ' + kube.get('disk_space_units'),
                };
                container.rawPrice = kubePrice * kubes;
                container.price = pkg.getFormattedPrice(container.rawPrice);
                totalPrice += container.rawPrice;
            });

            if (this.isPublic && !this.get('domain'))
                totalPrice += pkg.get('price_ip');
            if (this.isPerSorage)
                totalPrice += pkg.get('price_pstorage') * totalSize;
            this.rawTotalPrice = totalPrice;
            this.totalPrice = pkg.getFormattedPrice(totalPrice);
        },
        waitForStatus: function(statuses){
            var deferred = $.Deferred(),
                checker = function(){
                    if (_.contains(statuses, this.get('status')))
                        deferred.resolveWith(this);
                    else
                        this.once('change:status', checker);
                };
            checker.call(this);
            return deferred.promise();
        },

        // commands with common app/UI interactions, return promise
        cmdStart: function(){
            utils.preloader.show();
            return this.command('start')
                .always(utils.preloader.hide).fail(utils.notifyWindow);
        },
        cmdStop: function(){
            utils.preloader.show();
            return this.command('stop')
                .always(utils.preloader.hide).fail(utils.notifyWindow);
        },
        cmdPayAndStart: function(){
            var deferred = new $.Deferred(),
                model = this;
            App.getSystemSettingsCollection().done(function(settingCollection){
                var billingType = settingCollection.findWhere({
                    name: 'billing_type'}).get('value');
                if (billingType.toLowerCase() === 'no billing') {
                    model.cmdStart().then(deferred.resolve, deferred.reject);
                } else {
                    utils.preloader.show();
                    $.ajax({  // TODO: use Backbone.Model
                        authWrap: true,
                        type: 'POST',
                        contentType: 'application/json; charset=utf-8',
                        url: '/api/billing/order',
                        data: JSON.stringify({
                            pod: JSON.stringify(model.attributes)
                        })
                    }).always(
                        utils.preloader.hide
                    ).fail(
                        utils.notifyWindow
                    ).done(function(response){
                        if (response.data.status === 'Paid') {
                            deferred.resolveWith(model, arguments);
                        } else {
                            utils.modalDialog({
                                title: 'Insufficient funds',
                                body: 'Your account funds seem to be' +
                                      ' insufficient for the action.' +
                                      ' Would you like to go to billing' +
                                      ' system to make the payment?',
                                small: true,
                                show: true,
                                footer: {
                                    buttonOk: function(){
                                        window.location = response.data.redirect;
                                    },
                                    buttonCancel: function(){
                                        deferred.rejectWith(model, []);
                                    },
                                    buttonOkText: 'Go to billing',
                                    buttonCancelText: 'No, thanks',
                                }
                            });
                        }
                    });
                }
            });
            return deferred.promise();
        },
        cmdApplyChanges: function(){
            var deferred = new $.Deferred(),
                model = this;
            App.getSystemSettingsCollection().done(function(settings){
                var fixedPrice = App.userPackage.get('count_type') === 'fixed' &&
                    settings.byName('billing_type')
                    .get('value').toLowerCase() !== 'no billing';
                if (!fixedPrice){
                    var cmd = model.ableTo('start') ? 'start' : 'redeploy';
                    return model.command(cmd, {applyEdit: true})
                        .done(function(){
                            model.applyingChangesStarted = +new Date();
                            model.trigger('apply-changes-start');
                        })
                        .fail(utils.notifyWindow)
                        .then(deferred.resolve, deferred.reject);
                }
                if (model.ableTo('stop')){
                    // Workaround for better error-handling: restart and stop
                    // are asynchronous, so billing might not get any error
                    // from KD API directly.
                    // Stop pod and then go to billing.
                    utils.notifyWindow('Pod will be restarted...', 'success');
                    $.when(
                        model.command('stop'),
                        model.waitForStatus(['stopped'])
                    ).done(function(){
                        model.cmdApplyChanges()
                            .then(deferred.resolve, deferred.reject);
                    }).fail(utils.notifyWindow, deferred.reject);
                    return deferred.promise();
                }
                new Backbone.Model().save({pod: model}, {url: '/api/billing/orderPodEdit'})
                    .fail(utils.notifyWindow, _.bind(deferred.reject, deferred))
                    .done(function(response){
                        if (response.data.status === 'Paid') {
                            if (model.get('status') !== 'running')
                                model.set('status', 'pending');
                            model.get('containers').each(function(c){
                                if (c.get('state') !== 'running')
                                    c.set('state', 'pending');
                            });
                            model.applyingChangesStarted = +new Date();
                            model.trigger('apply-changes-start');
                            deferred.resolve();
                            App.navigate('pods/' + model.id, {trigger: true});
                            return;
                        }
                        utils.modalDialog({
                            title: 'Insufficient funds',
                            body: 'Your account funds seem to be' +
                                  ' insufficient for the action.' +
                                  ' Would you like to go to billing' +
                                  ' system to make the payment?',
                            small: true,
                            show: true,
                            footer: {
                                buttonOk: function(){
                                    window.location = response.data.redirect;
                                },
                                buttonCancel: function(){
                                    deferred.reject();
                                },
                                buttonOkText: 'Go to billing',
                                buttonCancelText: 'No, thanks'
                            }
                    });
                });
            });
            return deferred.promise();
        },
        cmdRestart: function(){
            var deferred = new $.Deferred(),
                model = this,
                name = model.get('name');
            utils.modalDialog({
                title: 'Confirm restarting of application ' + _.escape(name),
                body: 'You can wipe out all the data and redeploy the ' +
                      'application or you can just restart and save data ' +
                      'in Persistent storages of your application.',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        model.command('redeploy')
                            .always(utils.preloader.hide).fail(utils.notifyWindow)
                            .done(function(){
                                utils.notifyWindow('Pod will be restarted soon', 'success');
                            }).then(deferred.resolve, deferred.reject);
                    },
                    buttonCancel: function(){
                        utils.modalDialog({
                            title: 'Confirm restarting of application ' + _.escape(name),
                            body: 'Are you sure you want to delete all data? You will ' +
                                  'not be able to recover this data if you continue.',
                            small: true,
                            show: true,
                            footer: {
                                buttonOk: function(){
                                    utils.preloader.show();
                                    model.command('redeploy', {wipeOut: true})
                                        .always(utils.preloader.hide).fail(utils.notifyWindow)
                                        .done(function(){
                                            utils.notifyWindow('Pod will be restarted soon',
                                                               'success');
                                        }).then(deferred.resolve, deferred.reject);
                                },
                                buttonOkText: 'Continue',
                                buttonOkClass: 'btn-danger',
                                buttonCancel: true
                            }
                        });
                    },
                    buttonOkText: 'Just Restart',
                    buttonCancelText: 'Wipe Out',
                    buttonCancelClass: 'btn-danger',
                }
            });
            return deferred.promise();
        },
        cmdDelete: function(){
            var deferred = new $.Deferred(),
                model = this,
                name = model.get('name');
            utils.modalDialogDelete({
                title: 'Delete ' + _.escape(name) + '?',
                body: "Are you sure you want to delete pod '" + _.escape(name) + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        model.destroy({wait: true})
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow)
                            .done(function(){
                                App.getPodCollection().done(function(col){
                                    col.remove(model);
                                });
                            }).then(deferred.resolve, deferred.reject);
                    },
                    buttonCancel: true
                }
            });
            return deferred.promise();
        },
    });

    data.Image = Backbone.Model.extend({
        url: '/api/images/new',
        idAttribute: 'image',
        defaults: function(){
            return {
                image: 'Imageless',
                args: [],
                command: [],
                ports: [],
                volumeMounts: [],
            };
        },
        parse: unwrapper,
        fetch: function(options){
            return Backbone.Model.prototype.fetch.call(this, _.extend({
                contentType: 'application/json; charset=utf-8',
                type: 'POST',
            }, options));
        },
    });

    data.Stat = Backbone.Model.extend({
        parse: unwrapper,
        defaults: function(){
            return {
                lines: 2,
                points: [],
                series: [],
            };
        },
    });

    data.PodCollection = data.SortableCollection.extend({
        url: '/api/podapi/',
        model: data.Pod,
        parse: unwrapper,
        state: {
            pageSize: 8
        },
        getForSort: function(model, key){
            if (key === 'name')
                return (model.get(key) || '').toLowerCase();
            if (key === 'kubes')
                return model.get('containers').reduce(
                    function(sum, c){ return sum + c.get('kubes'); }, 0);
            return model.get(key);
        },
        allChecked: function(){
            var checkable = this.fullCollection.filter(
                function(m){ return m.get('status') !== 'deleting'; });
            return checkable.length && _.all(_.pluck(checkable, 'is_checked'));
        },
        checkedItems: function(){
            return this.fullCollection.filter(function(m){ return m.is_checked; });
        },
    });
    App.getPodCollection = App.resourcePromiser('podCollection', data.PodCollection);


    data.ImageSearchItem = Backbone.Model.extend({
        idAttribute: 'name',
        parse: unwrapper,
    });

    data.ImageSearchCollection = Backbone.Collection.extend({
        url: '/api/images/',
        model: data.ImageSearchItem,
        parse: unwrapper
    });

    data.ImageSearchPageableCollection = Backbone.PageableCollection.extend({
        url: '/api/images/',
        model: data.ImageSearchItem,
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
                ip: '',
                logs: [],
                logsError: null,
            };
        },
        getLogs: function(size){
            size = size || 100;
            return $.ajax({  // TODO: use Backbone.Model
                authWrap: true,
                url: '/api/logs/node/' + this.get('hostname') + '?size=' + size,
                context: this,
            }).done(function(data) {
                var oldLines = this.get('logs'),
                    lines = data.data.hits.reverse();

                _.each(lines, function(line){
                    line['@timestamp'] = App.currentUser.localizeDatetime(line['@timestamp']);
                });
                if (lines.length && oldLines.length) {
                    // if we have some logs, append only new lines
                    var first = lines[0],
                        indexTo = _.sortedIndex(oldLines, first, 'time_nano'),
                        indexFrom = Math.max(0, indexTo + lines.length - this.logsLimit);
                    lines.unshift.apply(lines, oldLines.slice(indexFrom, indexTo));
                }

                this.set('logs', lines);
                this.set('logsError', null);
            }).fail(function(xhr) {
                var data = xhr.responseJSON;
                if (data && data.data !== undefined)
                    this.set('logsError', data.data);
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
    App.getNodeCollection = App.resourcePromiser('nodeCollection', data.NodeCollection);

    data.StatsCollection = Backbone.Collection.extend({
        url: '/api/stats',
        model: data.Stat,
        parse: unwrapper,
        setEmpty: function(noNetwork){
            var emptyLines = [{
                series: [{label: 'available'}, {label: 'cpu load'}],
                title: 'CPU', ylabel: '%'
            }, {
                series: [{label: 'available'}, {fill: true, label: 'used'}],
                title: 'Memory', ylabel: 'MB'
            }, {
                series: [{fill: 'true', label: 'in'}, {label: 'out'}],
                title: 'Network', ylabel: 'bps'
            }];
            if (noNetwork)
                emptyLines.pop();
            this.reset(emptyLines);
        }
    });

    data.PodStatsCollection = data.StatsCollection.extend({
        initialize: function(models, options){
            this.podId = options.podId;
        },
        url: function(){
            return '/api/stats/pods/' + this.podId;
        }
    });

    data.ContainerStatsCollection = data.StatsCollection.extend({
        initialize: function(models, options){
            this.podId = options.podId;
            this.containerId = options.containerId;
        },
        url: function(){
            return '/api/stats/' + ['pods', this.podId, 'containers', this.containerId].join('/');
        }
    });

    // TODO: Fixed code duplication by moving models from settings_app to a common file
    data.PersistentStorageModel = Backbone.Model.extend({
        defaults: {
            name: 'Nameless',
            size: 1,
            in_use: false,
            pod_id: '',
            pod_name: '',
            available: true,
            node_id: undefined,
            kube_type: undefined,
        },
        parse: unwrapper,
        /**
         * Find all PDs from parent collection in pod, that conflict with this one.
         *
         * @param {data.Pod} pod - pod model
         * @param {data.PersistentStorageModel} ignored - ignore conflicts with this PD
         */
        conflictsWith: function(pod, ignored){
            if (this.get('node_id') == null)
                return new data.PersistentStorageCollection();
            var podDisks = _.chain(pod.get('volumes'))
                    .pluck('persistentDisk').filter().pluck('pdName').value();

            return new data.PersistentStorageCollection(this.collection.filter(function(pd){
                return pd !== this && pd !== ignored &&
                    _.contains(podDisks, pd.get('name')) &&
                    pd.get('node_id') != null &&
                    pd.get('node_id') !== this.get('node_id');
            }, this));
        },
    });

    // TODO: Fixed code duplication by moving models from settings_app to a common file
    data.PersistentStorageCollection = Backbone.Collection.extend({
        url: '/api/pstorage',
        model: data.PersistentStorageModel,
        parse: unwrapper,
    });
    data.PaginatedPersistentStorageCollection = data.SortableCollection.extend({
        url: '/api/pstorage',
        model: data.PersistentStorageModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        }
    });

    data.UserModel = Backbone.Model.extend({
        urlRoot: '/api/users/all',
        parse: unwrapper,
        defaults: function(){
            return {
                username: '',
                first_name: '',
                last_name: '',
                middle_initials: '',
                email: '',
                timezone: 'GMT (+00:00)',
                rolename: 'User',
                active: true,
                suspended: false,
                actions: {
                    lock: true,
                    delete: true,
                    suspend: true,
                },
            };
        },

        deleteUserConfirmDialog: function(options, text, force){
            var that = this;
            text = text || ('Are you sure you want to delete user "' +
                            this.get('username') + '"?');

            utils.modalDialog({
                title: 'Delete ' + this.get('username') + '?',
                body: text,
                small: true,
                show: true,
                type: force ? 'deleteAnyway' : 'delete',
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
                title: 'Authorize by ' + this.get('username'),
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
            return new Backbone.Model()
                .save({user_id: this.id}, _.extend({url: '/api/users/loginA'}, options))
                .done(function(){ App.navigate('').cleanUp(/*keepToken*/true).initApp(); })
                .always(utils.preloader.hide)
                .fail(utils.notifyWindow);
        },
    }, {
        checkUsernameFormat: function(username){
            if (username.length > 25)
                return 'Maximum length is 25 symbols.';
            if (!/^[A-Z\d_-]+$/i.test(username))
                return 'Only "-", "_" and alphanumeric symbols are allowed.';
            if (!/^[A-Z\d](?:.*[A-Z\d])?$/i.test(username))
                return 'Username should start and end with a letter or digit.';
            if (!/\D/g.test(username))
                return 'Username cannot consist of digits only.';
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
            pageSize: 10
        }
    });
    App.getUserCollection = App.resourcePromiser('userCollection', data.UsersPageableCollection);
    App.getTimezones = App.resourcePromiser('timezoneList', '/api/settings/timezone-list');
    App.getRoles = App.resourcePromiser('roles', '/api/users/roles');

    data.ActivitiesCollection = Backbone.PageableCollection.extend({
        url: '/api/users/a/:id',
        model: data.UserActivitiesModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 100
        }
    });

    data.NodeStatsCollection = data.StatsCollection.extend({
        initialize: function(models, options){
            this.hostname = options.hostname;
        },
        url: function() {
            return '/api/stats/nodes/' + this.hostname;
        }
    });

    data.AppModel = Backbone.Model.extend({
        defaults: {
            name: '',
            template: '',
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
            this.filtered = new data.SortableCollection(
                null, {state: this.state});
            this.filtered.getForSort = function(model, key){
                if (key === 'name')
                    return (model.get(key) || '').toLowerCase();
                return model.get(key);
            };
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
        defaults: {
            impersonated: false
        },
        localizeDatetime: function(dt, formatString){
            return utils.localizeDatetime({dt: dt, tz: this.get('timezone'),
                                           formatString: formatString});
        },
        isImpersonated: function(){  // TODO-JWT: get this data from token
            return this.get('impersonated');
        },
        roleIs: function(/* ...roles */){
            for (var i = 0; i < arguments.length; i++){
                if (this.get('rolename') === arguments[i])
                    return true;
            }
            return false;
        },
    });
    App.getCurrentUser = App.resourcePromiser('user', data.CurrentUserModel);

    data.SettingsModel = Backbone.Model.extend({
        urlRoot: '/api/settings/sysapi',
        parse: unwrapper
    });

    data.SettingsCollection = Backbone.Collection.extend({
        url: '/api/settings/sysapi',
        model: data.SettingsModel,
        parse: unwrapper,
        comparator: function(model){ return model.id; },
        byName: function(name){ return this.findWhere({name: name}); },
        filterByGroup: function(group){ return this.filter({setting_group: group}); }
    });
    App.getSystemSettingsCollection = App.resourcePromiser(
        'systemSettingsCollection', data.SettingsCollection);

    data.NetworkModel = Backbone.Model.extend({
        urlRoot: '/api/ippool/',
        parse: unwrapper,
        getIPs: function(){
            var subnet = this,
                getRawIPs = function(){
                    var allocation = subnet.get('allocation'),
                        names = allocation.length === 3
                            ? ['ip', 'podName', 'status']
                            : ['ip', 'podName', 'status', 'userName'];
                    return _.map(allocation, _.partial(_.object, names));
                },
                IPsCollection = new data.IPsCollection(getRawIPs());
            IPsCollection.listenTo(this, 'change:allocation', function(){
                var page = IPsCollection.state.currentPage;
                IPsCollection.fullCollection.reset(getRawIPs());
                IPsCollection.getPage(page);
            });
            return IPsCollection;
        },
    });

    data.NetworkCollection = Backbone.PageableCollection.extend({
        url: '/api/ippool/',
        model: data.NetworkModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 8
        }
    });

    App.getIppoolMode = App.resourcePromiser('ippoolMode', '/api/ippool/mode');
    App.getIPPoolCollection = App.resourcePromiser('ippoolCollection', data.NetworkCollection);

    data.IPModel = Backbone.Model.extend({
        idAttribute: 'ip',
    });
    data.IPsCollection = data.SortableCollection.extend({
        model: data.IPModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 8
        },
        order: [{key: 'ip', order: 1}],
        getForSort: function(model, key){
            if (key === 'ip')
                return model.get('ip').replace(/\b\d{1}\b/g, '00$&').replace(/\b\d{2}\b/g, '0$&');
            return model.get(key);
        },
    });

    data.DomainModel = Backbone.Model.extend({
        urlRoot: '/api/domains/',
        parse: unwrapper,
    });

    data.DomainsCollection = Backbone.PageableCollection.extend({
        url: '/api/domains/',
        model: data.DomainModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 8,
        },
    });

    App.getDomainsCollection = App.resourcePromiser(
        'domainsCollection', data.DomainsCollection);

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

    data.BreadcrumbsControls = Backbone.Model.extend({
        defaults: {button: false, search: false},
    });

    data.MenuModel = Backbone.Model.extend({
        defaults: function(){
            return { children: [], path: '#' };
        }
    });

    data.MenuCollection = Backbone.Collection.extend({
        url: '/api/settings/menu',
        model: data.MenuModel,
        parse: unwrapper,
    });
    App.getMenuCollection = App.resourcePromiser('menu', data.MenuCollection);

    data.NotificationCollection = Backbone.Collection.extend({
        url: '/api/settings/notifications',
        parse: unwrapper,
    });
    App.getNotificationCollection = App.resourcePromiser(
        'notifications', data.NotificationCollection);

    data.LicenseModel = Backbone.Model.extend({
        parse: unwrapper,
        url: '/api/pricing/license'
    });
    App.getLicenseModel = App.resourcePromiser('licenseModel', data.LicenseModel);


    // Billing & resources

    data.Package = Backbone.AssociatedModel.extend({
        url: function(){
            return '/api/pricing/packages/' + this.id + '?with_kubes=1&with_internal=1';
        },
        parse: unwrapper,
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
        initialize: function(attributes, options){
            var kubes = this.get('kubes');
            this.unset('kubes');
            if (App.packageCollection == null)
                App.packageCollection = new data.PackageCollection();
            if (App.kubeTypeCollection == null)
                App.kubeTypeCollection = new data.KubeTypeCollection();
            if (App.packageKubeCollection == null)
                App.packageKubeCollection = new data.PackageKubeCollection();
            App.packageCollection.add(this);
            _.each(kubes, function(kube){
                App.kubeTypeCollection.add(kube);
                App.packageKubeCollection.add({package_id: this.id,
                                               kube_id: kube.id,
                                               kube_price: kube.price});
            }, this);
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
                    model.get('kubeType').id === kubeID;
            });
            return packageKube ? packageKube.get('kube_price') : undefined;
        },
        getFormattedPrice: function(price, format) {
            return this.get('prefix') +
                numeral(price).format(format || '0.00') +
                this.get('suffix');
        },
    });
    data.PackageCollection = Backbone.Collection.extend({
        url: '/api/pricing/packages/?with_kubes=1&with_internal=1',
        model: data.Package,
        parse: unwrapper,
    });
    App.getPackages = App.resourcePromiser('packages', data.PackageCollection);

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
    data.KubeType.noAvailableKubeTypes.notifyConflict = function(){
        // Case, when there are no available kube types, 'cause of conflicts with pod's PDs.
        // TODO: better message
        utils.notifyWindow('You cannot use selected Persistent Disks with any ' +
                           'available Kube Types.');
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
        defaults: {kube_price: 0},
        initialize: function(){
            this.reattach();
            this.on('change:package_id change:kube_id', this.reattach);
        },
        reattach: function(){
            this.set('kubeType', App.kubeTypeCollection.get(this.get('kube_id')));
            this.set('package', App.packageCollection.get(this.get('package_id')));
        },
    });
    data.PackageKubeCollection = Backbone.Collection.extend({
        model: data.PackageKube,
    });

    data.AuthModel = Backbone.Model.extend({
        noauth: true,
        urlRoot: '/api/auth/token2',
        defaults: {
            username: 'Nameless'
        },
        parse: function(data){
            return data.status === 'OK' ? _.omit(data, 'status') : {};
        }
    });

    return data;
});
