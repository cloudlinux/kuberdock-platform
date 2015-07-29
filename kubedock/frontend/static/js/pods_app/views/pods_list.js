define(['pods_app/app',
        'tpl!pods_app/templates/layout_pod_list.tpl',
        'tpl!pods_app/templates/pod_list_item.tpl',
        'tpl!pods_app/templates/pod_list.tpl',
        'pods_app/utils',
        'bootstrap', 'bootstrap-editable'],
       function(Pods, layoutPodListTpl, podListItemTpl, podListTpl, utils){

    Pods.module('Views.List', function(List, App, Backbone, Marionette, $, _){

        List.PodListLayout = Backbone.Marionette.LayoutView.extend({
            template: layoutPodListTpl,

            initialize: function(){
                var that = this;
                this.listenTo(this.list, 'show', function(view){
                    that.listenTo(view, 'pager:clear', that.clearPager);
                });
                this.countChecked = 0;
            },

            clearPager: function(){
                this.trigger('pager:clear');
            },

            regions: {
                list: '#layout-list',
                pager: '#layout-footer'
            },

            ui: {
                'checkAll'   : 'thead label.custom span',
                'removePods' : '.removePods'
            },

            events: {
                'click @ui.checkAll'   : 'checkAll',
                'click @ui.removePods' : 'removePods'
            },

            childEvents: {
                render: function(childView) {
                    var items = App.WorkFlow.getCollection().fullCollection.models,
                        countChecked = 0,
                        thead = this.$('thead'),
                        count = this.$('.count'),
                        podsControl = this.$('.podsControl');

                    _.each(items, function(obj, index){
                        obj.is_checked ? countChecked++ : false
                    });

                    if (countChecked > 0){
                        thead.addClass('min-opacity');
                        podsControl.show();
                    } else {
                        thead.removeClass('min-opacity');
                        podsControl.hide();
                    }

                    countChecked < 2 ? count.text(countChecked +' Item') : count.text(countChecked + ' Items');
                }
            },

            checkAll: function(){
                this.trigger('pods:check');
            },

            removePods: function(){
               var items = App.WorkFlow.getCollection().fullCollection.models;

               utils.modalDialogDelete({
                    title: "Delete",
                    body: "Are you sure want to delete selected pods?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            _.each(items, function(item){
                                if (item.is_checked){
                                    item.destroy();
                                }
                            });
                        },
                        buttonCancel: true
                   }
                });
            },
        });

        // View for showing a single pod item as a container in pods list
        List.PodListItem = Backbone.Marionette.ItemView.extend({
            template    : podListItemTpl,
            tagName     : 'tr',
            className   : function(){
                return this.model.is_checked ? 'pod-item checked' : 'pod-item';
            },

            templateHelpers: function(){
                var kubes = _.reduce(this.model.get('containers'), function(memo, c) {
                    return memo + c.kubes
                }, 0);
                var modelIndex = this.model.collection.indexOf(this.model);

                return {
                    index: modelIndex + 1,
                    kubes: kubes
                }
            },

            ui: {
                reditable  : '.reditable',
                start      : '.start-btn',
                stop       : '.stop-btn',
                terminate  : '.terminate-btn',
                checkbox   : 'label.custom span',
                podPageBtn : '.poditem-page-btn'
            },

            events: {
                'click @ui.start'      : 'startItem',
                'click @ui.stop'       : 'stopItem',
                'click @ui.terminate'  : 'terminateItem',
                'click @ui.podPageBtn' : 'podPage',
                'click'                : 'checkItem',
            },

            onRender: function(){
                var that = this;
                var status = this.model.get('status');
                this.ui.reditable.editable({
                    type: 'text',
                    title: 'Change replicas number',
                    success: function(response, newValue) {
                        that.model.set({
                            'command'   : 'resize',
                            'replicas'  : parseInt(newValue.trim())
                        });
                        that.model.save();
                    }
                });
            },

            podPage: function(evt){
                App.navigate('pods/' + this.model.get('id'), {trigger: true});
                evt.stopPropagation();
            },

            startItem: function(evt){
                var that = this,
                    preloader = $('#page-preloader');
                preloader.show();
                evt.stopPropagation();
                this.model.save({command: 'start'}, {
                    wait: true,
                    success: function(model, response, options){
                        that.render();
                        preloader.hide();
                    },
                    error: function(model, response, options, data){
                        that.render();
                        preloader.hide();
                        utils.modelError(response);
                    }
                });
            },

            stopItem: function(evt){
                var that = this,
                    preloader = $('#page-preloader');
                preloader.show();
                evt.stopPropagation();
                this.model.save({command: 'stop'}, {
                    wait: true,
                    success: function(model, response, options){
                        that.render();
                        preloader.hide();
                    },
                    error: function(model, response, options, data){
                        that.render();
                        preloader.hide();
                        utils.modelError(response);
                    }
                });
            },

            terminateItem: function(evt){
                var that = this,
                    name = this.model.get('name'),
                    preloader = $('#page-preloader');
                    preloader.show();
                this.model.destroy({
                    wait: true,
                    success: function(){
                        that.remove();
                        preloader.hide();
                    },
                   error: function(model, response, options, data){
                        that.render();
                        preloader.hide();
                        utils.modelError(response);
                    }
                });
                evt.stopPropagation();
            },

            checkItem: function(evt){
                if (this.model.is_checked){
                    this.$el.removeClass('checked');
                    this.model.is_checked = false;
                } else {
                    this.model.is_checked = true;
                    this.$el.addClass('checked');
                }
                this.render();
            }
        });

        List.PodCollection = Backbone.Marionette.CompositeView.extend({
            template            : podListTpl,
            childView: List.PodListItem,
            tagName             : 'div',
            childViewContainer  : 'tbody',

            ui: {
                'node_search' : 'input#nav-search-input'
            },

            events: {
                'keyup @ui.node_search' : 'filterCollection'
            },

            initialize: function() {
                this.fakeCollection = this.collection.fullCollection.clone();

                this.listenTo(this.collection, 'reset', function (col, options) {
                    options = _.extend({ reindex: true }, options || {});
                    if(options.reindex && options.from == null && options.to == null) {
                        this.fakeCollection.reset(col.models);
                    }
                });
            },

            filterCollection: function(){
                var value = this.ui.node_search[0].value,
                    valueLength = value.length;

                if (valueLength >= 2){
                    this.collection.fullCollection.reset(_.filter(this.fakeCollection.models, function(e) {
                        if(e.get('name').indexOf( value || '') >= 0) return e
                    }), { reindex: false });
                } else{
                    this.collection.fullCollection.reset(this.fakeCollection.models, { reindex: false});
                }
                this.collection.getFirstPage();
            },

            onBeforeDestroy: function(){
                this.trigger('pager:clear');
            }
        });
    });

    return Pods.Views.List;
});
