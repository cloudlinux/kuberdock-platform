define(['pods_app/app', 'pods_app/utils', 'pods_app/models/pods'], function(Pods, Utils){
    Pods.module("WorkFlow", function(WorkFlow, App, Backbone, Marionette, $, _){
        WorkFlow.getCollection = function(){
            if (!WorkFlow.hasOwnProperty('PodCollection')) {
                WorkFlow.PodCollection = new App.Data.PodCollection(podCollectionData);
            }
            return WorkFlow.PodCollection;
        }

        WorkFlow.commandPod = function(cmd, pod){
            Utils.preloader.show();
            pod = WorkFlow.getCollection().fullCollection.get(pod);
            if (/^container_/.test(cmd)) {
                console.error('Container stop/start/delete not implemented yet.');
                return;
            }
            return pod.command(cmd, {
                wait: true,
                error: function(model, xhr){ Utils.notifyWindow(xhr); },
                complete: function(){
                    Utils.preloader.hide();
                    WorkFlow.getCollection().trigger('pods:collection:fetched');
                },
            });
        };

        WorkFlow.updateContainer = function(containerModel){
            var performUpdate = function () {
                Utils.preloader.show();
                return containerModel.update().always(Utils.preloader.hide)
                    .fail(function(xhr){ Utils.notifyWindow(xhr); });
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
            return containerModel.checkForUpdate().always(Utils.preloader.hide)
                .fail(function(xhr){ Utils.notifyWindow(xhr); })
                .done(function(rs){
                    if (!rs.data)
                        Utils.notifyWindow('No updates found', 'success');
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

                    var masthead = new App.Views.Item.PageHeader({
                        model: new Backbone.Model({name: model.get('name')})
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
                                    collection: model.get('containers'),
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
                            data: {unit: data.id},
                            reset: true,
                            success: function(){
                                itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                                    graphs: true,
                                    model: model
                                }));
                                itemLayout.info.show(new App.Views.Item.PodGraph({
                                    model: model,
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
                            collection: model.get('containers')
                        }));
                    });

                    that.listenTo(itemLayout, 'show', function(){
                        itemLayout.masthead.show(masthead);
                        itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                            graphs: false,
                            model: model
                        }));
                        itemLayout.info.show(new App.Views.Item.InfoPanel({
                            collection: model.get('containers'),
                        }));
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
                        model = parent_model.get('containers').get(name);

                    var show = function(View){
                        return wizardLayout.steps.show(new View({model: model}));
                    };

                    that.listenTo(wizardLayout, 'show',
                        _.partial(show, App.Views.NewItem.WizardLogsSubView));

                    that.listenTo(wizardLayout, 'step:portconf',
                        _.partial(show, App.Views.NewItem.WizardPortsSubView));
                    that.listenTo(wizardLayout, 'step:volconf',
                        _.partial(show, App.Views.NewItem.WizardVolumesSubView));
                    that.listenTo(wizardLayout, 'step:envconf',
                        _.partial(show, App.Views.NewItem.WizardEnvSubView));
                    that.listenTo(wizardLayout, 'step:resconf',
                        _.partial(show, App.Views.NewItem.WizardResSubView));
                    that.listenTo(wizardLayout, 'step:otherconf',
                        _.partial(show, App.Views.NewItem.WizardOtherSubView));
                    that.listenTo(wizardLayout, 'step:statsconf', function(){
                        var statCollection = new App.Data.StatsCollection();
                        statCollection.fetch({
                            data: {unit: parent_model.id, container: model.id},
                            reset: true,
                            success: function(){
                                wizardLayout.steps.show(new App.Views.NewItem.WizardStatsSubView({
                                    model: model,
                                    collection:statCollection
                                }));
                            },
                            error: function(){
                                console.log('failed to fetch graphs');
                            }
                        });
                    });
                    that.listenTo(wizardLayout, 'step:logsconf',
                        _.partial(show, App.Views.NewItem.WizardLogsSubView));
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
                        podModels = WorkFlow.getCollection().fullCollection.models,
                        imageView,
                        podName;
                        if (podModels.length === 0) {
                            podName = 'Unnamed-1';
                        } else {
                            podName = 'Unnamed-' + (_.max(podModels.map(function(m){
                                var match = /^Unnamed-(\d+)$/.exec(m.attributes.name);
                                return match !== null ? +match[1] : 0;
                            }))+1);
                        }
                    var model = new App.Data.Pod({ name: podName });
                    model.detached = true;
                    model.lastEditedContainer = {id: null, isNew: true};
                    that.listenTo(model, 'remove:containers', function(container){
                        model.deleteVolumes(_.pluck(container.get('volumeMounts'), 'name'));
                    });

                    var newImageView = function(options){
                        imageView = new App.Views.NewItem.GetImageView(
                            _.extend({pod:model, registryURL: registryURL}, options)
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
                                    collection: imageCollection,
                                    query: query
                                });
                                if (collection.length == 0) {
                                    utils.notifyWindow('We couldn\'t find any results for this search');
                                }
                            },
                            error: processCollectionLoadError,
                        });
                    });
                    that.listenTo(wizardLayout, 'image:getnextpage', function(currentCollection, query){
                        var that = this,
                            windowTopPosition = window.pageYOffset;
                        imageTempCollection.getNextPage({
                            wait: true,
                            data: {searchkey: query, url: registryURL},
                            success: function(collection, response, opts){
                                collection.each(function(m){currentCollection.add(m)});
                                newImageView({
                                    collection: currentCollection,
                                    query: query
                                });
                                $('html, body').scrollTop(windowTopPosition);
                                if (collection.length == 0) $('#load-control').hide();
                            },
                            error: processCollectionLoadError
                        });
                    });
                    that.listenTo(wizardLayout, 'step:getimage', function(){
                        newImageView({
                            collection: new App.Data.ImageCollection(imageTempCollection.fullCollection.models),
                        });
                    });
                    that.listenTo(wizardLayout, 'clear:pager', function(){
                        wizardLayout.footer.empty();
                    });
                    that.listenTo(wizardLayout, 'step:portconf', function(){
                        var container = model.lastEditedContainer.id;
                        wizardLayout.steps.show(
                            new App.Views.NewItem.WizardPortsSubView({
                                model: model.get('containers').get(container),
                            })
                        );
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(){
                        var container = model.lastEditedContainer.id,
                            containerModel = model.get('containers').get(container),
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
                        // if (window.hasOwnProperty('replicas')) {
                        //     console.warn('Taking number of replicas from global var');
                        //     data.attributes.replicas = window.replicas;
                        // }

                        utils.preloader.show();
                        WorkFlow.getCollection().fullCollection.create(data, {
                            wait: true,
                            success: function(model){
                                model.detached = false;
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
                    that.listenTo(wizardLayout, 'step:complete', function(){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardCompleteSubView({
                            model: model
                        }));
                    });
                    that.listenTo(wizardLayout, 'image:selected', function(image, auth){
                        utils.preloader.show();
                        $.ajax({
                            type: 'POST',
                            contentType: 'application/json; charset=utf-8',
                            url: '/api/images/new',
                            data: JSON.stringify({image: image, auth: auth})
                        }).always(utils.preloader.hide).fail(function(data){
                            utils.notifyWindow(data);
                        }).done(function(data){
                            var newContainer = App.Data.Container.fromImage(data.data);
                            model.get('containers').remove(model.lastEditedContainer.id);
                            model.get('containers').add(newContainer);
                            model.lastEditedContainer.id = newContainer.id;
                            wizardLayout.trigger('step:portconf');
                        });
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
