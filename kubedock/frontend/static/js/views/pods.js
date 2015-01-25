/**
 * This module provides view for displaying data
 */
KubeDock.module('Views', function(Views, App, Backbone, Marionette, $, _){
    
    // this layout view shows the main page: basic pods list
    Views.PodListLayout = Backbone.Marionette.LayoutView.extend({
        template: '#layout-pod-list-template',
        
        initialize: function(){
            var that = this;
            this.listenTo(this.list, 'show', function(view){
                that.listenTo(view, 'pager:clear', that.clearPager);
            });
        },
        
        clearPager: function(){
            this.trigger('pager:clear');
        },
        
        regions: {
            masthead: '#masthead-title',
            list: '#layout-list',
            pager: '#layout-footer'
        }
    });
    
    // View for showing a single pod item as a row in pods list
    Views.PodListItem = Backbone.Marionette.ItemView.extend({
        template: '#pod-list-item-template',
        tagName: 'tr',
        className: 'pod-item',
        
        ui: {
            reditable: '.reditable'
        },

        onRender: function(){
            var that = this;
            this.ui.reditable.editable({
                type: 'text',
                title: 'Change replicas number',
                success: function(response, newValue) {
                    that.model.set({'command': 'resize', 'replicas': newValue});
                    that.model.save();
                }
            });
        },

        events: {
            'click .start-btn': 'startItem',
            'click .stop-btn': 'stopItem',
            'click .terminate-btn': 'terminateItem'
        },

        startItem: function(evt){
            evt.stopPropagation();
            this.model.set({'command': 'start'});
            this.model.save();
            },

        stopItem: function(evt){
            evt.stopPropagation();
            this.model.set({'command': 'stop'});
            this.model.save();
            },
        
        terminateItem: function(evt){
            evt.stopPropagation();
            var that = this,
                name = this.model.get('name');
            this.model.destroy({
                wait: true,
                success: function(){
                    that.remove();
                },
                error: function(){
                    console.log('Could not remove '+name);
                }
            });
        }
    });
    
    Views.PodCollection = Backbone.Marionette.CompositeView.extend({
        childView: Views.PodListItem,
        tagName: 'div',
        className: 'row',
        childViewContainer: 'tbody',
        template: '#pod-list-template',
        
        onBeforeDestroy: function(){
            this.trigger('pager:clear');
        }
    });
    
    
    // this layout view shows details a pod details page
    Views.PodItemLayout = Backbone.Marionette.LayoutView.extend({
        template: '#layout-pod-item-template',
        
        regions: {
            masthead: '#masthead-title',
            controls: '#item-controls',
            info: '#item-info',
            aside: '#layout-aside',
            contents: '#layout-contents'
        },
        
        initialize: function(){
            var that = this;
            this.listenTo(this.info, 'show', function(view){
                that.listenTo(view, 'display:pod:stats', that.showPodStats);
            });
        },
        
        showPodStats: function(data){
             this.trigger('display:pod:stats', data.model)
         }
    });
    
    Views.PageHeader = Backbone.Marionette.ItemView.extend({
        template: '#page-header-title-template'
    });
    
    Views.InfoPanel = Backbone.Marionette.ItemView.extend({
        template: '#page-info-panel-template',
        tagName: 'div',
        className: 'row',
        
        triggers: {
            'click .stats': 'display:pod:stats'
        }
    });
    
    Views.ControlsPanel = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-controls-template',
        tagName: 'div',
        className: 'pod-controls',

        events: {
            'click .start-btn': 'startItem',
            'click .stop-btn': 'stopItem',
            'click .terminate-btn': 'terminateItem'
        },

        getItem: function(){
            return initPodCollection.fullCollection.get(this.model.id);
            },

        startItem: function(evt){
            evt.stopPropagation();
            var item = this.getItem();
            item.set({'command': 'start'});
            item.save();
            },

        stopItem: function(evt){
            evt.stopPropagation();
            var item = this.getItem();
            item.set({'command': 'stop'});
            item.save();
            },

        terminateItem: function(evt){
            evt.stopPropagation();
            var item = this.getItem(),
                name = item.get('name');
            item.destroy({
                wait: true,
                success: function(){
                    initPodCollection.remove(item);
                    window.location.href = '/#pods';
                },
                error: function(){
                    console.log('Could not remove '+name);
                }
            });
        }
    });

    Views.PodGraph = Backbone.Marionette.CollectionView.extend({
        childView: Views.PodGraphItem
    });
    
    Views.PodGraphItem = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-graph-template'
    });
    
    Views.PodItemMain = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-main-template'
    });
    
    Views.PodItemContainer = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-container-template'
    });
    
    // View for display pod and its containers in the whole
    Views.PodItem = Backbone.Marionette.CollectionView.extend({
        childView: Views.PodItemContainer
    });
    
    // Layout view for wizard
    Views.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: '#layout-wizard-template',
        initialize: function(){
            var that = this;
            this.listenTo(this.steps, 'show', function(view){
                that.listenTo(view, 'step:getimage', that.getImage);
                that.listenTo(view, 'image:selected', that.imageSelected);
                that.listenTo(view, 'step:portconf', that.portConf);
                that.listenTo(view, 'step:volconf', that.volConf);
                that.listenTo(view, 'step:envconf', that.envConf);
                that.listenTo(view, 'step:resconf', that.resConf);
                that.listenTo(view, 'step:otherconf', that.otherConf);
                that.listenTo(view, 'step:complete', that.completeConf);
                that.listenTo(view, 'image:fetched', that.imageFetched);
                that.listenTo(view, 'pager:clear', that.clearPager);
                that.listenTo(view, 'pod:save', that.podSave);
                that.listenTo(view, 'pod:run', that.podRun);
            });
        },
        regions: {
            header: '#header-steps',
            steps: '#steps',
            sidebar: '#sidebar',
            footer: '#footer-steps'
        },
        getImage: function(data){
            this.trigger('step:getimage', data);
        },
        imageSelected: function(data){
            this.trigger('image:selected', data);
        },
        portConf: function(data){
            this.trigger('step:portconf', data.model);
        },
        volConf: function(data){
            this.trigger('step:volconf', data.model);
        },
        envConf: function(data){
            this.trigger('step:envconf', data.model);
        },
        resConf: function(data){
            this.trigger('step:resconf', data.model);
        },
        otherConf: function(data){
            this.trigger('step:otherconf', data.model);
        },
        completeConf: function(data){
            this.trigger('step:complete', data.model);
        },
        imageFetched: function(data){
            this.trigger('image:fetched', data);
        },
        clearPager: function(){
            this.trigger('clear:pager');
        },
        podSave: function(data){
            this.trigger('pod:save', data.model);
        },
        podRun: function(data){
            this.trigger('pod:run', data.model);
        }
    });
    
    
    
    Views.PodHeaderView = Backbone.Marionette.ItemView.extend({
        template: _.template('<h2 class="peditable"><%- name %></h2>'),
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',
        
        initialize: function(options){
            this.model = options.model;
        },
        
        ui: {
            peditable: '.peditable'
        },
        
        onRender: function(){
            var that = this;
            this.ui.peditable.editable({
                type: 'text',
                title: 'Change container name',
                success: function(response, newValue) {
                    that.model.set({name: newValue});
                }
            });
        }
    });
    
    // Images collection item view
    Views.ImageListItemView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-image-collection-item-template',
        tagName: 'div',
        className: 'item',
        
        events: {
            'click .add-item': 'addItem'
        },
        
        addItem: function(evt){
            evt.stopPropagation();
            this.trigger('image:selected');
        }
    });
    
    // Images collection view
    Views.GetImageView = Backbone.Marionette.CompositeView.extend({
        template: '#wizard-get-image-template',
        childView: Views.ImageListItemView,
        childViewContainer: '#data-collection',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',
        
        initialize: function(options){
            this.collection = new App.Data.ImageCollection();
            this.listenTo(this.collection, 'reset', this.render);
        },
        
        triggers: {
            'click .next-step' : 'step:next'
        },
        
        events: {
            'click .search-image': 'onSearchClick',
            'keypress #search-image-field': 'onInputKeypress'
        },
        
        childEvents: {
            'image:selected': 'childImageSelected'
        },
        
        ui: {
            input: 'input#search-image-field',
            spinner: '#data-collection'
        },
        
        onInputKeypress: function(evt){
            evt.stopPropagation();
            if (evt.which === 13) { // 'Enter' key
                this.fetchCollection(this.ui.input.val().trim());
            }
        },
        
        onSearchClick: function(evt){
            evt.stopPropagation();
            this.fetchCollection(this.ui.input.val().trim());
        },
        
        fetchCollection: function(query){
            var that = this;
            this.ui.spinner.spin({color: '#437A9E'});
            this.collection.fetch({
                data: {searchkey: query},
                reset: true,
                success: function(){
                    that.ui.spinner.spin(false);
                    that.trigger('image:fetched', that);
                }
            });
        },
        
        onShow: function(){
            this.ui.input.focus();
        },

        onBeforeDestroy: function(){
            this.trigger('pager:clear');
        },
        
        childImageSelected: function(data){
            this.trigger('image:selected', data.model.get('name'));
        }
    });
    
    Views.LoadingView = Backbone.Marionette.ItemView.extend({
        template: _.template('<div id="spinner"></div>'),
        ui: {
            spinner: '#spinner'
        },
        onRender: function(){
            this.ui.spinner.spin({color: '#437A9E'});
        }
    });
    
    Views.WizardPortsSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-ports-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',
        
        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },
        
        initialize: function(options){
            try {
                var image = options.model.get('lastAddedImage');
                this.model = new App.Data.Image(options.model.getContainerByImage(image));
            }
            catch(e){
                if (e.constructor === TypeError) {
                    this.model = options.model
                }
            }
        },
        
        ui: {
            ieditable: '.ieditable',
            iseditable: '.iseditable'
        },
        
        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:volconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-resources': 'step:resconf',
            'click .go-to-other': 'step:otherconf',
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var index = $(this).closest('tr').index(),
                        item = $(this).parent().attr('class');
                    that.model.get('ports')[index][item] = newValue;
                }
            });
            this.ui.iseditable.editable({
                type: 'select',
                value: 'tcp',
                source: [{value: 'tcp', text: 'tcp'}, {value: 'udp', text: 'udp'}],
                mode: 'inline',
                success: function(response, newValue) {
                    var index = $(this).closest('tr').index();
                    that.model.get('ports')[index]['protocol'] = newValue;
                }
            });
        }
    });
    
    Views.WizardVolumesSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-volumes-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',
        
        ui: {
            ieditable: '.ieditable'
        },
        
        events: {
            'click .readonly': 'toggleReadOnly'
        },
        
        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },
        
        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:envconf',
            'click .prev-step' : 'step:portconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-resources': 'step:resconf',
            'click .go-to-other': 'step:otherconf',
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var index = $(this).closest('tr').index();
                    that.model.get('volumeMounts')[index]['name'] = newValue;
                }
            });
        },
        toggleReadOnly: function(evt){
            evt.stopPropagation();
            index = $(evt.target).closest('tr').index()
            var on = this.model.get('volumeMounts')[index]['readOnly'];
            if (on) {
                this.model.get('volumeMounts')[index]['readOnly'] = false;
            }
            else {
                this.model.get('volumeMounts')[index]['readOnly'] = true;
            }
            this.render();
        }
    });
    
    Views.WizardEnvSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-env-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',
        
        ui: {
            ieditable: '.ieditable',
            table: '#data-table',
        },
        
        events: {
            'click .add-env': 'addItem',
        },
        
        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },
        
        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:resconf',
            'click .prev-step' : 'step:volconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-resources': 'step:resconf',
            'click .go-to-other': 'step:otherconf',
        },
        
        addItem: function(env){
            env.stopPropagation();
            this.model.get('env').push({name: null, value: null});
            this.render();
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var item = $(this);
                    index = item.closest('tr').index();
                    if (item.hasClass('name')) {
                        that.model.get('env')[index]['name'] = newValue;
                    }
                    else if (item.hasClass('value')) {
                        that.model.get('env')[index]['value'] = newValue;
                    }
                }
            });
        }
    });
    
    Views.WizardResSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-resources-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        ui: {
            ieditable: '.ieditable'
        },
        
        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:otherconf',
            'click .prev-step' : 'step:envconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-other': 'step:otherconf',
        },
        
        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    if ($(this).hasClass('cpu')) {
                        that.model.set('cpu', parseInt(newValue));
                    }
                    else if ($(this).hasClass('memory')) {
                        that.model.set('memory', parseInt(newValue));
                    }
                }
            });
        }
        
    });
    
    Views.WizardOtherSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-other-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        ui: {
            ieditable: '.ieditable'
        },
        
        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },
        
        triggers: {
            'click .complete' : 'step:complete',
            'click .prev-step' : 'step:resconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-resources': 'step:resconf',
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    if ($(this).hasClass('working-dir')) {
                        that.model.set('workingDir', newValue);
                    }
                    else if ($(this).hasClass('command')) {
                        that.model.set('command', newValue.split(' '));
                    }
                }
            });
        }
    });
    
    Views.WizardCompleteSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-complete-template',
        tagName: 'div',
        className: 'row',
        
        ui: {
            ieditable: '.ieditable'
        },
        
        events: {
            'click .delete-item': 'deleteItem',
            'click .cluster': 'toggleCluster',
            'change .replicas': 'changeReplicas'
        },
        
        triggers: {
            'click .add-more' : 'step:getimage',
            'click .prev-step' : 'step:envconf',
            'click .save-container': 'pod:save',
            'click .save-run-container': 'pod:run'
        },
        
        deleteItem: function(evt){
            evt.stopPropagation();
            var image = $(evt.target).closest('tr').children('td:first').text().trim();
            this.model.attributes.containers = _.filter(this.model.get('containers'),
            function(i){ return i.image !== this.image }, {image: image});
            this.render();
        },
        
        toggleCluster: function(evt){
            evt.stopPropagation();
            if (this.model.get('cluster')) {
                this.model.set('cluster', false);
            }
            else {
                if (this.model.get('port') === null) {
                    var containers = this.model.get('containers'),
                        port = containers[0]['ports'][0]['containerPort'],
                        obj = {cluster: true, port: port, service: true};
                }
                else {
                    var obj = {cluster: true};
                }
                this.model.set(obj);
            }
            this.render();
        },
        
        changeReplicas: function(evt){
            evt.stopPropagation();
            this.model.set('replicas', parseInt($(evt.target).val().trim()));
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                inputclass: 'shortfield',
                success: function(response, newValue) {
                    var item = $(this);
                    if (item.hasClass('volume')) {
                        var index = item.closest('tr').index();
                        that.model.get('volumes')[index]['source'] = {hostDir: {path: newValue}};
                    }
                    else if (item.hasClass('port')) {
                        that.model.set('port', newValue);
                    }
                    else {
                        console.log('oops!');
                    }
                }
            });
        }
    });
    
    Views.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: '#paginator-template',
        
        initialize: function(options) {
            this.model = new Backbone.Model({
                v: options.view,
                c: options.view.collection
            });
        },
        
        events: {
            'click li.pseudo-link': 'paginateIt'
        },
        
        paginateIt: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target);
            if (tgt.hasClass('paginatorFirst')) this.model.get('c').getFirstPage();
            else if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
            else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
            else if (tgt.hasClass('paginatorLast')) this.model.get('c').getLastPage();
            this.model.get('v').render();
            this.render();
        }
    });
});