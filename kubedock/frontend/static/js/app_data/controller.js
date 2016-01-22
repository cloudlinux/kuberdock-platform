define(['app_data/app', 'app_data/utils', 'app_data/model'], function(App, utils, Model){
    //"use strict";

    var controller = Marionette.Object.extend({

        showPods: function(){
            var that = this;
            require(['app_data/pods/views/pods_list',
                     'app_data/pods/views/breadcrumbs',
                     'app_data/paginator/views',
                     'app_data/menu/views'], function(Views, Misc, Pager, Menu){
                var listLayout = new Views.PodListLayout(),
                    breadcrumbsData = {breadcrumbs: [{name: 'Pods'}],
                                       buttonID: 'add_pod',
                                       buttonLink: '/#newpod',
                                       buttonTitle: 'Add new container'},
                    breadcrumbsModel = new Backbone.Model(breadcrumbsData),
                    breadcrumbs = new Misc.Breadcrumbs({model: breadcrumbsModel}),
                    navbar = new Menu.NavList({collection: App.menuCollection});

                that.listenTo(listLayout, 'show', function(){
                    App.getPodCollection().done(function(collection){
                        listLayout.nav.show(navbar);
                        listLayout.header.show(breadcrumbs);
                        var view = new Views.PodCollection({collection: collection});
                        listLayout.list.show(view);
                        listLayout.pager.show(new Pager.PaginatorView({view: view}));
                    });
                });

                that.listenTo(listLayout, 'clear:pager', function(){
                    listLayout.pager.empty();
                });

                that.listenTo(listLayout, 'collection:filter', function(data){
                    App.getPodCollection().done(function(collection){
                        if (data.length > 2) {
                            collection = new Model.PodCollection(
                                collection.searchIn(data));
                        }
                        var view = new Views.PodCollection({collection: collection});
                        listLayout.list.show(view);
                        listLayout.pager.show(new Pager.PaginatorView({view: view}));
                    });
                });

                App.contents.show(listLayout);
            });
        },

        showPodItem: function(id){
            var that = this;
            require(['app_data/pods/views/pod_item',
                     'app_data/paginator/views',
                     'app_data/menu/views'], function(Views, Pager, Menu){
                App.getPodCollection().done(function(podCollection){
                    var itemLayout = new Views.PodItemLayout(),
                        model = podCollection.fullCollection.get(id),
                        graphsOn = false;

                    if (model === undefined) {
                        App.navigate('pods');
                        that.showPods();
                        return;
                    }

                    that.listenTo(model, 'remove destroy', function(){
                        App.navigate('pods', {trigger: true});
                    });

                    var navbar = new Menu.NavList({
                        collection: App.menuCollection
                    });

                    var masthead = new Views.PageHeader({
                        model: new Backbone.Model({name: model.get('name')})
                    });

                    that.listenTo(itemLayout, 'display:pod:stats', function(data){
                        var statCollection = new Model.StatsCollection(),
                            that = this;
                        graphsOn = true;
                        statCollection.fetch({
                            data: {unit: data.id},
                            reset: true,
                            success: function(){
                                itemLayout.controls.show(new Views.ControlsPanel({
                                    graphs: true,
                                    model: model
                                }));
                                itemLayout.info.show(new Views.PodGraph({
                                    model: model,
                                    collection: statCollection
                                }));
                            },
                            error: function(collection, response){
                                utils.notifyWindow(response);
                            },
                        });
                    });

                    that.listenTo(itemLayout, 'display:pod:list', function(data){
                        graphsOn = false;
                        itemLayout.controls.show(new Views.ControlsPanel({
                            graphs: false,
                            model: model
                        }));
                        itemLayout.info.show(new Views.InfoPanel({
                            collection: model.get('containers')
                        }));
                    });

                    that.listenTo(itemLayout, 'show', function(){
                        itemLayout.nav.show(navbar);
                        itemLayout.masthead.show(masthead);
                        itemLayout.controls.show(new Views.ControlsPanel({
                            graphs: false,
                            model: model
                        }));
                        itemLayout.info.show(new Views.InfoPanel({
                            collection: model.get('containers'),
                        }));
                    });
                    App.contents.show(itemLayout);
                });
            });
        },

        showPodContainer: function(id, name){
            var that = this;
            require(['app_data/pods/views/pod_create',
                     'app_data/paginator/views',
                     'app_data/pods/views/loading',
                     'app_data/menu/views'], function(Views, Pager, Loading, Menu){
                App.getPodCollection().done(function(podCollection){
                    var wizardLayout = new Views.PodWizardLayout(),
                        pod = podCollection.fullCollection.get(id),
                        model = pod.get('containers').get(name),
                        navbar = new Menu.NavList({ collection: App.menuCollection });

                    var show = function(View){
                        return wizardLayout.steps.show(new View({model: model}));
                    };

                    that.listenTo(pod, 'remove destroy', function(){
                        App.navigate('pods', {trigger: true});
                    });

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.nav.show(navbar);
                        wizardLayout.steps.show(new Views.WizardLogsSubView({model: model}));
                    });

                    that.listenTo(wizardLayout, 'step:portconf',
                        _.partial(show, Views.WizardPortsSubView));
                    that.listenTo(wizardLayout, 'step:volconf',
                        _.partial(show, Views.WizardVolumesSubView));
                    that.listenTo(wizardLayout, 'step:envconf',
                        _.partial(show, Views.WizardEnvSubView));
                    that.listenTo(wizardLayout, 'step:resconf',
                        _.partial(show, Views.WizardResSubView));
                    that.listenTo(wizardLayout, 'step:otherconf',
                        _.partial(show, Views.WizardOtherSubView));
                    that.listenTo(wizardLayout, 'step:statsconf', function(){
                        var statCollection = new Model.StatsCollection();
                        statCollection.fetch({
                            data: {unit: pod.id, container: model.id},
                            reset: true,
                            success: function(){
                                wizardLayout.steps.show(new Views.WizardStatsSubView({
                                    model: model,
                                    collection:statCollection
                                }));
                            },
                            error: function(collection, response){
                                utils.notifyWindow(response);
                            },
                        });
                    });
                    that.listenTo(wizardLayout, 'step:logsconf',
                        _.partial(show, Views.WizardLogsSubView));
                    App.contents.show(wizardLayout);
                });
            });
        },

        createPod: function(){
            "use strict";
            var that = this;
            require(['app_data/utils',
                     'app_data/pods/views/pod_create',
                     'app_data/paginator/views',
                     'app_data/pods/views/loading',
                     'app_data/menu/views'], function(utils, Views, Pager, Loading, Menu){
                App.getPodCollection().done(function(podCollection){
                    var registryURL = 'registry.hub.docker.com',
                        imageTempCollection = new Model.ImagePageableCollection(),
                        wizardLayout = new Views.PodWizardLayout(),
                        podModels = podCollection.fullCollection.models,
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
                    var model = new Model.Pod({ name: podName });
                    model.detached = true;
                    model.lastEditedContainer = {id: null, isNew: true};
                    that.listenTo(model, 'remove:containers', function(container){
                        model.deleteVolumes(_.pluck(container.get('volumeMounts'), 'name'));
                    });
                    var newImageView = function(options){
                        imageView = new Views.GetImageView(
                            _.extend({pod:model, registryURL: registryURL}, options)
                        );
                        wizardLayout.steps.show(imageView);
                    };

                    var navbar = new Menu.NavList({
                        collection: App.menuCollection
                    });

                    var processCollectionLoadError = function(collection, response){
                        utils.notifyWindow(response);
                        imageView.removeLoader();
                    };

                    model.origEnv = {};

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.nav.show(navbar);
                        wizardLayout.header.show(new Views.PodHeaderView({model: model}));
                        newImageView({
                            collection: new Model.ImageCollection()
                        });
                    });
                    that.listenTo(wizardLayout, 'image:searchsubmit', function(query){
                        var imageCollection = new Model.ImageCollection();
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
                            collection: new Model.ImageCollection(imageTempCollection.fullCollection.models)
                        });
                    });
                    that.listenTo(wizardLayout, 'clear:pager', function(){
                        wizardLayout.footer.empty();
                    });
                    that.listenTo(wizardLayout, 'step:portconf', function(){
                        var container = model.lastEditedContainer.id;
                        wizardLayout.steps.show(
                            new Views.WizardPortsSubView({
                                model: model.get('containers').get(container),
                            })
                        );
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(data){
                        var container = model.lastEditedContainer.id,
                            containerModel = model.get('containers').get(container),
                            image = containerModel.get('image');
                        if (!(containerModel.get('image') in model.origEnv)) {
                            model.origEnv[image] = _.map(containerModel.attributes.env, _.clone);
                        }
                        containerModel.origEnv = _.map(model.origEnv[image], _.clone);
                        wizardLayout.steps.show(new Views.WizardEnvSubView({
                            model: containerModel
                        }));
                    });
                    that.listenTo(wizardLayout, 'pod:save', function(data){
                        if (model.get('kube_type') == Model.KubeType.noAvailableKubeTypes.id){
                            Model.KubeType.noAvailableKubeTypes.notify();
                            return;
                        }
                        utils.preloader.show();
                        podCollection.fullCollection.create(data, {
                            wait: true,
                            complete: utils.preloader.hide,
                            success: function(model){
                                model.detached = false;
                                App.navigate('pods');
                                that.showPods();
                            },
                            error: function(model, response){
                                utils.notifyWindow(response);
                            },
                        });
                    });
                    that.listenTo(wizardLayout, 'step:complete', function(){
                        if (model.get('kube_type') == Model.KubeType.noAvailableKubeTypes.id)
                            Model.KubeType.noAvailableKubeTypes.notify();
                        wizardLayout.steps.show(new Views.WizardCompleteSubView({
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
                        }).always(
                            utils.preloader.hide
                        ).fail(
                            utils.notifyWindow
                        ).done(function(data){
                            var newContainer = Model.Container.fromImage(data.data);
                            model.get('containers').remove(model.lastEditedContainer.id);
                            model.get('containers').add(newContainer);
                            model.lastEditedContainer.id = newContainer.id;
                            wizardLayout.trigger('step:portconf');
                        });
                    });
                    App.contents.show(wizardLayout);
                });
            });
        },

        showNodes: function(){
            var that = this;
            require(['app_data/nodes/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.NodesLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});

                that.listenTo(layoutView, 'show', function(){
                    App.getNodeCollection().done(function(nodeCollection){
                        layoutView.nav.show(navbar);
                        var nodeCollectionView = new Views.NodesListView({
                            collection: nodeCollection
                        });
                        layoutView.main.show(nodeCollectionView);
                        layoutView.pager.show(
                            new Views.PaginatorView({
                                view: nodeCollectionView
                            })
                        );
                    });
                });
                that.listenTo(layoutView, 'collection:name:filter', function(value){
                    App.getNodeCollection().done(function(nodeCollection){
                        filteredCollection = new Model.NodeCollection(
                            nodeCollection.fullCollection.filter(function(model){
                                return model.get('hostname').indexOf(value) !== -1;
                            })
                        );
                        var nodeCollectionView = new Views.NodesListView({
                            collection: filteredCollection,
                            searchString: value
                        });
                        layoutView.main.show(nodeCollectionView);
                        layoutView.pager.show(
                            new Views.PaginatorView({
                                view: nodeCollectionView
                            })
                        );
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showAddNode: function(){
            var that = this;
            require(['app_data/nodes/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.NodeAddWizardLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.nodeAddStep.show(new Views.NodeAddStep({
                        model: new Backbone.Model({isFinished: false})
                    }));
                });
                App.contents.show(layoutView);
            });
        },

        showDetailedNode: function(nodeId, tab){
            var that = this;
            require(['app_data/nodes/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.NodeDetailedLayout({nodeId: nodeId, tab: tab}),
                    navbar = new Menu.NavList({collection: App.menuCollection});

                that.listenTo(layoutView, 'show', function(){
                    App.getNodeCollection().done(function(nodeCollection){

                        var node = nodeCollection.get(nodeId);
                            //breadcrumbsModel = new Backbone.Model({hostname: node.get('hostname')});
                            //sidebarModel = new Backbone.Model({tab: tab, });

                        that.listenTo(node, 'remove destroy', function(){
                            App.navigate('nodes', {trigger: true});
                        });

                        layoutView.nav.show(navbar);
                        //layoutView.breadcrumbs.show(new Views.Breadcrumbs({model: breadcrumbsModel}));

                        switch (tab) {

                            case 'general': {
                                //layoutView.sidebar.show(new Views.SideBar({model: sidebarModel, nodeId: nodeId}));
                                layoutView.tabContent.show(new Views.NodeGeneralTabView({ model: node }));
                            } break;

                            case 'stats': {
                                layoutView.tabContent.show(new Views.NodeStatsTabView({ model: node }));
                            } break;

                            case 'logs': {
                                //layoutView.sidebar.show(new Views.SideBar({model: sidebarModel, nodeId: nodeId}));
                                layoutView.tabContent.show(new Views.NodeLogsTabView({ model: node }));
                            } break;

                            case 'monitoring': {
                                var hostname = node.get('hostname'),
                                    graphCollection = new Model.NodeStatsCollection();
                                graphCollection.fetch({
                                    wait: true,
                                    data: {node: hostname},
                                    success: function(){
                                        var view = new Views.NodeMonitoringTabView({
                                            collection: graphCollection,
                                            model: node,
                                        });
                                        //layoutView.sidebar.show(new Views.SideBar({model: sidebarModel, nodeId: nodeId}));
                                        layoutView.tabContent.show(view);
                                    },
                                    error: function(collection, response){
                                        utils.notifyWindow(response);
                                    }
                                });
                            } break;

                            case 'timelines': {
                                layoutView.tabContent.show(new Views.NodeTimelinesTabView({ model: node }));
                            } break;

                            case 'configuration': {
                                layoutView.tabContent.show(new Views.NodeConfigurationTabView({ model: node }));
                            } break;

                            default: {
                                //layoutView.sidebar.show(new Views.SideBar({model: sidebarModel, nodeId: nodeId}));
                                layoutView.tabContent.show(new Views.NodeGeneralTabView({ model: node }));
                            } break;

                        } // switch
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showOnlineUsers: function(){
            var layout_view = new App.Views.UsersLayout(),
                online_users_list_view = new App.Views.OnlineUsersListView({
                    collection: App.Data.onlineUsers
                }),
                user_list_pager = new App.Views.PaginatorView({
                    view: online_users_list_view
                });

            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(online_users_list_view);
                layout_view.pager.show(user_list_pager);
            });
            App.contents.show(layout_view);
        },

        showUserActivity: function(user_id){
            var that = this,
                layout_view = new App.Views.UsersLayout();

            $.ajax({
                'url': '/api/users/a/' + user_id,
                success: function(rs){
                    UsersApp.Data.activities = new UsersApp.Data.ActivitiesCollection(rs.data);
                    var activities_view = new App.Views.UsersActivityView({
                            collection: UsersApp.Data.activities
                        }),
                        activities_list_pager = new App.Views.PaginatorView({
                            view: activities_view
                        });

                    that.listenTo(layout_view, 'show', function(){
                        layout_view.main.show(activities_view);
                        layout_view.pager.show(activities_list_pager);
                    });
                    App.contents.show(layout_view);
                },
            });
        },

        showUsers: function(){
            var that = this;
            require(['app_data/users/views',
                     'app_data/paginator/views',
                     'app_data/menu/views',
            ], function(Views, Pager, Menu){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    App.getUserCollection().done(function(userCollection){
                        var userCollectionView = new Views.UsersListView({ collection: userCollection });
                        layoutView.main.show(userCollectionView);
                        layoutView.pager.show(new Pager.PaginatorView({ view: userCollectionView }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showAllUsersActivity: function(){
            var that = this;
            require(['app_data/users/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.main.show(new Views.AllUsersActivitiesView());
                });
                App.contents.show(layoutView);
            });
        },

        showCreateUser: function(){
            var that = this;
            require(['app_data/users/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    $.when(App.getRoles(), App.getPackages(), App.getTimezones()).done(function(roles, packages, timezones){
                        layoutView.main.show(new Views.UserCreateView({ roles: roles, packages: packages, timezones: timezones }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showEditUser: function(userId){
            var that = this;
            require(['app_data/users/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    $.when(App.getUserCollection(), App.getKubeTypes(),
                           App.getRoles(), App.getPackages(), App.getTimezones()).done(function(userCollection, kubeTypes, roles, packages, timezones){
                        var model = userCollection.fullCollection.get(Number(userId)),
                            view = new Views.UsersEditView({ model: model, kubeTypes: kubeTypes,
                                                           roles: roles, packages: packages, timezones: timezones});
                        layoutView.main.show(view);
                        $('#pager').hide();
                        $('#user-header h2').text('Edit');
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showProfileUser: function(userId){
            var that = this;
            require(['app_data/users/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    $.when(App.getUserCollection(), App.getKubeTypes()).done(function(userCollection, kubeTypes){
                        var userModel = userCollection.fullCollection.get(Number(userId)),
                            userProfileView = new Views.UserProfileView({ model: userModel, kubeTypes: kubeTypes });
                        layoutView.main.show(userProfileView);
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showProfileUserLogHistory: function(userId){
            var that = this;
            require(['app_data/users/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    App.getUserCollection().done(function(userCollection){
                        var model = userCollection.fullCollection.get(Number(userId)),
                            view = new Views.UserProfileViewLogHistory({ model: model });
                        layoutView.main.show(view);
                    });
                });
                App.contents.show(layoutView);
            });
        },

        listPredefinedApps: function(){
            var that = this;
            require(['app_data/papps/views',
                     'app_data/paginator/views',
                     'app_data/menu/views',
            ], function(Views, Pager, Menu){
                var appCollection = new Model.AppCollection(),
                    mainLayout = new Views.MainLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    breadcrumbsData = {buttonID: 'add_pod',  buttonLink: '/#newapp',
                                       buttonTitle: 'Add new application', showControls: true};
                appCollection.fetch({wait: true})
                    .done(function(){ App.contents.show(mainLayout); })
                    .fail(utils.notifyWindow);

                that.listenTo(mainLayout, 'app:showloadcontrol', function(id){
                    var breadcrumbsModel = new Backbone.Model(_.extend(
                            _.clone(breadcrumbsData),
                            {breadcrumbs: [{name: 'Predefined Apps'},
                                           {name: id === undefined ?
                                                  'Add new application' :
                                                  'Edit application'}]},
                            {showControls: false})),
                        breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel}),
                        appModel = (id !== undefined) ?
                            appCollection.fullCollection.get(id) :
                            new Model.AppModel();
                    mainLayout.breadcrumbs.show(breadcrumbsView);
                    mainLayout.main.show(new Views.AppLoader({model: appModel}));
                    mainLayout.pager.empty();
                });

                var successModelSaving = function(context) {
                    var breadcrumbsModel = new Backbone.Model(_.extend(
                            _.clone(context.breadcrumbsData), {breadcrumbs: [{name: 'Predefined Apps'}]})),
                        breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel});

                    utils.notifyWindow(
                        'Predefined application "' + context.model.attributes.name +
                            '" is ' + (context.isNew ? 'added' : 'updated'),
                        'success'
                    );
                    context.mainLayout.breadcrumbs.show(breadcrumbsView);
                    if (context.isNew) {
                        context.appCollection.add(context.model);
                    }
                    var view = new Views.AppList(
                        {collection: appCollection.filterByOrigin()});
                    mainLayout.main.show(view);
                    mainLayout.pager.show(new Pager.PaginatorView({view: view}));
                };

                var getValidationError = function(data) {
                    var res = '';
                    if (data.common) {
                        res += JSON.stringify(data.common) + '<br />';
                    }
                    if (data.customVars) {
                        res += 'Invalid custom variables:<br />' +
                            JSON.stringify(data.customVars) + '<br />';
                    }
                    if (data.values) {
                        res += 'Invalid values:<br />' +
                            JSON.stringify(data.values) + '<br />';
                    }
                    if (!res) {
                        res = JSON.stringify(data);
                    }
                    return res;
                };

                var errorModelSaving = function(context, response) {
                    if (!(response.responseJSON &&
                          response.responseJSON.data &&
                          response.responseJSON.data.validationError)){
                        return;
                    }
                    var errorText = getValidationError(
                        response.responseJSON.data.validationError);
                    errorText = 'Your template contains some errors. ' +
                        'Are you shure you want to save it with that errors?' +
                        '<br/><hr/>' +
                        errorText;
                    utils.modalDialog({
                        title: 'Invalid template',
                        body: errorText,
                        show: true,
                        small: true,
                        type: 'saveAnyway',
                        footer: {
                            buttonOk: function(){
                                context.model.save(null, {wait: true})
                                    .done(function(){ successModelSaving(context); })
                                    .fail(utils.notifyWindow);
                            },
                            buttonCancel: true
                        }
                    });
                };

                that.listenTo(mainLayout, 'app:save', function(model){
                    var context = {
                        mainLayout: mainLayout,
                        appCollection: appCollection,
                        isNew: model.isNew(),
                        breadcrumbsData: breadcrumbsData,
                        model: model
                    };
                    // First try to save with validation turned on.
                    // If there will be a validation error, then the user will
                    // be asked about saving template with errors. If user
                    // have confirm, then the model will be saved without
                    // validation flag.
                    var url = model.url() + '?' + $.param({validate: true});
                    model.save(null, {wait: true, url: url})
                        .done(function(){ successModelSaving(context); })
                        .fail(function(xhr){ errorModelSaving(context, xhr); });
                });

                that.listenTo(mainLayout, 'app:cancel', function(){
                    that.listPredefinedApps();
                });

                that.listenTo(mainLayout, 'show', function(){
                    var breadcrumbsModel = new Backbone.Model(_.extend(
                            _.clone(breadcrumbsData), {breadcrumbs: [{name: 'Predefined Apps'}]})),
                        breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel});
                    mainLayout.nav.show(navbar);
                    mainLayout.breadcrumbs.show(breadcrumbsView);
                    appCollection.fetch({
                        wait: true,
                        success: function(){
                            var view = new Views.AppList(
                                {collection: appCollection.filterByOrigin()});
                            mainLayout.main.show(view);
                            mainLayout.pager.show(new Pager.PaginatorView({view: view}));
                        },
                    });

                });
                App.contents.show(mainLayout);
            });
        },

        showSettings: function(){
            var layout_view = new App.Views.SettingsLayout();
            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show();
            });
            App.contents.show(layout_view);
        },

        showPermissionSettings: function(){
            var layout_view = new App.Views.SettingsLayout();
            var permissions_view = new App.Views.PermissionsListView({
                collection: SettingsApp.Data.permissions
            });
            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(permissions_view);
            });
            App.contents.show(layout_view);
        },

        showNotificationSettings: function(){
            var layout_view = new App.Views.SettingsLayout();
            var notifications_view = new App.Views.NotificationsView({
                collection: SettingsApp.Data.notifications
            });
            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(notifications_view);
            });
            App.contents.show(layout_view);
        },

        addNotificationSettings: function(){
            var layout_view = new App.Views.SettingsLayout();
            var notifications_create_view = new App.Views.NotificationCreateView();
            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(notifications_create_view);
            });
            App.contents.show(layout_view);
        },

        editNotificationSettings: function(nid){
            var layout_view = new App.Views.SettingsLayout();
            var notifications_edit_view = new App.Views.NotificationEditView({
                model: SettingsApp.Data.notifications.get(parseInt(nid))
            });
            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(notifications_edit_view);
            });
            App.contents.show(layout_view);
        },

        editProfileSettings: function(){
            var that = this;
            require(['app_data/settings/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    userModel = App.currentUser;
                that.listenTo(layoutView, 'show', function(){
                    App.getTimezones().done(function(timezones){
                        userModel.fetch({
                            wait: true,
                            success: function(model, resp, opts){
                                layoutView.nav.show(navbar);
                                layoutView.main.show(new Views.ProfileEditView({ model: model, timezones : timezones}))
                            },
                            error: function(model, response){
                                utils.notifyWindow(response);
                            },
                        });
                    })
                });
                App.contents.show(layoutView);
            });
        },

        showGeneralSettings: function(){
            var that = this;
            require(['app_data/settings/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                    settingsCollection = new Model.SettingsCollection();
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    App.getSystemSettingsCollection().done(function(settingsCollection){
                        layoutView.main.show(new Views.GeneralView({ collection: settingsCollection }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showLicense: function(){
            var that = this;
            require(['app_data/settings/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                    licenseModel = new Model.LicenseModel();
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    App.getLicenseModel().done(function(license){
                        layoutView.main.show(new Views.LicenseView({ model: license }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showNetworks: function(){
            var that = this;
            require(['app_data/ippool/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.NetworksLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    App.getIPPoolCollection().done(function(ippoolCollection){
                        layoutView.nav.show(navbar);
                        layoutView.main.show(new Views.BreadcrumbView());
                        layoutView.aside.show(new Views.AsideView());
                        layoutView.left.show(new Views.LeftView({
                            collection: ippoolCollection
                        }));
                        layoutView.right.show(new Views.RightView({
                            collection: new Model.NetworkCollection()
                        }));
                    });
                });
                that.listenTo(layoutView, 'ippool:network:picked', function(id){
                    App.getIPPoolCollection().done(function(ippoolCollection){
                        var item = ippoolCollection.findWhere({id: id});
                        layoutView.nav.show(navbar);
                        layoutView.main.show(new Views.BreadcrumbView());
                        layoutView.aside.show(new Views.AsideView());
                        ippoolCollection.each(function(m){
                            m.checked = false;
                        });
                        item.checked = true;
                        layoutView.left.show(new Views.LeftView({collection: ippoolCollection}));
                        layoutView.right.show(new Views.RightView({
                            collection: new Model.NetworkCollection(item)
                        }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showCreateNetwork: function(){
            var that = this;
            require(['app_data/ippool/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.NetworksLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.main.show(new Views.NetworkCreateView());
                });
                App.contents.show(layoutView);
            });
        },

        showPersistentVolumes: function(){
            var that = this;
            require(['app_data/pstorage/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    var pvCollection = new Model.PersistentStorageCollection();
                    layoutView.nav.show(navbar);
                    pvCollection.fetch({
                        wait: true,
                        success: function(collection, resp, opts){
                            layoutView.main.show(new Views.PersistentVolumesView({collection: collection}));
                        },
                        error: function(model, response){
                            utils.notifyWindow(response);
                        },
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showIPs: function(){
            var that = this;
            require(['app_data/public_ips/views', 'app_data/menu/views'], function(Views, Menu){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    var ipCollection = new Model.UserAddressCollection();
                    layoutView.nav.show(navbar);
                    ipCollection.fetch({
                        wait: true,
                        success: function(collection, resp, opts){
                            layoutView.main.show(new Views.PublicIPsView({collection: collection}));
                        },
                        error: function(model, response){
                            utils.notifyWindow(response);
                        },
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showNotifications: function(){
            require(['app_data/misc/views'], function(Views){
                App.getNotificationCollection().done(function(notificationCollection){
                    if (notificationCollection.length) {
                        var notificationView = new Views.MessageList({collection: notificationCollection});
                        App.message.show(notificationView);
                    }
                });
            });
        },

        attachNotification: function(data){
            var that = this;
            require(['app_data/misc/views'], function(Views){
                App.getNotificationCollection().done(function(notificationCollection){
                    notificationCollection.add(data);
                    var notificationView = new Views.MessageList({collection: notificationCollection});
                    App.message.show(notificationView);
                });
            });
        },

        detachNotification: function(data){
            if (!App.message.hasView()) { return; }
            var that = this;
            require(['app_data/misc/views'], function(Views){
                App.getNotificationCollection().done(function(notificationCollection){
                    'use strict';
                    notificationCollection.remove(data.id);
                    if (notificationCollection.length) {
                        var notificationView = new Views.MessageList({collection: notificationCollection});
                        App.message.show(notificationView);
                    }
                    else {
                        App.message.empty();
                    }
                });
            });
        }
    });
    return controller;
});
