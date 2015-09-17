define(['pods_app/app', 'pods_app/models/pods'], function(Pods){
    Pods.module("WorkFlow", function(WorkFlow, App, Backbone, Marionette, $, _){
        WorkFlow.getCollection = function(){
            if (!WorkFlow.hasOwnProperty('PodCollection')) {
                WorkFlow.PodCollection = new App.Data.PodCollection(podCollectionData);
            }
            return WorkFlow.PodCollection;
        }

        WorkFlow.Router = Marionette.AppRouter.extend({
            appRoutes: {
                'pods': 'showPods',
                'pods/:id': 'showPodItem',
                'newpod': 'createPod',
                'poditem/:id/:name': 'showPodContainer'
            }
        });

        WorkFlow.Controller = Marionette.Controller.extend({

            showPods: function(){
                var that = this;
                require(['pods_app/views/pods_list',
                         'pods_app/views/breadcrumbs',
                         'pods_app/views/paginator'], function(){
                    var listLayout = new App.Views.List.PodListLayout(),
                        breadcrumbsData = {breadcrumbs: [{name: 'Pods'}],
                                           buttonID: 'add_pod',
                                           buttonLink: '/#newpod',
                                           buttonTitle: 'Add new container'},
                        breadcrumbsModel = new Backbone.Model(breadcrumbsData)
                        breadcrumbs = new App.Views.Misc.Breadcrumbs({model: breadcrumbsModel}),
                        podCollection = new App.Views.List.PodCollection({
                            collection: WorkFlow.getCollection()
                        });

                    that.listenTo(listLayout, 'show', function(){
                        listLayout.header.show(breadcrumbs);
                        listLayout.list.show(podCollection);
                        listLayout.pager.show(
                            new App.Views.Paginator.PaginatorView({
                                view: podCollection
                            })
                        );
                    });

                    that.listenTo(listLayout, 'clear:pager', function(){
                        listLayout.pager.empty();
                    });

                    that.listenTo(listLayout, 'collection:filter', function(data){
                        if (data.length < 2) {
                            var collection = WorkFlow.getCollection();
                        }
                        else {
                            var collection = new App.Data.PodCollection(WorkFlow.getCollection().searchIn(data));
                        }
                        view = new App.Views.List.PodCollection({collection: collection});
                        listLayout.list.show(view);
                        listLayout.pager.show(new App.Views.Paginator.PaginatorView({view: view}));
                    });

                    App.contents.show(listLayout);
                });
            },

            showPodItem: function(id){
                var that = this;
                require(['pods_app/views/pod_item',
                         'pods_app/views/paginator'], function(){
                    var itemLayout = new App.Views.Item.PodItemLayout(),
                        model = WorkFlow.getCollection().fullCollection.get(id);

                    if (model === undefined) {
                        Pods.navigate('pods');
                        that.showPods();
                        return;
                    }
                    var _containerCollection = model.get('containers');
                    _.each(_containerCollection, function(i){
                            i.parentID = this.parentID;
                        }, {parentID: id, kubes: model.get('kubes')});
                    containerCollection = new Backbone.Collection(_containerCollection);

                    var masthead = new App.Views.Item.PageHeader({
                        model: new Backbone.Model({name: model.get('name')})
                    });

                    var infoPanel = new App.Views.Item.InfoPanel({
                        collection: containerCollection
                    });

                    that.listenTo(itemLayout, 'display:pod:stats', function(data){
                        var statCollection = new App.Data.StatsCollection(),
                            that = this;
                        statCollection.fetch({
                            data: {unit: data.get('id')},
                            reset: true,
                            success: function(){
                                itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                                    graphs: true,
                                    model: model
                                }));
                                itemLayout.info.show(new App.Views.Item.PodGraph({
                                    collection: statCollection
                                }));
                            },
                            error: function(){
                                console.log('failed to fetch graphs');
                            }
                        })
                    });

                    that.listenTo(itemLayout, 'display:pod:list', function(data){

                        itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                            graphs: false,
                            model: model
                        }));

                        itemLayout.info.show(new App.Views.Item.InfoPanel({
                            collection: containerCollection
                        }));
                    });

                    that.listenTo(itemLayout, 'show', function(){
                        itemLayout.masthead.show(masthead);
                        itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                            graphs: false,
                            model: model
                        }));
                        itemLayout.info.show(infoPanel);
                    });
                    App.contents.show(itemLayout);
                });
            },

            showPodContainer: function(id, name){
                var that = this;
                require(['pods_app/views/pod_create',
                         'pods_app/views/paginator',
                         'pods_app/views/loading'], function(){
                    var wizardLayout = new App.Views.NewItem.PodWizardLayout(),
                        parent_model = WorkFlow.getCollection().fullCollection.get(id),
                        model_data = _.find(parent_model.get('containers'),
                            function(i){return i.name === name}
                        );
                    if (!model_data.hasOwnProperty('kubes')) model_data['kubes'] = 1;
                    if (!model_data.hasOwnProperty('workingDir')) model_data['workingDir'] = undefined;
                    if (!model_data.hasOwnProperty('args')) model_data['args'] = [];
                    if (!model_data.hasOwnProperty('env')) model_data['env'] = [];
                    if (!model_data.hasOwnProperty('parentID')) model_data['parentID'] = id;

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardLogsSubView({
                            model: new App.Data.Image(model_data)
                        }));
                    });

                    that.listenTo(wizardLayout, 'step:portconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:volconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardVolumesSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardEnvSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:resconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardResSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:otherconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardOtherSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:statsconf', function(data){
                        var statCollection = new App.Data.StatsCollection();
                        statCollection.fetch({
                            data: {unit: data.get('parentID'), container: data.get('name')},
                            reset: true,
                            success: function(){
                                wizardLayout.steps.show(new App.Views.NewItem.WizardStatsSubView({
                                    containerModel: data,
                                    collection:statCollection
                                }));
                            },
                            error: function(){
                                console.log('failed to fetch graphs');
                            }
                        });
                    });
                    that.listenTo(wizardLayout, 'step:logsconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardLogsSubView({model: data}));
                    });
                    App.contents.show(wizardLayout);
                });
            },

            createPod: function(){
                "use strict";
                var that = this;
                require(['pods_app/utils',
                         'pods_app/views/pod_create',
                         'pods_app/views/paginator',
                         'pods_app/views/loading'], function(utils){
                    var model = new App.Data.Pod({name: "Unnamed-1", containers: [], volumes: []}),
                        registryURL = 'registry.hub.docker.com',
                        imageTempCollection = new App.Data.ImagePageableCollection(),
                        wizardLayout = new App.Views.NewItem.PodWizardLayout();
                    model.containerUrls = {};
                    model.origEnv = {};

                    var processRequest = function(data){
                        var hasPublic = function(containers){
                            for (var i in containers) {
                                for (var j in containers[i].ports) {
                                    if (containers[i].ports[j].hasOwnProperty('isPublic')
                                            && containers[i].ports[j].isPublic) {
                                        return true;
                                    }
                                }
                            }
                            return false;
                        };
                        var pdBackup = {};
                        var volumeNames = {};
                        if (data.has('persistentDrives')) { delete data.attributes.persistentDrives; }
                        _.each(data.get('containers'), function(c){
                            if (c.hasOwnProperty('persistentDrives')) { delete c.persistentDrives; }
                            _.each(c.volumeMounts, function(v){
                                volumeNames[v.name] = true;
                                if (v.isPersistent) {
                                    var entry = {name: v.name, persistentDisk: v.persistentDisk};
                                    var used = _.filter(data.attributes.persistentDrives,
                                        function(i){return i.pdName === v.persistentDisk.pdName});
                                    if (used.length) {
                                        used[0].used = true;
                                    }
                                    pdBackup[v.name] = _.clone(v.persistentDisk);
                                }
                                else {
                                    var entry = {name: v.name, localStorage: true};
                                }
                                delete v.isPersistent;
                                delete v.persistentDisk;
                                var filtered = _.filter(data.get('volumes'), function(vi){
                                    return vi.name === entry.name;
                                });
                                if (filtered.length === 0) {
                                    data.get('volumes').push(entry);
                                }
                            });
                        });

                        data.attributes.volumes = _.filter(data.attributes.volumes, function(v){
                            return _.has(volumeNames, v.name);
                        });

                        if (hasPublic(data.get('containers'))) {
                            data.attributes['set_public_ip'] = true;
                        }
                        else {
                            data.attributes['set_public_ip'] = false;
                        }

                        WorkFlow.getCollection().fullCollection.create(data.attributes, {
                            wait: true,
                            success: function(){
                                Pods.navigate('pods');
                                that.showPods();
                            },
                            error: function(model, response, options){
                                console.log('error applying data');
                                _.each(_.pairs(pdBackup), function(p){
                                    _.each(model.get('containers'), function(c){
                                        _.each(c['volumeMounts'], function(v){
                                            if (v.name === p[0]) {
                                                v.persistentDisk = _.clone(p[1]);
                                                v.isPersistent = true;
                                            }
                                        });
                                    });
                                });
                                var body = response.responseJSON ? JSON.stringify(response.responseJSON.data) : response.responseText;
                                $.notify(body, {
                                    autoHideDelay: 5000,
                                    globalPosition: 'bottom left',
                                    className: 'error'
                                });
                            }
                        });
                    };

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.header.show(new App.Views.NewItem.PodHeaderView({model: model}));
                        wizardLayout.steps.show(new App.Views.NewItem.GetImageView({collection: new App.Data.ImageCollection()}));
                    });
                    that.listenTo(wizardLayout, 'image:searchsubmit', function(query){
                        var imageCollection = new App.Data.ImageCollection();
                        imageTempCollection.fullCollection.reset();
                        imageTempCollection.getFirstPage({
                            wait: true,
                            data: {searchkey: query, url: registryURL},
                            success: function(collection, response, opts){
                                collection.each(function(m){imageCollection.add(m)});
                                wizardLayout.steps.show(new App.Views.NewItem.GetImageView({
                                    registryURL: registryURL,
                                    collection: imageCollection,
                                    query: query
                                }));
                            }
                        });
                    });
                    that.listenTo(wizardLayout, 'image:getnextpage', function(currentCollection, query){
                        imageTempCollection.getNextPage({
                            wait: true,
                            data: {searchkey: query, url: registryURL},
                            success: function(collection, response, opts){
                                collection.each(function(m){currentCollection.add(m)});
                                wizardLayout.steps.show(new App.Views.NewItem.GetImageView({
                                    registryURL: registryURL,
                                    collection: currentCollection,
                                    query: query
                                }));
                            }
                        });
                    });
                    that.listenTo(wizardLayout, 'step:getimage', function(){
                        wizardLayout.steps.show(new App.Views.NewItem.GetImageView({
                            collection: new App.Data.ImageCollection(imageTempCollection.fullCollection.models),
                            registryURL: registryURL
                        }));
                    });
                    that.listenTo(wizardLayout, 'clear:pager', function(){
                        wizardLayout.footer.empty();
                    });
                    that.listenTo(wizardLayout, 'step:portconf', function(data, imageName){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({model: data, imageName: imageName}));
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(data){
                        var containerModel = data.has('containers')
                                ? new App.Data.Image(_.last(model.get('containers')))
                                : data,
                            image = containerModel.get('image');
                        if (!(containerModel.get('image') in model.origEnv)) {
                            model.origEnv[image] = _.map(containerModel.attributes.env, _.clone);
                        }
                        if (!containerModel.hasOwnProperty('url')) {
                            containerModel.url = model.containerUrls[image];
                        }
                        containerModel.origEnv = _.map(model.origEnv[image], _.clone);
                        wizardLayout.steps.show(new App.Views.NewItem.WizardEnvSubView({
                            model: containerModel
                        }));
                    });
                    that.listenTo(wizardLayout, 'pod:save', function(data){
                        processRequest(data);
                    });
                    that.listenTo(wizardLayout, 'step:complete', function(containerModel){
                        if (containerModel.hasOwnProperty('persistentDrives')) {
                            model.persistentDrives = containerModel.persistentDrives;
                        }
                        model.containerUrls[containerModel.attributes.image] = containerModel.url;
                        if (containerModel.hasOwnProperty('origEnv')) {
                            model.origEnv[containerModel.get('image')] = containerModel.origEnv;
                        }
                        var container = _.find(model.get('containers'), function(c){
                            return c.name === containerModel.get('name');
                        });
                        if (container === undefined) {
                            container = {};
                            model.get('containers').push(container);
                        }
                        _.extendOwn(container, containerModel.attributes);
                        wizardLayout.steps.show(new App.Views.NewItem.WizardCompleteSubView({
                            model: model
                        }));
                    });
                    that.listenTo(wizardLayout, 'image:selected', function(image, url, imageName){
                        if (imageName !== undefined) {
                            var container = _.find(model.get('containers'), function(c){
                                return imageName === c.name
                            });
                            var containerModel = new App.Data.Image(container);
                            containerModel.url = url;
                            containerModel.persistentDrives = model.persistentDrives;
                            wizardLayout.steps.show(
                                new App.Views.NewItem.WizardPortsSubView({
                                    model: containerModel,
                                    containers: model.get('containers'),
                                    volumes: model.get('volumes')
                            }));
                        }
                        else {
                            var rqst = $.ajax({
                                type: 'POST',
                                url: '/api/images/new',
                                data: {image: image}
                            });
                            rqst.done(function(data){
                                var slash = image.indexOf('/'),
                                    name = (slash >= 0) ? image.substring(slash+1) : image;
                                if (data.hasOwnProperty('data')) { data = data['data']; }
                                name += _.map(_.range(10), function(i){return _.random(1, 10);}).join('');
                                var contents = {
                                    image: image, name: name, workingDir: null,
                                    ports: [], volumeMounts: [], env: [], args: [], kubes: 1,
                                    terminationMessagePath: null
                                };
                                model.fillContainer(contents, data);
                                var containerModel = new App.Data.Image(contents);
                                if (model.hasOwnProperty('persistentDrives')) {
                                    containerModel.persistentDrives = model.persistentDrives;
                                }
                                containerModel.url = url;
                                wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({
                                    model: containerModel,
                                    containers: model.get('containers'),
                                    volumes: model.get('volumes')
                                }));
                            });
                            wizardLayout.steps.show(new App.Views.Loading.LoadingView());
                        }
                    });
                    App.contents.show(wizardLayout);
                });
            }
        });

        WorkFlow.addInitializer(function(){
            var controller = new WorkFlow.Controller();
            new WorkFlow.Router({
                controller: controller
            });
            if (typeof(EventSource) === undefined) {
                console.log('ERROR: EventSource is not supported by browser');
            } else {
                var source = new EventSource("/api/stream");
                source.addEventListener('pull_pods_state', function () {
                    WorkFlow.getCollection().fetch();
                }, false);
                source.onerror = function () {
                    console.log("SSE Error");
                    // TODO Setup here timer to reconnect, maybe via location.reload
                };
            }
        });

    });

    Pods.on('pods:list', function(){
        var controller = new Pods.WorkFlow.Controller();
        Pods.navigate('pods');
        controller.showPods();
    });

    return Pods.WorkFlow.Controller;
});
