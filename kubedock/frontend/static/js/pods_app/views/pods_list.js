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
            },

            clearPager: function(){
                this.trigger('pager:clear');
            },

            regions: {
                list: '#layout-list',
                pager: '#layout-footer'
            },

            ui: {
                'checkAll' : 'thead label.custom span'
            },

            events: {
                'click @ui.checkAll' : 'checkAll',
            },

            checkAll: function(e){
                var items = App.WorkFlow.getCollection().fullCollection.models,
                    that = this,
                    input = this.$el.find('thead input');

                _.each(items, function(model){
                    var status = model.get('checked');
                    if (!input.is(':checked')){
                        model.set('checked',true);
                        that.$el.find('tbody tr').addClass('checked');
                    } else {
                        model.set('checked',false);
                        that.$el.find('tbody tr').removeClass('checked');
                    }
                })
            }
        });

        // View for showing a single pod item as a container in pods list
        List.PodListItem = Backbone.Marionette.ItemView.extend({
            template    : podListItemTpl,
            tagName     : 'tr',
            className   : function(){
                return this.model.get('checked') ? 'pod-item checked' : 'pod-item';
            },

            templateHelpers: function(){
                var kubes = this.model.get('kubes');
                var modelIndex = this.model.collection.indexOf(this.model);

                return {
                    index: modelIndex + 1,
                    kubes: kubes ? kubes : 0
                }
            },

            ui: {
                reditable   : '.reditable',
                start       : '.start-btn',
                stop        : '.stop-btn',
                terminate   : '.terminate-btn',
                checkbox    : 'label.custom span',
            },

            events: {
                'click @ui.start'      : 'startItem',
                'click @ui.stop'       : 'stopItem',
                'click @ui.terminate'  : 'terminateItem',
                'click @ui.checkbox'   : 'checkItem'
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

            startItem: function(evt){
                var that = this,
                    preloader = $('#page-preloader');
                preloader.show();
                evt.stopPropagation();
                this.model.clearModel();
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
                this.model.clearModel();
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
                this.model.set('checked', !this.model.get('checked'));
                this.$el.toggleClass('checked');
                this.render();
            }
        });

        List.PodCollection = Backbone.Marionette.CompositeView.extend({
            childView: List.PodListItem,
            tagName             : 'div',
            childViewContainer  : 'tbody',
            template            : podListTpl,

            onBeforeDestroy: function(){
                this.trigger('pager:clear');
            }
        });

    });

    return Pods.Views.List;

});