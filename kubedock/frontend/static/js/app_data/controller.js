define([
    'app_data/app', 'app_data/utils', 'app_data/model',
    'app_data/menu/views', 'app_data/paginator/views', 'app_data/breadcrumbs/views',
], function(App, utils, Model, Menu, Pager, Breadcrumbs){
    'use strict';

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
        changeAppPackage: function(podID){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            var that = this;
            require(['app_data/pa/views'], function(Views){
                App.getPodCollection().done(function(podCollection){
                    var pod = podCollection.get(podID),
                        templateID = pod.get('template_id'),
                        currentPlanName = pod.get('template_plan_name');
                    if (!templateID || !currentPlanName)
                        return that.pageNotFound();
                    var predefinedApp = new Model.AppModel({id: templateID}),
                        plans = new Model.Plans();
                    plans.podID = podID;
                    $.when(predefinedApp.fetch(), plans.fetch())
                        .fail(_.bind(that.pageNotFound, that))
                        .done(function(){
                            predefinedApp.set('plans', plans);
                            var plansLayout = new Views.PlansLayout({
                                    pod: pod, model: predefinedApp,
                                }),
                                plansListView = new Views.PlansList({
                                    pod: pod, model: predefinedApp,
                                    collection: plans,
                                }),
                                breadcrumbsLayout = new Breadcrumbs.Layout(
                                    {points: ['pods', 'pod', 'container']}),
                                navbar = new Menu.NavList({collection: App.menuCollection});

                            plans.each(function(plan){
                                plan.set('current', plan.get('name') === currentPlanName);
                            });

                            plansLayout.on('show', function(){
                                plansLayout.header.show(navbar);
                                plansLayout.breadcrumbs.show(breadcrumbsLayout);
                                breadcrumbsLayout.pods.show(new Breadcrumbs.Link(
                                    {text: 'Pods', href: '#pods'}));
                                breadcrumbsLayout.pod.show(new Breadcrumbs.Link(
                                    {text: pod.get('name'), href: '#pods/' + pod.get('id')}));
                                breadcrumbsLayout.container.show(new Breadcrumbs.Text(
                                    {text: "Switch Package for " + predefinedApp.get('name')}));

                                plansLayout.plans.show(plansListView);
                            });
                            App.contents.show(plansLayout);
                        });
                });
            });
        },
        doLogin: function(options){
            var deferred = new $.Deferred();
            require(['app_data/login/views'], function(Views){
                var loginView = new Views.LoginView(options);
                App.message.empty();  // hide any notification
                utils.preloader.hide();  // hide preloader if there is any
                App.listenTo(loginView, 'action:signin', function(authModel){
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
                var suspendedTitle,
                    isInternalUser = App.currentUser.usernameIs('kuberdock-internal');
                if (App.currentUser.get('suspended')) {
                    suspendedTitle = 'Suspended users can\'t create new containers';
                }
                var listLayout = new Views.PodListLayout(),
                    breadcrumbsLayout = new Breadcrumbs.Layout({points: ['pods']}),
                    button = App.currentUser.roleIs('User', 'TrialUser') && !isInternalUser && {
                        id: 'add_pod', href: '#pods/new', title: 'Add new container',
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

                        var filteredCollection = collection.getFiltered(function(model){
                            var searchFilter = !this.searchString ||
                                this.searchString.length < 3 ||
                                model.get('name').indexOf(this.searchString) !== -1;
                            return searchFilter && (this.showDeleted ||
                                model.get('status') !== 'paid_deleted');
                        });
                        var view = new Views.PodCollection({collection: filteredCollection});
                        listLayout.list.show(view);
                        listLayout.pager.show(new Pager.PaginatorView({view: view}));
                        view.listenTo(breadcrumbsControls, 'search', view.search);
                    });
                });

                that.listenTo(listLayout, 'clear:pager', function(){
                    listLayout.pager.empty();
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
                'app_data/pods/views/breadcrumbs',
                'app_data/pods/views/messages',
            ], function(Views, PodBreadcrumbs, PodMessages){
                if (that.podPageData && that.podPageData.model.id === id) {
                    deferred.resolveWith(that, [that.podPageData]);
                    return;
                }
                $.when(
                    App.getPodCollection(),
                    App.getSystemSettingsCollection()
                ).done(function(podCollection, settings){
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
                        messagesLayout = new PodMessages.Layout(),
                        breadcrumbsLayout = new Breadcrumbs.Layout({points: ['pods', 'podName']}),
                        fixedPrice = App.userPackage.get('count_type') === 'fixed'
                            && settings.byName('billing_type')
                                .get('value').toLowerCase() !== 'no billing';

                    that.listenTo(itemLayout, 'show', function(){
                        itemLayout.nav.show(navbar);

                        itemLayout.header.show(breadcrumbsLayout);
                        breadcrumbsLayout.pods.show(
                            new Breadcrumbs.Link({text: 'Pods', href: '#pods'}));
                        breadcrumbsLayout.podName.show(
                            new PodBreadcrumbs.EditableName({model: model}));

                        itemLayout.messages.show(messagesLayout);
                        messagesLayout.podHasChanges.show(
                            new PodMessages.PodHasChanges({
                                fixedPrice: fixedPrice, model: model
                            }));
                        messagesLayout.postDescription.show(
                            new PodMessages.PostDescription({model: model}));
                    });
                    that.listenTo(itemLayout, 'before:destroy', function(){
                        delete this.podPageData;
                    });

                    App.contents.show(itemLayout);

                    that.podPageData = {model: model, fixedPrice: fixedPrice,
                                        itemLayout: itemLayout, navbar: navbar};
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
                    var statCollection = new Model.PodStatsCollection(
                        null, {podId: pageData.model.id});
                    statCollection.fetch({reset: true})
                        .always(function(){
                            pageData.itemLayout.controls.show(new Views.ControlsPanel({
                                graphs: true,
                                model: pageData.model,
                                fixedPrice: pageData.fixedPrice,
                            }));
                        })
                        .done(function(){
                            pageData.itemLayout.info.show(new Views.PodGraph({
                                model: pageData.model,
                                collection: statCollection,
                            }));
                        })
                        .fail(function(xhr){
                            pageData.itemLayout.info.show(new Views.PodGraph({
                                model: pageData.model,
                                collection: statCollection,
                                error: xhr.responseJSON && xhr.responseJSON.data,
                            }));
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
                        fixedPrice: pageData.fixedPrice,
                        model: pageData.model
                    }));
                    var diffCollection = pageData.model.getContainersDiffCollection();
                    pageData.itemLayout.info.show(
                        new Views.ContainersPanel({collection: diffCollection}));
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
                        fixedPrice: pageData.fixedPrice,
                    }));
                    var newModel = new Model.Pod(pageData.model.toJSON());
                    App.getSystemSettingsCollection().done(function(settings){
                        var billingType = settings.byName('billing_type').get('value'),
                            kubesLimit = settings.byName('max_kubes_per_container').get('value');
                        pageData.itemLayout.info.show(new Views.UpgradeResources({
                            kubesLimit: parseInt(kubesLimit, 10),
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

        // TODO: rename views and events names; refactoring
        showPodContainer: function(id, name, tab){
            if (!this.checkPermissions(['User', 'TrialUser', 'LimitedUser']))
                return;
            if (!tab)
                return App.navigate('pods/' + id + '/container/' + name + '/logs')
                    .controller.showPodContainer(id, name, 'logs');
            var that = this;
            require([
                'app_data/pods/views/pod_container',
                'app_data/pods/views/messages',
            ], function(Views, PodMessages){
                $.when(App.getPodCollection(),
                    App.getSystemSettingsCollection()
                    ).done(function(podCollection, settings){
                    var wizardLayout = new Views.PodWizardLayout(),
                        pod = podCollection.fullCollection.get(id),
                        diffCollection = pod.getContainersDiffCollection(),
                        model = diffCollection.get(name),
                        navbar = new Menu.NavList({ collection: App.menuCollection }),
                        breadcrumbsLayout = new Breadcrumbs.Layout(
                            {points: ['pods', 'pod', 'container']}),
                        messagesLayout = new PodMessages.Layout(),
                        tabViews = {
                            logs: Views.WizardLogsSubView,
                            stats: Views.WizardStatsSubView,
                            general: Views.WizardGeneralSubView,
                            env: Views.WizardEnvSubView,
                        },
                        fixedPrice = App.userPackage.get('count_type') === 'fixed'
                            && settings.byName('billing_type')
                                .get('value').toLowerCase() !== 'no billing';

                    if (!model || !_.contains(_.keys(tabViews), tab))
                        return that.pageNotFound();

                    wizardLayout.listenTo(pod, 'remove destroy', function(){
                        App.navigate('pods', {trigger: true});
                    });

                    var showTab = function(newTab, changeURL){
                        tab = newTab;
                        if (changeURL)
                            App.navigate('pods/' + id + '/container/' + name + '/' + tab);
                        if (tab === 'stats'){
                            var statCollection = new Model.ContainerStatsCollection(
                                    null,
                                    {podId: pod.id, containerId: model.id}
                            );
                            statCollection.fetch({
                                reset: true,
                            }).done(function(){
                                wizardLayout.steps.show(new Views.WizardStatsSubView({
                                    model: model, collection: statCollection,
                                }));
                            }).fail(function(xhr){
                                wizardLayout.steps.show(new Views.WizardStatsSubView({
                                    model: model, collection: statCollection,
                                    error: xhr.responseJSON && xhr.responseJSON.data,
                                }));
                            });
                        } else {
                            return wizardLayout.steps.show(new tabViews[tab]({model: model}));
                        }
                    };

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.nav.show(navbar);

                        wizardLayout.header.show(breadcrumbsLayout);
                        breadcrumbsLayout.pods.show(new Breadcrumbs.Link(
                            {text: 'Pods', href: '#pods'}));
                        breadcrumbsLayout.pod.show(new Breadcrumbs.Link(
                            {text: pod.get('name'), href: '#pods/' + pod.get('id')}));
                        breadcrumbsLayout.container.show(new Breadcrumbs.Text(
                            {text: (model.get('before') ||
                                    model.get('after')).get('image')}));

                        wizardLayout.messages.show(messagesLayout);
                        messagesLayout.podHasChanges.show(
                            new PodMessages.PodHasChanges({
                                fixedPrice: fixedPrice, model: pod
                            }));

                        showTab(tab);
                    });
                    wizardLayout.listenTo(diffCollection, 'update reset', function(){
                        var diff = diffCollection.get(name);
                        if (!diff){
                            App.navigate('pods/' + id, {trigger: true});
                            return;
                        }
                        if (model !== diff){
                            model = diff;
                            showTab(tab);
                        }
                    });

                    that.listenTo(wizardLayout, 'step:portconf',
                                  _.partial(showTab, 'general', true));
                    that.listenTo(wizardLayout, 'step:envconf',
                                  _.partial(showTab, 'env', true));
                    that.listenTo(wizardLayout, 'step:statsconf',
                                  _.partial(showTab, 'stats', true));
                    that.listenTo(wizardLayout, 'step:logsconf',
                                  _.partial(showTab, 'logs', true));
                    App.contents.show(wizardLayout);
                });
            });
        },


        /**
         * Go to the last step of edit pod wizard.
         *
         * @param {string} id - The ID of the pod.
         */
        editPodBase: function(id){
            var that = this,
                deferred = $.Deferred(),
                persistentDrives = new Model.PersistentStorageCollection();
            $.when(
                App.getPodCollection(),
                persistentDrives.fetch()
            ).done(function(podCollection){
                var originalModel = podCollection.fullCollection.get(id);
                if (!originalModel){
                    deferred.rejectWith(that, []);
                    return;
                }

                // create copy of original model, so it won't be affected by SSE and stuff
                var podConfig = utils.deepClone(originalModel.toJSON()),
                    originalModelCopy = new Model.Pod(podConfig);
                if (!originalModelCopy.get('edited_config')){
                    // copy original config to edited_config (if latter is empty)
                    originalModelCopy.set('edited_config',
                        _.partial(_.pick, podConfig).apply(
                            _, originalModelCopy.persistentAttributes));
                }
                var model = originalModelCopy.get('edited_config');
                model.persistentDrives = persistentDrives;
                deferred.resolveWith(that, [{podModel: model}]);
            });
            return deferred.promise();
        },

        /**
         * Go to the last step of edit pod wizard.
         *
         * @param {string} id - The ID of the pod.
         */
        editEntirePod: function(id){
            this.editPodBase(id)
                .fail(function(){ this.pageNotFound(); })
                .done(function(options){
                    options.podModel.wizardState = {
                        flow: 'EDIT_ENTIRE_POD',
                    };
                    this.podWizardStepFinal(options);
                });
        },
        /**
         * Go to the third step of edit pod wizard.
         *
         * @param {string} id - The ID of the pod.
         * @param {string} containerID - The name of the container.
         */
        editContainerEnv: function(id, containerID){
            this.editPodBase(id)
                .fail(function(){ this.pageNotFound(); })
                .done(function(options){
                    var container = options.podModel.get('containers').get(containerID);
                    if (!container)
                        return this.pageNotFound();
                    options.podModel.wizardState = {
                        flow: 'EDIT_CONTAINER_ENV',
                        container: container,
                    };
                    this.podWizardStepEnv(options);
                });
        },
        /**
         * Go to the second step of edit pod wizard.
         *
         * @param {string} id - The ID of the pod.
         * @param {string} containerID - The name of the container.
         */
        editContainerGeneral: function(id, containerID){
            this.editPodBase(id)
                .fail(function(){ this.pageNotFound(); })
                .done(function(options){
                    var container = options.podModel.get('containers').get(containerID);
                    if (!container)
                        return this.pageNotFound();
                    options.podModel.wizardState = {
                        flow: 'EDIT_CONTAINER_GENERAL',
                        container: container,
                    };
                    this.podWizardStepGeneral(options);
                });
        },

        /**
         * Prepare basic data and layout for edit pod wizard.
         *
         * @param {Object} [options={}] - Cached data from other wizard step or
         *      existing pod.
         * @param {Model.Pod} [options.podModel] - Pod model. In case of editing
         *      existent pod, create temporal model in "edited_config" field and use it.
         * @param [options.layout] - Pod wizard layout.
         *
         * @param {Object} [options.podModel.wizardState={}] -
         *      Informations about current state and previous actions that is
         *      used to determine how and where user can go next.
         * @param {bool} [options.podModel.wizardState.addContainerFlow] -
         *      Indicates that user is in a process of adding a new container
         *      to the pod (not editing one).
         * @param {Model.container} [options.podModel.wizardState.container] -
         *      The container user works with.
         * @param {string} [options.podModel.wizardState.flow='CREATE_POD'] -
         *      General goal of this wizard. Must be one of: CREATE_POD,
         *      EDIT_ENTIRE_POD, EDIT_CONTAINER_ENV, EDIT_CONTAINER_GENERAL.
         *
         * @returns {Promise} - Promise of filled `options`.
         */
        podWizardBase: function(options){
            this.podWizardData = options = options || this.podWizardData || {};
            var that = this,
                deferred = $.Deferred();
            require([
                'app_data/pods/views/pod_edit',
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
                    var pod = options.podModel;
                    if (!pod.wizardState){
                        pod.wizardState = {
                            flow: 'CREATE_POD',
                            addContainerFlow: true,
                        };
                    }
                    pod.originalImages = pod.originalImages
                        || new Backbone.Collection([], {model: Model.Image});

                    if (!options.layout){
                        options.layout = new Views.PodWizardLayout();

                        var navbar = new Menu.NavList({collection: App.menuCollection}),
                            breadcrumbsLayout = new Breadcrumbs.Layout({points: ['pods', 'pod']});

                        that.listenTo(options.layout, 'show', function(){
                            options.layout.nav.show(navbar);
                            options.layout.header.show(breadcrumbsLayout);
                            breadcrumbsLayout.pods.show(
                                new Breadcrumbs.Link({text: 'Pods', href: '#pods'}));

                            var editNameModel;
                            if (pod.wizardState.flow === 'CREATE_POD'){
                                editNameModel = pod;
                            } else {
                                // in case of pod edit, we use a copy of the original model
                                var originalModelCopy = pod.editOf();
                                editNameModel = podCollection.fullCollection.get(originalModelCopy);
                                // so we need to update name in both models
                                originalModelCopy.listenTo(editNameModel, 'change:name', function(){
                                    this.set('name', editNameModel.get('name'));
                                });
                            }
                            breadcrumbsLayout.pod.show(
                                new PodBreadcrumbs.EditableName({model: editNameModel}));
                        });
                        that.listenTo(options.layout, 'before:destroy', function(){
                            if (that.podWizardData === options)
                                delete that.podWizardData;
                        });
                        that.listenTo(options.layout, 'pod:save_changes', function(){
                            utils.preloader.show();
                            var originalModel = podCollection.fullCollection.get(pod.editOf()),
                                oldEdited = originalModel.get('edited_config');
                            originalModel.set('edited_config', pod.toJSON()).command('edit')
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow,
                                      function(){ originalModel.set('edited_config', oldEdited); })
                                .done(function(){
                                    delete originalModel.applyingChangesStarted;
                                    pod.editOf().cleanup();  // backbone-associations, prevent leak
                                    var url = 'pods/' + originalModel.id,
                                        containerID = (pod.wizardState.container &&
                                                       pod.wizardState.container.id);
                                    if (pod.wizardState.flow === 'EDIT_CONTAINER_GENERAL')
                                        url += '/container/' + containerID + '/general';
                                    else if (pod.wizardState.flow === 'EDIT_CONTAINER_ENV')
                                        url += '/container/' + containerID + '/env';
                                    App.navigate(url, {trigger: true});
                                });
                        });


                        var warnAboutSwitchingAppPackages = function(){
                            if (!pod.editOf().ableTo('switch-package'))
                                return $.Deferred().resolve().promise();
                            var deferred = $.Deferred();
                            utils.modalDialog({
                                title: 'Warning',
                                body: 'If you apply this changes, you won\'t be ' +
                                    'able to switch packages for this application.',
                                small: true,
                                show: true,
                                footer: {
                                    buttonOk: deferred.resolve,
                                    buttonCancel: deferred.reject,
                                    buttonOkText: 'Continue',
                                }
                            });
                            return deferred.promise();
                        };
                        var payAndApply = function(){
                            utils.preloader.show();
                            var originalModel = podCollection.fullCollection.get(pod.editOf()),
                                oldEdited = originalModel.get('edited_config');
                            originalModel.set('edited_config', pod.toJSON()).command('edit')
                                .fail(utils.preloader.hide, utils.notifyWindow,
                                      function(){ originalModel.set('edited_config', oldEdited); })
                                .done(function(){
                                    pod.editOf().cleanup();  // backbone-associations, prevent leak
                                    originalModel.cmdApplyChanges().always(function(){
                                        utils.preloader.hide();
                                        App.navigate('pods/' + originalModel.id, {trigger: true});
                                    }).done(function(){
                                        utils.notifyWindow(
                                            'Pod will be restarted with the ' +
                                            'new configuration soon', 'success');
                                    }).fail(function(){
                                        utils.notifyWindow(
                                            'New configuration saved successfully, ' +
                                            'but it\'s not applied yet', 'success');
                                    });
                                });
                        };
                        that.listenTo(options.layout, 'pod:pay_and_apply', function(){
                            warnAboutSwitchingAppPackages().done(payAndApply);
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
                var pod = options.podModel,
                    state = pod.wizardState;
                state.registryURL = state.registryURL || 'registry.hub.docker.com';
                state.imageCollection = state.imageCollection
                    || new Model.ImageSearchPageableCollection();
                state.selectImageViewModel = state.selectImageViewModel
                    || new Backbone.Model({query: ''});

                var view = new Views.GetImageView({
                    pod: pod, model: state.selectImageViewModel,
                    collection: new Model.ImageSearchCollection(
                        state.imageCollection.fullCollection.models),
                });

                this.listenTo(view, 'image:searchsubmit', function(){
                    view.collection.reset();
                    state.imageCollection.fullCollection.reset();
                    state.imageCollection.getFirstPage({
                        wait: true,
                        data: {searchkey: state.selectImageViewModel.get('query'),
                               url: state.registryURL},
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
                    state.imageCollection.getNextPage({
                        wait: true,
                        data: {searchkey: state.selectImageViewModel.get('query'),
                               url: state.registryURL},
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
                            pod.originalImages.add(image);
                            state.container = containerModel;
                            pod.get('containers').add(containerModel);
                            App.controller.podWizardStepGeneral(options);
                        },
                    }).always(utils.preloader.hide).fail(utils.notifyWindow);
                });

                this.listenTo(view, 'step:complete', this.podWizardStepFinal);
                options.layout.steps.show(view);
            });
        },

        addOriginalImage: function(container){
            utils.preloader.show();
            var deferred = $.Deferred().always(utils.preloader.hide);
            if (container.originalImage)
                return deferred.resolve().promise();

            var pod = container.getPod(),
                image = container.get('image');
            container.originalImage = pod.originalImages.get(image);
            if (container.originalImage)
                return deferred.resolve().promise();

            var podID = pod.editOf() ? pod.editOf().id : pod.id;
            container.originalImage = new Model.Image({image: image});
            container.originalImage.fetch({data: JSON.stringify({image: image, podID: podID})})
                .always(function(){
                    pod.originalImages.add(container.originalImage);
                    deferred.resolve();
                });
            return deferred.promise();
        },

        podWizardStepGeneral: function(options){
            if (!this.checkPermissions(['User', 'TrialUser']))
                return;
            $.when(
                this.podWizardBase(options),
                App.getSystemSettingsCollection(),
                App.getDomainsCollection(),
                App.getIppoolMode()
            ).done(_.bind(function(base, settingsCollection, domainsCollection, ipMode){
                var options = base[0], Views = base[1];
                var containerModel = options.podModel.wizardState.container,
                    billingType = settingsCollection.byName('billing_type').get('value'),
                    payg = App.userPackage.get('count_type') === 'payg',
                    view = new Views.WizardPortsSubView({
                        model: containerModel,
                        hasBilling: billingType.toLowerCase() !== 'no billing',
                        payg: payg,
                        domains: domainsCollection,
                        ipMode: ipMode,
                    });

                this.listenTo(view, 'step:envconf', this.podWizardStepEnv);
                this.listenTo(view, 'step:getimage', this.podWizardStepImage);
                this.listenTo(view, 'step:complete', this.podWizardStepFinal);

                this.addOriginalImage(containerModel).done(function(){
                    options.layout.steps.show(view);
                });
            }, this));
        },

        podWizardStepEnv: function(options){
            if (!this.checkPermissions(['User', 'TrialUser']))
                return;
            this.podWizardBase(options).done(function(options, Views){
                var containerModel = options.podModel.wizardState.container,
                    view = new Views.WizardEnvSubView({model: containerModel});

                this.listenTo(view, 'step:portconf', this.podWizardStepGeneral);
                this.listenTo(view, 'step:complete', this.podWizardStepFinal);

                this.addOriginalImage(containerModel).done(function(){
                    options.layout.steps.show(view);
                });
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
                model.solveKubeTypeConflicts();

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
                                    if (response.data.status === 'Paid'){
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
                                        } else {
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
                        // layoutView.breadcrumbs.show(new Views.Breadcrumbs(
                        //     {model: breadcrumbsModel}));

                        if (tab === 'logs') {
                            // layoutView.sidebar.show(new Views.SideBar(
                            //     {model: sidebarModel, nodeId: nodeId}));
                            layoutView.tabContent.show(
                                new Views.NodeLogsTabView({model: node}));
                        } else if (tab === 'timelines') {
                            // layoutView.sidebar.show(new Views.SideBar(
                            //     {model: sidebarModel, nodeId: nodeId}));
                            layoutView.tabContent.show(
                                new Views.NodeTimelinesTabView({model: node}));
                        } else if (tab === 'monitoring') {
                            var hostname = node.get('hostname'),
                                graphCollection = new Model.NodeStatsCollection(
                                    null, {hostname: hostname});
                            graphCollection.fetch({wait: true})
                                .done(function(){
                                    var view = new Views.NodeMonitoringTabView({
                                        collection: graphCollection,
                                        model: node,
                                    });
                                    layoutView.tabContent.show(view);
                                })
                                .fail(function(xhr){
                                    var view = new Views.NodeMonitoringTabView({
                                        collection: graphCollection,
                                        model: node,
                                        error: xhr.responseJSON && xhr.responseJSON.data,
                                    });
                                    layoutView.tabContent.show(view);
                                });
                        } else {
                            // layoutView.sidebar.show(new Views.SideBar(
                            //     {model: sidebarModel, nodeId: nodeId}));
                            layoutView.tabContent.show(
                                new Views.NodeGeneralTabView({model: node}));
                        }
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
                        var userCollectionView = new Views.UsersListView(
                            {collection: userCollection});
                        layoutView.main.show(userCollectionView);
                        layoutView.pager.show(new Pager.PaginatorView(
                            {view: userCollectionView}));
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
                    $.when(
                        App.getRoles(),
                        App.getPackages(),
                        App.getTimezones()
                    ).done(function(roles, packages, timezones){
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
                    $.when(
                        App.getUserCollection(),
                        App.getRoles(),
                        App.getTimezones()
                    ).done(function(userCollection, roles, timezones){
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
                    breadcrumbsData = {buttonID: 'add_pod', buttonLink: '/#newapp',
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
                            _.clone(context.breadcrumbsData),
                                    {breadcrumbs: [{name: 'Predefined Apps'}]})),
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

                var errorModelSaving = function(context, response) {
                    if (response && !(response.responseJSON &&
                            response.responseJSON.data &&
                            response.responseJSON.type === 'ValidationError')){
                        utils.notifyWindow(response);
                        return;
                    }
                    // TODO: move it in views in AC-3434
                    require([
                        'app_data/papps/templates/validation_error.tpl',
                        'js-yaml'
                    ], function(validationErrorTpl, jsyaml){
                        utils.modalDialog({
                            title: 'Invalid template',
                            body: validationErrorTpl(
                                {data: response.responseJSON.data, jsyaml: jsyaml}),
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

        showSettingsGroup: function(group){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/settings/views'], function(Views){
                var layoutView = new Views.SettingsLayout(),
                    navbar = new Menu.NavList({collection: App.menuCollection});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    App.getSystemSettingsCollection().done(function(settingsCollection){
                        var view = new Views.GeneralView({
                            collection: new Model.SettingsCollection(
                                settingsCollection.filterByGroup(group)
                            )
                        });
                        layoutView.main.show(view);
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showGeneralSettings: function(){ this.showSettingsGroup('general') },
        showDomainSettings: function(){ this.showSettingsGroup('domain') },
        showBillingSettings: function(){ this.showSettingsGroup('billing') },

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
                var layoutView = new Views.IppoolLayoutView(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    breadcrumbsLayout = new Breadcrumbs.Layout({points: ['subnets']});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.breadcrumb.show(breadcrumbsLayout);
                    $.when(App.getIppoolMode(), App.getIPPoolCollection())
                        .done(function(ipPoolMode, ippoolCollection){
                            var view, item, button, breadcrumbsControls;
                            ippoolCollection.ipPoolMode = ipPoolMode;
                            if (ipPoolMode === 'aws') {
                                breadcrumbsControls = new Breadcrumbs.Controls(
                                    {button: {}});
                                layoutView.breadcrumb.show(breadcrumbsLayout);
                                breadcrumbsLayout.subnets.show(
                                    new Breadcrumbs.Text({text: 'DNS names'}));
                                breadcrumbsLayout.controls.show(breadcrumbsControls);
                                item = ippoolCollection.at(0);
                                view = new Views.SubnetIpsListView({
                                    model: item,
                                    collection: item.getIPs().getFiltered(function(m){return true;})
                                });
                            } else {
                                button = {id: 'create_network',
                                          href: '#ippool/create',
                                          title: 'Add subnet'};
                                breadcrumbsControls = new Breadcrumbs.Controls(
                                    {button: button});
                                layoutView.breadcrumb.show(breadcrumbsLayout);
                                breadcrumbsLayout.subnets.show(
                                    new Breadcrumbs.Text({text: 'IP Pool'}));
                                breadcrumbsLayout.controls.show(breadcrumbsControls);
                                view = new Views.SubnetsListView(
                                    {collection: ippoolCollection});
                            }
                            layoutView.main.show(view);
                            layoutView.pager.show(new Pager.PaginatorView({view: view}));
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
                var layoutView = new Views.IppoolLayoutView(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    breadcrumbsLayout = new Breadcrumbs.Layout({points: ['subnets', 'create']});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.breadcrumb.show(breadcrumbsLayout);
                    breadcrumbsLayout.subnets.show(
                        new Breadcrumbs.Link({text: 'IP Pool', href:'#ippool'}));
                    breadcrumbsLayout.create.show(
                        new Breadcrumbs.Text({text: 'Add subnet'}));
                    $.when(
                        App.getIppoolMode(),
                        App.getNodeCollection()
                    ).done(function(ipPoolMode, nodeCollection){
                        var nodelist = _.map(nodeCollection.fullCollection.models,
                            function(model){ return model.get('hostname'); });
                        layoutView.main.show(new Views.IppoolCreateSubnetworkView(
                            {ipPoolMode : ipPoolMode, nodelist : nodelist}));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showSubnetIps: function(id){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/ippool/views'], function(Views){
                var layoutView = new Views.IppoolLayoutView(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    breadcrumbsLayout = new Breadcrumbs.Layout(
                        {points: ['subnets', 'subnetName']});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.breadcrumb.show(breadcrumbsLayout);
                    breadcrumbsLayout.subnets.show(
                        new Breadcrumbs.Link({text: 'IP Pool', href:'#ippool'}));
                    breadcrumbsLayout.subnetName.show(new Breadcrumbs.Text({text: id}));
                    App.getIPPoolCollection().done(function(ippoolCollection){
                        var item = ippoolCollection.get(id),
                            filteredIPs = item.getIPs().getFiltered(function(model){
                                return this.showExcluded || model.get('status') === 'free';
                            }),
                            view = new Views.SubnetIpsListView(
                                {model: item, collection: filteredIPs});
                        layoutView.main.show(view);
                        layoutView.pager.show(new Pager.PaginatorView({view: view}));
                    });
                });
                App.contents.show(layoutView);
            });
        },

        showAddDomain: function(){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/domains/views'], function(Views){
                var layoutView = new Views.DomainsLayoutView(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    breadcrumbsLayout = new Breadcrumbs.Layout({points: ['domains', 'add']});
                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.breadcrumb.show(breadcrumbsLayout);
                    breadcrumbsLayout.domains.show(
                        new Breadcrumbs.Link({text: 'Domains Control', href:'#domains'}));
                    breadcrumbsLayout.add.show(new Breadcrumbs.Text({text: 'Add domain'}));
                    layoutView.main.show(
                        new Views.DomainsAddDomainView()
                    );
                });
                App.contents.show(layoutView);
            });
        },

        showDomains: function(){
            if (!this.checkPermissions(['Admin']))
                return;
            var that = this;
            require(['app_data/domains/views'], function(Views){
                var view,
                    layoutView = new Views.DomainsLayoutView(),
                    navbar = new Menu.NavList({collection: App.menuCollection}),
                    breadcrumbsLayout = new Breadcrumbs.Layout({points: ['domains']}),
                    button = {id: 'add_domain', href: '#domains/add', title: 'Add new domain'},
                    breadcrumbsControls = new Breadcrumbs.Controls({button: button});

                that.listenTo(layoutView, 'show', function(){
                    layoutView.nav.show(navbar);
                    layoutView.breadcrumb.show(breadcrumbsLayout);
                    breadcrumbsLayout.domains.show(
                        new Breadcrumbs.Link({text: 'Domains Control'}));
                    breadcrumbsLayout.controls.show(breadcrumbsControls);
                    App.getDomainsCollection().done(function(domainsCollection){
                        view = new Views.DomainsListView({collection: domainsCollection});
                        layoutView.main.show(view);
                        layoutView.pager.show(new Pager.PaginatorView({view: view}));
                    });
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
                        var notificationView = new Views.MessageList(
                            {collection: notificationCollection});
                        App.message.show(notificationView);
                    }
                });
            });
        },

        attachNotification: function(data){
            require(['app_data/misc/views'], function(Views){
                App.getNotificationCollection().done(function(notificationCollection){
                    notificationCollection.add(data);
                    var notificationView = new Views.MessageList(
                        {collection: notificationCollection});
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
                        var notificationView = new Views.MessageList(
                            {collection: notificationCollection});
                        App.message.show(notificationView);
                    } else {
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
