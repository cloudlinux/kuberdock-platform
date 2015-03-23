function modalDialog(options){
    var modal = $('.modal');
    if(options.title) modal.find('.modal-title').html(options.title);
    if(options.body) modal.find('.modal-body').html(options.body);
    if(options.large) modal.addClass('bs-example-modal-lg');
    if(options.small) modal.addClass('bs-example-modal-sm');
    if(options.show) modal.modal('show');
    return modal;
}

KubeDock.module('WorkFlow', function(WorkFlow, App, Backbone, Marionette, $, _){
    
    var routes;
    WorkFlow.routes = function(r){
        if (r !== undefined) {
            routes = r;
            return true;
        }
        return routes;
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
            var listLayout = new App.Views.PodListLayout();
                      
            var podCollection = new App.Views.PodCollection({
                collection: initPodCollection
            });
            
            this.listenTo(listLayout, 'show', function(){
                listLayout.list.show(podCollection);
                listLayout.pager.show(new App.Views.PaginatorView({view: podCollection}));
            });
            this.listenTo(listLayout, 'clear:pager', function(){
                listLayout.pager.empty();
            });
            App.contents.show(listLayout);
        },
        
        showPodItem: function(id){
            var itemLayout = new App.Views.PodItemLayout(),
                model = initPodCollection.fullCollection.get(id);
            _.each(model.get('containers'), function(i){
                    i.parentID = this.parentID;
                    i.kubes = this.kubes;
                }, {parentID: id, kubes: model.get('kubes')});
            var _containerCollection = model.get('containers');
            var newContainerCollection = [];
            _.each(model.get('dockers'), function(el){
                var container = {};
                _.each(_containerCollection, function(c){
                    if(c.imageID == el.info.imageID){
                        $.each(c, function(k, v){
                            container[k] = v;
                        });

                        container['info'] = el.info;
                        $.each(container.info.state, function(k, v){
                            container['state_repr'] = k;
                            container['startedAt'] = v.startedAt;
                        });
                    }
                });
                newContainerCollection.push(container);
            });
            containerCollection = new Backbone.Collection(newContainerCollection);

            var masthead = new App.Views.PageHeader({
                model: new Backbone.Model({name: model.get('name')})
            });
            
            var controlsPanel = new App.Views.ControlsPanel({
                model: new Backbone.Model({id: model.get('id')})
            });

            var infoPanel = new App.Views.InfoPanel({
                childView: App.Views.InfoPanelItem,
                childViewContainer: "tbody",
                collection: containerCollection
            });
            
            this.listenTo(itemLayout, 'display:pod:stats', function(data){
                var statCollection = new App.Data.StatsCollection(),
                    that = this;
                statCollection.fetch({
                    data: {unit: data.get('id')},
                    reset: true,
                    success: function(){
                        itemLayout.contents.show(new App.Views.PodGraph({
                            collection: statCollection
                        }));
                    },
                    error: function(){
                        console.log('failed to fetch graphs');
                    }
                })
            });
            
            this.listenTo(itemLayout, 'show', function(){
                itemLayout.masthead.show(masthead);
                itemLayout.controls.show(controlsPanel);
                itemLayout.info.show(infoPanel);
            });
            App.contents.show(itemLayout);
        },
        
        showPodContainer: function(id, name){
            wizardLayout = new App.Views.PodWizardLayout(),
                parent_model = initPodCollection.fullCollection.get(id),
                model_data = _.filter(
                    parent_model.get('containers'),
                    function(i){return i.name === this.n},
                    {n: name}
                )[0],
                container_id = _.last(_.filter(
                    parent_model.get('dockers'),
                    function(i){return i.info.imageID === this.d},
                    {d: model_data.imageID}
                )[0].info.containerID.split('/')),
                model_data.container_id = container_id,
                model_data.node = parent_model.get('dockers')[0].host;
            if (!model_data.hasOwnProperty('kubes')) model_data['kubes'] = 1;
            if (!model_data.hasOwnProperty('workingDir')) model_data['workingDir'] = undefined;
            if (!model_data.hasOwnProperty('command')) model_data['command'] = [];
            if (!model_data.hasOwnProperty('env')) model_data['env'] = [];
            if (!model_data.hasOwnProperty('parentID')) model_data['parentID'] = id;
            
            this.listenTo(wizardLayout, 'show', function(){
                wizardLayout.steps.show(new App.Views.WizardPortsSubView({
                    model: new App.Data.Image(model_data)
                }));
            });
            this.listenTo(wizardLayout, 'step:portconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardPortsSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:volconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardVolumesSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:envconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardEnvSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:resconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardResSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:otherconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardOtherSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:logsconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardLogsSubView({model: data}));
            });
            App.contents.show(wizardLayout);
        },
        
        createPod: function(){
            var model = new App.Data.Pod({name: "Unnamed 1", containers: [], volumes: []}),
                wizardLayout = new App.Views.PodWizardLayout(),
                that = this;
            
            var processRequest = function(data){
                if($('#set_public_ip').is(':checked'))
                    data.set('set_public_ip', '1');
                _.each(data.get('containers'), function(item){
                    item.volumeMounts = _.filter(item.volumeMounts, function(mp){
                        return mp['name'] !== null;
                    });
                });
                initPodCollection.fullCollection.create(data, {
                    success: function(){
                        routes.navigate('pods');
                        that.showPods();
                    },
                    error: function(model, response, options, data){
                        modalDialog({
                            title: 'Error',
                            body: response.responseJSON ? response.responseJSON.status : response.responseText,
                            show: true
                        });
                    }
                });
            };
            
            this.listenTo(wizardLayout, 'show', function(){
                wizardLayout.header.show(new App.Views.PodHeaderView({model: model}));
                wizardLayout.steps.show(new App.Views.GetImageView());
            });
            this.listenTo(wizardLayout, 'image:fetched', function(data){
                wizardLayout.footer.show(new App.Views.PaginatorView({view: data}));
            });
            this.listenTo(wizardLayout, 'clear:pager', function(){
                wizardLayout.footer.empty();
            });
            this.listenTo(wizardLayout, 'step:getimage', function(data){
                wizardLayout.steps.show(new App.Views.GetImageView());
            });
            this.listenTo(wizardLayout, 'step:portconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardPortsSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:volconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardVolumesSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:envconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardEnvSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:resconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardResSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'step:otherconf', function(data){
                wizardLayout.steps.show(new App.Views.WizardOtherSubView({model: data}));
            });
            this.listenTo(wizardLayout, 'pod:save', function(data){
                data.set({'save_only': true}, {silent: true});
                processRequest(data);
            });
            this.listenTo(wizardLayout, 'pod:run', function(data){
                data.set({'save_only': false}, {silent: true});
                processRequest(data);
            });
            this.listenTo(wizardLayout, 'step:complete', function(data){
                console.log(data);
                if(data.get('ports').length == 0){
                    modelError('Please, setup ports of container.');
                    wizardLayout.steps.show(new App.Views.WizardPortsSubView({model: data}));
                    return false;
                }
                _.each(data.get('volumeMounts'), function(mp){
                    if (mp['name'] !== null) {
                        var volumes = _.filter(model.get('volumes'), function(item){
                            return item['name'] === mp['name'];
                        });
                        if (!volumes.length) {
                            model.get('volumes').push({name: mp['name']});
                        }
                    }
                });
                var container = model.getContainerByImage(model.get('lastAddedImage'));
                _.each(data.attributes, function(value, key, obj){
                    this.container[key] = value;
                }, {container: container});
                var rqst = $.ajax({
                    type: 'GET',
                    url: '/api/nodes'
                });
                rqst.done(function(data){
                    if (data.hasOwnProperty('data')) { data = data['data']; }
                    $.ajax({
                        url: '/api/ippool/getFreeHost',
                        success: function(rs){
                            model.set({free_host: rs.data});
                            wizardLayout.steps.show(new App.Views.WizardCompleteSubView({
                                nodes: data, model: model, freeHost: rs.data}));
                        }
                    })
                });
                //wizardLayout.steps.show(new App.Views.WizardCompleteSubView({nodes: nodes, model: model}));
            });
            this.listenTo(wizardLayout, 'image:selected', function(image){
                var that = this,
                    slash = image.indexOf('/'),
                    name = (slash >= 0) ? image.substring(slash+1) : image,
                    rqst = $.ajax({
                        type: 'POST',
                        url: '/api/images/new',
                        data: {image: image}
                    });
                name += _.map(_.range(10), function(i){return _.random(1, 10);}).join('');
                model.get('containers').push({
                    image: image, name: name, workingDir: null,
                    ports: [], volumeMounts: [], env: [], command: [], kubes: 1,
                    terminationMessagePath: null
                });
                model.set('lastAddedImage', image);
                rqst.done(function(data){
                    if (data.hasOwnProperty('data')) { data = data['data']; }
                    var container = model.getContainerByImage(image);
                    model.fillContainer(container, data);
                    wizardLayout.steps.show(new App.Views.WizardPortsSubView({model: model}));
                });
                wizardLayout.steps.show(new App.Views.LoadingView());
            });
            App.contents.show(wizardLayout);
        }
    });
    
    WorkFlow.addInitializer(function(){
        var controller = new WorkFlow.Controller();
        var routes = new WorkFlow.Router({
            controller: controller
        });
        WorkFlow.routes(routes);
        controller.showPods();
        if (typeof(EventSource) === undefined) {
            console.log('ERROR: EventSource is not supported by browser');
        } else {
            var source = new EventSource("/api/stream");
            source.addEventListener('pull_pods_state', function (ev) {
                initPodCollection.fetch();
            }, false);
        }
    });
});
