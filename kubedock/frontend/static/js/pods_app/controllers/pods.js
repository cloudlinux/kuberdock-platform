define(['pods_app/app', 'pods_app/utils', 'pods_app/models/pods'], function(Pods, Utils){
    Pods.module("WorkFlow", function(WorkFlow, App, Backbone, Marionette, $, _){
        WorkFlow.getCollection = function(){
            if (!WorkFlow.hasOwnProperty('PodCollection')) {
                WorkFlow.PodCollection = new App.Data.PodCollection(podCollectionData);
            }
            return WorkFlow.PodCollection;
        }

        WorkFlow.commandPod = function(cmd, podID, containerName){
            Utils.preloader.show();
            var model = WorkFlow.getCollection().fullCollection.get(podID);

            if (/^container_/.test(cmd)) {
                console.error('Container stop/start/delete not implemented yet.');
                return;
            }
            return $.ajax({
                url: '/api/podapi/' + podID,
                data: {command: cmd},
                type: 'PUT',
                complete: function(){ Utils.preloader.hide(); },
                error: function(xhr){ Utils.notifyWindow(xhr); },
            });
        };

        WorkFlow.updateContainer = function(containerModel){
            var performUpdate = function () {
                Utils.preloader.show();
                return $.ajax({
                    url: '/api/podapi/' + containerModel.get('parentID') +
                         '/' + containerModel.get('containerID') + '/update',
                    type: 'POST',
                    complete: function(){ Utils.preloader.hide(); },
                    error: function(xhr){ Utils.notifyWindow(xhr); },
                    success: function(){ containerModel.updateIsAvailable = undefined; },
                });
            };

            Utils.modalDialog({
                title: 'Update container',
                body: "During update whole pod will be restarted. Continue?",
                small: true,
                show: true,
                footer: {buttonOk: performUpdate, buttonCancel: true}
            });
        };

        WorkFlow.checkContainerForUpdate = function(containerModel){
            Utils.preloader.show();
            return $.ajax({
                url: '/api/podapi/' + containerModel.get('parentID') +
                     '/' + containerModel.get('containerID') + '/update',
                type: 'GET',
                complete: function(){ Utils.preloader.hide(); },
                error: function(xhr){ Utils.notifyWindow(xhr); },
                success: function(rs){
                    if (!rs.data)
                        Utils.notifyWindow('No updates found', 'success');
                    containerModel.updateIsAvailable = rs.data;
                },
            });
        };

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
                        model = WorkFlow.getCollection().fullCollection.get(id),
                        graphsOn = false;

                    if (model === undefined) {
                        Pods.navigate('pods');
                        that.showPods();
                        return;
                    }

                    var containerCollection = new Backbone.Collection(
                        _.each(model.get('containers'), function(i){
                            i.parentID = this.parentID;
                        }, {parentID: id}));

                    var masthead = new App.Views.Item.PageHeader({
                        model: new Backbone.Model({name: model.get('name')})
                    });

                    var infoPanel = new App.Views.Item.InfoPanel({
                        collection: containerCollection
                    });

                    that.listenTo(WorkFlow.getCollection(), 'pods:collection:fetched', function(){
                        try {
                            var model = WorkFlow.getCollection().fullCollection.get(id);
                            if (typeof itemLayout.controls === 'undefined' || typeof model === 'undefined') {
                                return;
                            }
                            itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                                graphs: graphsOn,
                                model: model,
                            }));
                            if (!graphsOn) {
                                itemLayout.info.show(new App.Views.Item.InfoPanel({
                                    collection: new Backbone.Collection(
                                        _.each(model.get('containers'), function(i){
                                            i.parentID = this.parentID;
                                        }, {parentID: id}))
                                }));
                            }
                        } catch(e) {
                            console.log(e)
                        }
                    });

                    that.listenTo(itemLayout, 'display:pod:stats', function(data){
                        var statCollection = new App.Data.StatsCollection(),
                            that = this;
                        graphsOn = true;
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
                        graphsOn = false;
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
                        parent_model = WorkFlow.getCollection().fullCollection.get(id);

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardLogsSubView({
                            model: parent_model.getContainer(name)
                        }));
                    });

                    that.listenTo(wizardLayout, 'step:portconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({
                            model: data,
                            volumes: parent_model.get('volumes')
                        }));
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
                                    model: data,
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
                    var registryURL = 'registry.hub.docker.com',
                        imageTempCollection = new App.Data.ImagePageableCollection(),
                        wizardLayout = new App.Views.NewItem.PodWizardLayout(),
                        imageView,
                        podName = 'Unnamed-' + (Math.max.apply(null, WorkFlow.getCollection().fullCollection.models.map(function(m){
                            var match = /^Unnamed\-(\d+)$/.exec(m.attributes.name);
                               return match !== null ? +match[1] : 0;
                        }))+1);
                    var model = new App.Data.Pod({ name: podName, containers: [], volumes: [] });
                    var newImageView = function(options){
                        imageView = new App.Views.NewItem.GetImageView(
                            options
                        );
                        wizardLayout.steps.show(imageView);
                    };
                    var processCollectionLoadError = function(collection, response){
                        utils.notifyWindow(response);
                        imageView.removeLoader();
                    };

                    model.origEnv = {};

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.header.show(new App.Views.NewItem.PodHeaderView({model: model}));
                        newImageView({
                            collection: new App.Data.ImageCollection()
                        });
                    });
                    that.listenTo(wizardLayout, 'image:searchsubmit', function(query){
                        var imageCollection = new App.Data.ImageCollection();
                        imageTempCollection.fullCollection.reset();
                        imageTempCollection.getFirstPage({
                            wait: true,
                            data: {searchkey: query, url: registryURL},
                            success: function(collection, response, opts){
                                collection.each(function(m){imageCollection.add(m)});
                                newImageView({
                                    registryURL: registryURL,
                                    collection: imageCollection,
                                    query: query
                                });
                            },
                            error: processCollectionLoadError,
                        });
                    });
                    that.listenTo(wizardLayout, 'image:getnextpage', function(currentCollection, query){
                        imageTempCollection.getNextPage({
                            wait: true,
                            data: {searchkey: query, url: registryURL},
                            success: function(collection, response, opts){
                                collection.each(function(m){currentCollection.add(m)});
                                newImageView({
                                    registryURL: registryURL,
                                    collection: currentCollection,
                                    query: query
                                });
                            },
                            error: processCollectionLoadError
                        });
                    });
                    that.listenTo(wizardLayout, 'step:getimage', function(){
                        newImageView({
                            collection: new App.Data.ImageCollection(imageTempCollection.fullCollection.models),
                            registryURL: registryURL
                        });
                    });
                    that.listenTo(wizardLayout, 'clear:pager', function(){
                        wizardLayout.footer.empty();
                    });
                    that.listenTo(wizardLayout, 'step:portconf', function(data){
                        var containerModel = data.has('containers')
                                ? new App.Data.Image(_.last(model.get('containers')))
                                : data;
                        containerModel.persistentDrives = model.persistentDrives;
                        wizardLayout.steps.show(
                            new App.Views.NewItem.WizardPortsSubView({
                                model: containerModel,
                                containers: model.get('containers'),
                                volumes: model.get('volumes')
                            }));
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(data){
                        var containerModel = data.has('containers')
                                ? new App.Data.Image(_.last(model.get('containers')))
                                : data,
                            image = containerModel.get('image');
                        if (!(containerModel.get('image') in model.origEnv)) {
                            model.origEnv[image] = _.map(containerModel.attributes.env, _.clone);
                        }
                        containerModel.origEnv = _.map(model.origEnv[image], _.clone);
                        wizardLayout.steps.show(new App.Views.NewItem.WizardEnvSubView({
                            model: containerModel
                        }));
                    });
                    that.listenTo(wizardLayout, 'pod:save', function(data){
                        data.attributes['set_public_ip'] = _.any(
                            _.flatten(_.pluck(data.get('containers'), 'ports')),
                            function(p){return p['isPublic']});
                        // if (window.hasOwnProperty('replicas')) {
                        //     console.warn('Taking number of replicas from global var');
                        //     data.attributes.replicas = window.replicas;
                        // }

                        utils.preloader.show();
                        WorkFlow.getCollection().fullCollection.create(data.attributes, {
                            wait: true,
                            success: function(){
                                utils.preloader.hide();
                                Pods.navigate('pods');
                                that.showPods();
                            },
                            error: function(model, response, options){
                                console.log('could not save data');
                                var body = response.responseJSON
                                    ? JSON.stringify(response.responseJSON.data)
                                    : response.responseText;
                                utils.preloader.hide();
                                utils.notifyWindow(body);
                            }
                        });
                    });
                    that.listenTo(wizardLayout, 'step:complete', function(containerModel){
                        if (containerModel.hasOwnProperty('persistentDrives')) {
                            model.persistentDrives = containerModel.persistentDrives;
                        }
                        if (containerModel.hasOwnProperty('origEnv')) {
                            model.origEnv[containerModel.get('image')] = containerModel.origEnv;
                        }
                        model.last_edited_container = containerModel.get('name');
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
                    that.listenTo(wizardLayout, 'image:selected', function(image, containerName, auth){
                        if (containerName !== undefined) {
                            var container = _.find(model.get('containers'), function(c){
                                return containerName === c.name;
                            });
                            var containerModel = new App.Data.Image(container);
                            containerModel.persistentDrives = model.persistentDrives;
                            wizardLayout.steps.show(
                                new App.Views.NewItem.WizardPortsSubView({
                                    model: containerModel,
                                    containers: model.get('containers'),
                                    volumes: model.get('volumes')
                            }));
                        }
                        else {
                            utils.preloader.show();
                            var rqst = $.ajax({
                                type: 'POST',
                                dataType: 'json',
                                contentType: 'application/json; charset=utf-8',
                                url: '/api/images/new',
                                data: JSON.stringify({image: image, auth: auth})
                            });
                            rqst.error(function(data){
                                utils.preloader.hide();
                                utils.notifyWindow(data);
                            });
                            rqst.success(function(data){
                                utils.preloader.hide();
                                var name = image.replace(/[^a-z0-9]+/gi, '-');
                                name += _.random(Math.pow(36, 8)).toString(36);
                                if (data.hasOwnProperty('data')) { data = data['data']; }
                                var contents = {
                                    image: image, name: name, workingDir: null,
                                    ports: [], volumeMounts: [], env: [], args: [], kubes: 1,
                                    terminationMessagePath: null, sourceUrl: null
                                };
                                model.fillContainer(contents, data);
                                var containerModel = new App.Data.Image(contents);
                                if (model.hasOwnProperty('persistentDrives')) {
                                    containerModel.persistentDrives = model.persistentDrives;
                                }
                                wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({
                                    model: containerModel,
                                    containers: model.get('containers'),
                                    volumes: model.get('volumes')
                                }));
                            });
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

            function eventHandler(){
                var source = new EventSource("/api/stream");

                if (typeof(EventSource) === undefined) {
                    console.log('ERROR: EventSource is not supported by browser');
                } else {
                    source.addEventListener('pull_pods_state', function(){
                        WorkFlow.getCollection().fetch({
                            success: function(collection, response, opts){
                                collection.trigger('pods:collection:fetched');
                            }
                        });
                    },false);
                    source.onerror = function () {
                        console.info('SSE Error');
                        source.close();
                        setTimeout(eventHandler, 5 * 1000)
                    };
                }
            }
            eventHandler();
        });
    });

    Pods.on('pods:list', function(){
        var controller = new Pods.WorkFlow.Controller();
        Pods.navigate('pods');
        controller.showPods();
    });

    return Pods.WorkFlow.Controller;
});
