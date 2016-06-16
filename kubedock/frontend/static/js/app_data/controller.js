define([
    'app_data/app', 'app_data/utils', 'app_data/model',
    'app_data/menu/views', 'app_data/paginator/views', 'app_data/breadcrumbs/views',
], function(App, utils, Model, Menu, Pager, Breadcrumbs){
    "use strict";

    var controller = {
        checkPermissions: function(roles){
            if (App.currentUser && App.currentUser.roleIs.apply(App.currentUser, roles))
                return true;
            if (App.currentUser)  // do not show pageNotFound if user is on "login" view
                this.pageNotFound();
            return false;
        },
        index: function(){
            var admin = App.currentUser.get('rolename') === 'Admin';
            App.navigate(admin ? 'nodes' : 'pods', {trigger: true});
        },
        doLogin: function(options){
            var deferred = new $.Deferred();
            require(['app_data/login/views'], function(Views){
                var loginView = new Views.LoginView(options);
                App.message.empty();  // hide any notification
                utils.preloader.hide();  // hide preloader if there is any
                App.listenTo(loginView,'action:signin', function(authModel){
                    authModel.unset('password');
                    var token = authModel.get('token');
                    App.storage.authData = token;
                    deferred.resolveWith(App, [token]);
                });
                App.contents.show(loginView);
            });
            return deferred;
        },
        showPods: function(){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pods/views/pods_list'], function(Views){
                var suspendedTitle;
                if (App.currentUser.get('suspended')) {
                    suspendedTitle = 'Suspended users can\'t create new containers';
                }
                var listLayout = new Views.PodListLayout(),
                    breadcrumbsLayout = new Breadcrumbs.Layout({points: ['pods']}),
                    button = App.currentUser.roleIs('User', 'TrialUser')
                        && {id: 'add_pod', href: '#pods/new', title: 'Add new container',
                            suspendedTitle: suspendedTitle},
                    breadcrumbsControls = new Breadcrumbs.Controls(
                        {search: true, button: button}),
                    navbar = new Menu.NavList({collection: App.menuCollection});

                that.listenTo(listLayout, 'show', function(){
                    App.getPodCollection().done(function(collection){
                        listLayout.nav.show(navbar);
                        listLayout.header.show(breadcrumbsLayout);
                        breadcrumbsLayout.pods.show(new Breadcrumbs.Text({text: 'Pods'}));
                        breadcrumbsLayout.controls.show(breadcrumbsControls);

                        var view = new Views.PodCollection({collection: collection});
                        listLayout.list.show(view);
                        listLayout.pager.show(new Pager.PaginatorView({view: view}));
                    });
                });

                that.listenTo(listLayout, 'clear:pager', function(){
                    listLayout.pager.empty();
                });

                that.listenTo(breadcrumbsControls, 'search', function(data){
                    App.getPodCollection().done(function(collection){
                        var order = collection.order;
                        if (data.length > 2) {
                            collection = new Model.PodCollection(
                                collection.searchIn(data));
                        }
                        var view = new Views.PodCollection(
                            {collection: collection, order: order});
                        listLayout.list.show(view);
                        listLayout.pager.show(new Pager.PaginatorView({view: view}));
                    });
                });
                App.contents.show(listLayout);
            });
        },

        /**
         * Show basic pod page layout, menu, breadcrumbs.
         *
         * @param {string} id - Pod id.
         * @returns {Promise} Promise of the pod page data (model, layout, views).
         */
        showPodBase: function(id){
            var that = this,
                deferred = $.Deferred();
            require([
                'app_data/pods/views/pod_item',
                'app_data/pods/views/breadcrumbs'
            ], function(Views, PodBreadcrumbs){
                if (that.podPageData && that.podPageData.model.id === id) {
                    deferred.resolveWith(that, [that.podPageData]);
                    return;
                }
                App.getPodCollection().done(function(podCollection){
                    var model = podCollection.fullCollection.get(id);
                    if (model === undefined || model.get('status') === 'deleting'){
                        deferred.rejectWith(that, []);
                        return;
                    }
                    that.listenTo(model, 'remove destroy', function(){
                        App.navigate('pods', {trigger: true});
                    });

                    var itemLayout = new Views.PodItemLayout(),
                        navbar = new Menu.NavList({collection: App.menuCollection}),
                        breadcrumbsLayout = new Breadcrumbs.Layout({points: ['pods', 'podName']});

                    that.listenTo(itemLayout, 'show', function(){
                        itemLayout.nav.show(navbar);
                        itemLayout.header.show(breadcrumbsLayout);
                        breadcrumbsLayout.pods.show(new Breadcrumbs.Link({text: 'Pods', href: '#pods'}));
                        breadcrumbsLayout.podName.show(new PodBreadcrumbs.EditableName({model: model}));
                    });
                    that.listenTo(itemLayout, 'before:destroy', function(){
                        delete this.podPageData;
                    });

                    App.contents.show(itemLayout);

                    that.podPageData = {model: model, itemLayout: itemLayout, navbar: navbar};
                    deferred.resolveWith(that, [that.podPageData]);
                });
            });
            return deferred.promise();
        },

        showPodStats: function(id){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pods/views/pod_item'], function(Views){
                that.showPodBase(id).fail(function(){
                    App.navigate('pods', {trigger: true});
                }).done(function(pageData){
                    var statCollection = new Model.StatsCollection();
                    statCollection.fetch({
                        data: {unit: pageData.model.id},
                        reset: true,
                        success: function(){
                            pageData.itemLayout.controls.show(new Views.ControlsPanel({
                                graphs: true,
                                model: pageData.model
                            }));
                            pageData.itemLayout.info.show(new Views.PodGraph({
                                model: pageData.model,
                                collection: statCollection
                            }));
                        },
                        error: function(collection, response){
                            utils.notifyWindow(response);
                        },
                    });
                });
            });
        },

        showPodContainers: function(id){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pods/views/pod_item'], function(Views){
                that.showPodBase(id).fail(function(){
                    App.navigate('pods', {trigger: true});
                }).done(function(pageData){
                    pageData.itemLayout.controls.show(new Views.ControlsPanel({
                        model: pageData.model
                    }));
                    pageData.itemLayout.info.show(new Views.InfoPanel({
                        collection: pageData.model.get('containers'),
                    }));
                });
            });
        },

        showPodUpgrade: function(id, containerName){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pods/views/pod_item'], function(Views){
                that.showPodBase(id).fail(function(){
                    App.navigate('pods', {trigger: true});
                }).done(function(pageData){
                    pageData.itemLayout.controls.show(new Views.ControlsPanel({
                        upgrade: true,
                        model: pageData.model,
                    }));
                    var newModel = new Model.Pod(pageData.model.toJSON());
                    App.getSystemSettingsCollection().done(function(settings){
                        var billingType = settings.byName('billing_type').get('value'),
                            kubesLimit = settings.byName('max_kubes_per_container').get('value');
                        pageData.itemLayout.info.show(new Views.UpgradeResources({
                            kubesLimit: parseInt(kubesLimit),
                            modelOrig: pageData.model,
                            model: newModel,
                            containerName: containerName,
                            fixedPrice: billingType.toLowerCase() !== 'no billing'
                                && App.userPackage.get('count_type') === 'fixed',
                            collection: newModel.get('containers'),
                        }));
                    });
                });
            });
        },

        showPodContainer: function(id, name){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pods/views/pod_container'], function(Views){
                App.getPodCollection().done(function(podCollection){
                    var wizardLayout = new Views.PodWizardLayout(),
                        pod = podCollection.fullCollection.get(id),
                        model = pod.get('containers').get(name),
                        navbar = new Menu.NavList({ collection: App.menuCollection }),
                        breadcrumbsLayout = new Breadcrumbs.Layout(
                            {points: ['pods', 'pod', 'container']});

                    if (!model)
                        return this.pageNotFound();

                    that.listenTo(pod, 'remove destroy', function(){
                        App.navigate('pods', {trigger: true});
                    });

                    var show = function(View){
                        return wizardLayout.steps.show(new View({model: model}));
                    };

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.nav.show(navbar);
                        wizardLayout.header.show(breadcrumbsLayout);
                        breadcrumbsLayout.pods.show(new Breadcrumbs.Link(
                            {text: 'Pods', href: '#pods'}));
                        breadcrumbsLayout.pod.show(new Breadcrumbs.Link(
                            {text: pod.get('name'), href: '#pods/' + pod.get('id')}));
                        breadcrumbsLayout.container.show(new Breadcrumbs.Text(
                            {text: model.get('image') + ' (' + model.get('name') + ')'}));

                        show(Views.WizardLogsSubView);
                    });

                    that.listenTo(wizardLayout, 'step:portconf',
                        _.partial(show, Views.WizardGeneralSubView));
                    that.listenTo(wizardLayout, 'step:envconf',
                        _.partial(show, Views.WizardEnvSubView));
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

        /**
         * Prepare basic data and layout for edit pod wizard.
         *
         * @param {Object} [options={}] - Cached data from other wizard step or
         *      existing pod.
         * @param {Model.Pod} [options.podModel] - Pod model.
         * @param {Object} [options.podModel.origEnv] -
         *      Cached original env vars from images.
         * @param [options.layout] - Pod wizard layout.
         *
         * @returns {Promise} - Promise of filled `options`.
         */
        podWizardBase: function(options){
            this.podWizardData = options = options || this.podWizardData || {};
            var that = this,
                deferred = $.Deferred();
            require([
                'app_data/pods/views/pod_create',
                'app_data/pods/views/breadcrumbs',
            ], function(Views, PodBreadcrumbs){
                App.getPodCollection().done(function(podCollection){
                    if (!options.podModel){
                        options.podModel = new Model.Pod();

                        if (podCollection.length === 0) {
                            options.podModel.set('name', 'New Pod #1');
                        } else {
                            var maxName = _.max(podCollection.map(function(m){
                                var match = /^New Pod #(\d+)$/.exec(m.get('name'));
                                return match !== null ? +match[1] : 0;
                            }));
                            options.podModel.set('name', 'New Pod #' + (maxName + 1));
                        }
                    }
                    var model = options.podModel;
                    model.lastEditedContainer = model.lastEditedContainer || {id: null, isNew: true};
                    model.origEnv = model.origEnv || {};

                    if (!options.layout){
                        options.layout = new Views.PodWizardLayout();

                        var navbar = new Menu.NavList({collection: App.menuCollection}),
                            breadcrumbsLayout = new Breadcrumbs.Layout({points: ['pods', 'pod']});

                        that.listenTo(options.layout, 'show', function(){
                            options.layout.nav.show(navbar);
                            options.layout.header.show(breadcrumbsLayout);
                            breadcrumbsLayout.pods.show(
                                new Breadcrumbs.Link({text: 'Pods', href: '#pods'}));
                            breadcrumbsLayout.pod.show(
                                new PodBreadcrumbs.EditableName({model: model}));
                        });
                        that.listenTo(options.layout, 'before:destroy', function(){
                            if (that.podWizardData === options)
                                delete that.podWizardData;
                        });
                    }

                    App.contents.show(options.layout);
                    deferred.resolveWith(that, [options, Views]);
                });
            });
            return deferred;
        },

        podWizardStepImage: function(options){
            if (!this.checkPermissions(['User', 'TrialUser']))
                return;
            this.podWizardBase(options).done(function(options, Views){
                options.registryURL = options.registryURL || 'registry.hub.docker.com';
                options.imageCollection = options.imageCollection
                    || new Model.ImagePageableCollection();
                options.selectImageViewModel = options.selectImageViewModel
                    || new Backbone.Model({query: ''});

                var view = new Views.GetImageView({
                    pod: options.podModel, model: options.selectImageViewModel,
                    collection: new Model.ImageCollection(
                        options.imageCollection.fullCollection.models),
                });

                this.listenTo(view, 'image:searchsubmit', function(){
                    options.imageCollection.fullCollection.reset();
                    options.imageCollection.getFirstPage({
                        wait: true,
                        data: {searchkey: options.selectImageViewModel.get('query'),
                               url: options.registryURL},
                        success: function(collection, response, opts){
                            view.collection.reset(collection.models);
                            if (collection.length === 0) {
                                utils.notifyWindow(
                                    'We couldn\'t find any results for this search',
                                    'success');
                                view.loadMoreButtonHide();
                            } else {
                                view.loadMoreButtonWait();
                            }
                        },
                        error: function(collection, response){
                            utils.notifyWindow(response);
                            view.loadMoreButtonWait();
                        },
                    });
                });
                this.listenTo(view, 'image:getnextpage', function(){
                    options.imageCollection.getNextPage({
                        wait: true,
                        data: {searchkey: options.selectImageViewModel.get('query'),
                               url: options.registryURL},
                        success: function(collection, response, opts){
                            view.collection.add(collection.models);
                            if (!collection.length)
                                view.loadMoreButtonHide();
                            else
                                view.loadMoreButtonWait();
                        },
                        error: function(collection, response){
                            utils.notifyWindow(response);
                            view.loadMoreButtonWait();
                        },
                    });
                });
                this.listenTo(view, 'image:selected', function(image, auth){
                    utils.preloader.show();
                    new Model.Image().fetch({
                        data: JSON.stringify({image: image, auth: auth}),
                        success: function(image){
                            var containerModel = Model.Container.fromImage(image);
                            options.podModel.get('containers')
                                .remove(options.podModel.lastEditedContainer.id);
                            options.podModel.lastEditedContainer.id = containerModel.id;
                            options.podModel.get('containers').add(containerModel);
                            App.controller.podWizardStepGeneral(options);
                        },
                    }).always(utils.preloader.hide).fail(utils.notifyWindow);
                });

                this.listenTo(view, 'step:complete', this.podWizardStepFinal);
                options.layout.steps.show(view);
            });
        },

        podWizardStepGeneral: function(options){
            if (!this.checkPermissions(['User', 'TrialUser']))
                return;
            this.podWizardBase(options).done(function(options, Views){
                var containerID = options.podModel.lastEditedContainer.id;
                if (containerID == null)
                    return this.podWizardStepImage(options);

                var view = new Views.WizardPortsSubView({
                        model: options.podModel.get('containers').get(containerID),
                    });

                this.listenTo(view, 'step:envconf', this.podWizardStepEnv);
                this.listenTo(view, 'step:getimage', this.podWizardStepImage);
                options.layout.steps.show(view);
            });
        },

        podWizardStepEnv: function(options){
            if (!this.checkPermissions(['User', 'TrialUser']))
                return;
            this.podWizardBase(options).done(function(options, Views){
                var containerID = options.podModel.lastEditedContainer.id,
                    containerModel = options.podModel.get('containers').get(containerID),
                    image = containerModel.get('image'),
                    view = new Views.WizardEnvSubView({model: containerModel});

                if (!(containerModel.get('image') in options.podModel.origEnv))
                    options.podModel.origEnv[image] = _.map(containerModel.attributes.env, _.clone);
                containerModel.origEnv = _.map(options.podModel.origEnv[image], _.clone);

                this.listenTo(view, 'step:portconf', this.podWizardStepGeneral);
                this.listenTo(view, 'step:complete', this.podWizardStepFinal);
                options.layout.steps.show(view);
            });
        },

        podWizardStepFinal: function(options){
            if (!this.checkPermissions(['User', 'TrialUser']))
                return;
            var that = this;
            $.when(
                this.podWizardBase(options),
                App.getPodCollection(),
                App.getSystemSettingsCollection()
            ).done(function(base, podCollection, settingsCollection){
                var options = base[0], Views = base[1];

                var model = options.podModel;

                var checkKubeTypes = function(ensureSelected){
                    if (model.get('kube_type') === Model.KubeType.noAvailableKubeTypes.id){
                        if (App.userPackage.getKubeTypes().any( function(kt){return kt.get('available'); }))
                            Model.KubeType.noAvailableKubeTypes.notifyConflict();
                        else
                            Model.KubeType.noAvailableKubeTypes.notify();
                        return true;
                    } else if (model.get('kube_type') === undefined){
                        utils.notifyWindow('Please, select kube type.');
                        return true;
                    }
                };

                model.solveKubeTypeConflicts();
                checkKubeTypes(/*ensureSelected*/false);

                var billingType = settingsCollection.byName('billing_type').get('value'),
                    kubesLimit = settingsCollection.byName('max_kubes_per_container').get('value'),
                    payg = App.userPackage.get('count_type') === 'payg',
                    view = new Views.WizardCompleteSubView({
                        model: model,
                        kubesLimit: kubesLimit,
                        hasBilling: billingType.toLowerCase() !== 'no billing',
                        payg: payg,
                    });
                that.listenTo(view, 'pod:save', function(){
                    if (checkKubeTypes(/*ensureSelected*/true)) return;
                    utils.preloader.show();
                    model.save()
                        .always(utils.preloader.hide)
                        .fail(utils.notifyWindow)
                        .done(function(){
                            podCollection.fullCollection.add(model);
                            App.navigate('pods').controller.showPods();
                        });
                });
                that.listenTo(view, 'pod:pay_and_run', function(){
                    if (checkKubeTypes(/*ensureSelected*/true)) return;
                    if (billingType.toLowerCase() !== 'no billing' && !payg) {
                        utils.preloader.show();
                        podCollection.fullCollection.create(model, {
                            wait: true,
                            success: function(){
                                new Backbone.Model().save({
                                    pod: JSON.stringify(model),
                                }, {
                                    url: '/api/billing/order',
                                }).always(
                                    utils.preloader.hide
                                ).fail(
                                    utils.notifyWindow
                                ).done(function(response){
                                    if(response.data.status === 'Paid') {
                                        if (model && model.id) {
                                            if (model.get('status') !== 'running') {
                                                model.set('status', 'pending');
                                            }
                                            model.get('containers').each(function(c){
                                                if (c.get('state') !== 'running') {
                                                    c.set('state', 'pending');
                                                }
                                            });
                                            App.navigate('pods/' + model.id)
                                                .controller.showPodContainers(model.id);
                                        }
                                        else {
                                            App.navigate('pods')
                                                .controller.showPods();
                                        }
                                    } else {
                                        utils.modalDialog({
                                            title: 'Insufficient funds',
                                            body: 'Your account funds seem to be'
                                                + ' insufficient for the action.'
                                                + ' Would you like to go to billing'
                                                + ' system to make the payment?',
                                            small: true,
                                            show: true,
                                            footer: {
                                                buttonOk: function(){
                                                    window.location = response.data.redirect;
                                                },
                                                buttonCancel: function(){
                                                    App.navigate('pods')
                                                        .controller.showPods();
                                                },
                                                buttonOkText: 'Go to billing',
                                                buttonCancelText: 'No, thanks'
                                            }
                                        });
                                    }
                                });
                            },
                            error: function(model, response){
                                utils.preloader.hide();
                                utils.notifyWindow(response);
                            }
                        });
                    }
                });
                that.listenTo(view, 'step:envconf', that.podWizardStepEnv);
                that.listenTo(view, 'step:getimage', that.podWizardStepImage);
                that.listenTo(view, 'step:portconf', that.podWizardStepGeneral);
                options.layout.steps.show(view);
            });
        },

        showNodes: function(options){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/nodes/views'], function(Views){
                var layoutView = new Views.NodesLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    App.getNodeCollection().done(function(nodeCollection){
                        if (_.has(options, 'deleted')) {
                            nodeCollection.fullCollection.remove(options.deleted);
                        }
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
                        var filteredCollection = new Model.NodeCollection(
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/nodes/views'], function(Views){
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/nodes/views'], function(Views){
                App.getNodeCollection().done(function(nodeCollection){
                    var node = nodeCollection.get(nodeId);
                        //breadcrumbsModel = new Backbone.Model({hostname: node.get('hostname')});
                        //sidebarModel = new Backbone.Model({tab: tab, });

                    if (node == null){
                        App.navigate('nodes', {trigger: true});
                        return;
                    }

                    that.listenTo(node, 'remove destroy', function(){
                        App.navigate('nodes', {trigger: true});
                    });

                    var layoutView = new Views.NodeDetailedLayout({nodeId: nodeId, tab: tab}),
                        navbar = new Menu.NavList({collection: App.menuCollection});

                    that.listenTo(layoutView, 'show', function(){

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
                    App.contents.show(layoutView);
                });
            });
        },

        // TODO: remove all stuff in this block
        // showOnlineUsers: function(){
        //     var layout_view = new App.Views.UsersLayout(),
        //         online_users_list_view = new App.Views.OnlineUsersListView({
        //             collection: App.Data.onlineUsers
        //         }),
        //         user_list_pager = new App.Views.PaginatorView({
        //             view: online_users_list_view
        //         });
        //
        //     this.listenTo(layout_view, 'show', function(){
        //         layout_view.main.show(online_users_list_view);
        //         layout_view.pager.show(user_list_pager);
        //     });
        //     App.contents.show(layout_view);
        // },
        //
        // showUserActivity: function(user_id){
        //     var that = this,
        //         layout_view = new App.Views.UsersLayout();
        //
        //     $.ajax({
        //         'url': '/api/users/a/' + user_id,
        //         success: function(rs){
        //             UsersApp.Data.activities = new UsersApp.Data.ActivitiesCollection(rs.data);
        //             var activities_view = new App.Views.UsersActivityView({
        //                     collection: UsersApp.Data.activities
        //                 }),
        //                 activities_list_pager = new App.Views.PaginatorView({
        //                     view: activities_view
        //                 });
        //
        //             that.listenTo(layout_view, 'show', function(){
        //                 layout_view.main.show(activities_view);
        //                 layout_view.pager.show(activities_list_pager);
        //             });
        //             App.contents.show(layout_view);
        //         },
        //     });
        // },

        showUsers: function(){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/users/views'], function(Views){
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/users/views'], function(Views){
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/users/views'], function(Views){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    $.when(App.getRoles(), App.getPackages(), App.getTimezones()).done(function(roles, packages, timezones){
                        layoutView.main.show(new Views.UserCreateView({
                            model: new Model.UserModel(),
                            roles: roles,
                            packages: packages,
                            timezones: timezones,
                        }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showEditUser: function(userId){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/users/views'], function(Views){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    $.when(App.getUserCollection(), App.getRoles(),
                           App.getTimezones()).done(function(userCollection, roles, timezones){
                        var model = userCollection.fullCollection.get(Number(userId)),
                            view = new Views.UsersEditView({
                                model: model, kubeTypes: App.kubeTypeCollection,
                                roles: roles, packages: App.packageCollection,
                                timezones: timezones});
                        layoutView.main.show(view);
                        $('#pager').hide();
                        $('#user-header h2').text('Edit');
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showProfileUser: function(userId){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/users/views'], function(Views){
                var layoutView = new Views.UsersLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    App.getUserCollection().done(function(userCollection){
                        var userModel = userCollection.fullCollection.get(Number(userId)),
                            userProfileView = new Views.UserProfileView({
                                model: userModel, kubeTypes: App.kubeTypeCollection});
                        layoutView.main.show(userProfileView);
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showProfileUserLogHistory: function(userId){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/users/views'], function(Views){
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/papps/views'], function(Views){
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
                        res += _.escape(JSON.stringify(data.common)) + '<br />';
                    }
                    if (data.customVars) {
                        res += 'Invalid custom variables:<br />' +
                            _.escape(JSON.stringify(data.customVars)) + '<br />';
                    }
                    if (data.values) {
                        res += 'Invalid values:<br />' +
                            _.escape(JSON.stringify(data.values)) + '<br />';
                    }
                    if (data.kuberdock) {
                        var kuberdock = typeof data.kuberdock == 'string'
                                ? [data.kuberdock] : data.kuberdock;
                        kuberdock = _.map(kuberdock, function(err){
                            return typeof err == 'string' ? err : JSON.stringify(err);
                        });

                        res += 'Invalid "kuberdock" section:<br />- ' +
                            _.map(kuberdock, _.escape).join('<br />- ') + '<br />';
                    }
                    if (!res) {
                        res = JSON.stringify(data);
                    }
                    return res;
                };

                var errorModelSaving = function(context, response) {
                    if ( response && !(response.responseJSON &&
                        response.responseJSON.data &&
                        response.responseJSON.data.validationError)){
                        utils.notifyWindow(response);
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
            return App.currentUser.get('rolename') === 'Admin'
                ? this.showGeneralSettings()
                : this.editProfileSettings();
        },

        editProfileSettings: function(){
            var that = this;
            require(['app_data/settings/views'], function(Views){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    userModel = App.currentUser;
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    utils.preloader.show();
                    App.getTimezones().done(function(timezones){
                        utils.preloader.hide();
                        userModel.fetch({
                            wait: true,
                            success: function(model, resp, opts){
                                layoutView.main.show(new Views.ProfileEditView(
                                    { model: model, timezones : timezones}));
                            },
                            error: function(model, response){
                                utils.notifyWindow(response);
                            },
                        });
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showGeneralSettings: function(){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/settings/views'], function(Views){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/settings/views'], function(Views){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    utils.preloader.show();
                    App.getLicenseModel().done(function(license){
                        utils.preloader.hide();
                        layoutView.main.show(new Views.LicenseView({ model: license }));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showNetworks: function(){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/ippool/views'], function(Views){
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
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/ippool/views'], function(Views){
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
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pstorage/views'], function(Views){
                var layoutView = new Views.PersistentVolumesLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});

                that.listenTo(layoutView, 'show', function(){
                    var pvCollection = new Model.PaginatedPersistentStorageCollection();
                    layoutView.nav.show(navbar);
                    pvCollection.fetch({
                        wait: true,
                        success: function(collection, resp, opts){
                            var view = new Views.PersistentVolumesView({collection: collection});
                            layoutView.main.show(view);
                            layoutView.pager.show(new Pager.PaginatorView({view: view}));
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
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/public_ips/views'], function(Views){
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
            require(['app_data/misc/views'], function(Views){
                App.getNotificationCollection().done(function(notificationCollection){
                    notificationCollection.remove(
                        notificationCollection.filter(function(m){
                            return m.get('target').indexOf(data.target) !== -1;
                        })
                    );
                    if (notificationCollection.length) {
                        var notificationView = new Views.MessageList({collection: notificationCollection});
                        App.message.show(notificationView);
                    }
                    else {
                        App.message.empty();
                    }
                });
            });
        },

        pageNotFound: function(){
            var that = this;
            require(['app_data/misc/views'], function(Views){
                var layoutView = new Views.PageLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.main.show(new Views.PageNotFound());
                });
                App.contents.show(layoutView);
            });
        }
    };

    return Marionette.Object.extend(controller);
});
