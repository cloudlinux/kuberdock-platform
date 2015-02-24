KubeDock.module('WorkFlow', function(WorkFlow, App, Backbone, Marionette, $, _){
    
    var routes;
    WorkFlow.routes = function(r){
        if (r !== undefined) {
            routes = r;
            return true;
        }
        return routes;
    }
    WorkFlow.Router = Marionette.AppRouter.extend({
        appRoutes: {
            'pods': 'showPods',
            'pods/:id': 'showPodItem',
            'newpod': 'createPod',
            'poditem/:id/:name': 'showPodContainer',
        }
    });
    
    WorkFlow.Controller = Marionette.Controller.extend({
        
        showPods: function(){
            var listLayout = new App.Views.PodListLayout();
            
            var masthead = new App.Views.PageHeader({
                model: new Backbone.Model({name: 'Pods'})
            });
            
            var podCollection = new App.Views.PodCollection({
                collection: initPodCollection
            });
            
            this.listenTo(listLayout, 'show', function(){
                listLayout.masthead.show(masthead);
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
                    i.parentID = this.parentID
                }, {parentID: id});
            var containers = new Backbone.Collection(model.get('containers'));

            var masthead = new App.Views.PageHeader({
                model: new Backbone.Model({name: model.get('name')})
            });
            
            var controlsPanel = new App.Views.ControlsPanel({
                model: new Backbone.Model({id: model.get('id')})
            });

            var infoPanel = new App.Views.InfoPanel({
                model: new Backbone.Model({status: model.get('status'), id: model.get('id')})
            });
            
            var itemView = new App.Views.PodItem({
                collection: containers,
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
                itemLayout.contents.show(itemView);
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
                )[0];
                
            if (!model_data.hasOwnProperty('cpu')) model_data['cpu'] = 0;
            if (!model_data.hasOwnProperty('memory')) model_data['memory'] = 0;
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
            App.contents.show(wizardLayout);
        },
        
        createPod: function(){
            var model = new App.Data.Pod({name: "Unnamed 1", containers: [], volumes: []}),
                wizardLayout = new App.Views.PodWizardLayout(),
                that = this;
            
            var processRequest = function(data){
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
                    error: function(){
                        console.log('failed to save pod')
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
                wizardLayout.steps.show(new App.Views.WizardCompleteSubView({model: model}));
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
                    image: image, name: name, cpu: 0, memory: 0, workingDir: null,
                    ports: [], volumeMounts: [], env: [], command: [],
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