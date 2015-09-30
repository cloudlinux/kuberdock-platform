define(['pods_app/app',
        'tpl!pods_app/templates/layout_pod_list.tpl',
        'tpl!pods_app/templates/pod_list_item.tpl',
        'tpl!pods_app/templates/pod_list.tpl',
        'pods_app/utils',
        'bootstrap'],
       function(Pods, layoutPodListTpl, podListItemTpl, podListTpl, utils){

    Pods.module('Views.List', function(List, App, Backbone, Marionette, $, _){

        List.PodListLayout = Backbone.Marionette.LayoutView.extend({
            template: layoutPodListTpl,

            initialize: function(){
                var that = this;
                this.listenTo(this.list, 'show', function(view){
                    that.listenTo(view, 'pager:clear', that.clearPager);

                });
                this.listenTo(this.header, 'show', function(view){
                    that.listenTo(view, 'collection:filter', that.collectionFilter);
                });
            },

            clearPager: function(){
                this.trigger('pager:clear');
            },

            collectionFilter: function(data){
                this.trigger('collection:filter', data);
            },

            regions: {
                header: '#layout-header',
                list: '#layout-list',
                pager: '#layout-footer'
            },
        });

        // View for showing a single pod item as a container in pods list
        List.PodListItem = Backbone.Marionette.ItemView.extend({
            template    : podListItemTpl,
            tagName     : 'tr',
            className   : function(){
                return this.model.is_checked ? 'pod-item checked' : 'pod-item';
            },

            initialize: function(options){
                this.index = options.childIndex;
            },

            templateHelpers: function(){
                var kubes = _.reduce(this.model.get('containers'), function(memo, c) {
                        return memo + c.kubes
                    }, 0),
                    checked = this.model.is_checked ? true : false;
                return {
                    kubes: kubes,
                    checked: checked
                }
            },

            ui: {
                start      : '.start-btn',
                stop       : '.stop-btn',
                checkbox   : 'label.custom span',
                podPageBtn : '.poditem-page-btn'
            },

            events: {
                'click @ui.start'      : 'startItem',
                'click @ui.stop'       : 'stopItem',
                'click @ui.podPageBtn' : 'podPage',
                'click @ui.checkbox'   : 'toggleItem'
            },

            podPage: function(evt){
                evt.stopPropagation();
                App.navigate('pods/' + this.model.get('id'), {trigger: true});
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
                        utils.notifyWindow(response);
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
                        utils.notifyWindow(response);
                    }
                });
            },

            toggleItem: function(evt){
                var tgt = $(evt.target);
                evt.stopPropagation();
                tgt.prop('checked', !tgt.prop('checked'));
                this.trigger('item:clicked');
            }
        });

        List.PodCollection = Backbone.Marionette.CompositeView.extend({
            template            : podListTpl,
            childView           : List.PodListItem,
            tagName             : 'div',
            className           : 'container',
            childViewContainer  : 'tbody',

            ui: {
                'runPods'       : '.runPods',
                'stopPods'      : '.stopPods',
                'removePods'    : '.removePods',
                'toggleCheck'   : 'thead label.custom span',
                'th'            : 'table th'
            },

            events: {
                'click @ui.runPods'    : 'runPods',
                'click @ui.stopPods'   : 'stopPods',
                'click @ui.toggleCheck': 'toggleCheck',
                'click @ui.removePods' : 'removePods',
                'click @ui.th'         : 'toggleSort'
            },

            templateHelpers: function(){
                return {
                    allChecked: this.collection.fullCollection.allChecked ? true : false,
                    checked: this.collection.fullCollection.checkedNumber
                }
            },

            initialize: function(){
                if (!this.collection.fullCollection.hasOwnProperty('checkedNumber')) {
                    this.collection.fullCollection.checkedNumber = 0;
                }
                this.counter = 1;
            },

            toggleSort: function(e) {
                var target = $(e.target),
                  targetClass = target.attr('class');
                if (targetClass) {
                  this.collection.setSorting(targetClass, this.counter);
                  this.collection.fullCollection.sort();
                  this.counter = this.counter * (-1)
                  target.find('.caret').toggleClass('rotate').parent()
                      .siblings().find('.caret').removeClass('rotate');
                }
            },

            toggleCheck: function(evt){
                var tgt = evt.target;
                evt.stopPropagation();
                if (this.collection.fullCollection.allChecked){
                    this.collection.fullCollection.allChecked = false;
                    this.collection.fullCollection.checkedNumber = 0;
                    this.collection.fullCollection.each(function(m){m.is_checked = false;});
                }
                else {
                    this.collection.fullCollection.allChecked = true;
                    this.collection.fullCollection.checkedNumber = this.collection.fullCollection.length;
                    this.collection.fullCollection.each(function(m){m.is_checked = true;});
                }
                this.render();
            },

            childEvents: {
                'item:clicked': function(view){
                    var model = this.collection.at(view.index);
                    model.is_checked = model.is_checked
                        ? (this.collection.fullCollection.checkedNumber--, false)
                        : (this.collection.fullCollection.checkedNumber++, true);
                    if (!this.collection.fullCollection.checkedNumber) {
                        this.collection.fullCollection.allChecked = false;
                    }
                    this.render();
                }
            },

            removePods: function(evt){
                evt.stopPropagation();
                var body;
                    that = this,
                    items = that.collection.fullCollection.filter(function(i){return i.is_checked});
                if (items.length > 1){
                    body = "Are you sure want to delete selected pods?"
                } else {
                    body = "Are you sure want to delete selected pod?"
                }
                utils.modalDialogDelete({
                    title: "Delete",
                    body: body,
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            for (i in items) {items[i].destroy({
                                wait: true,
                                error: function(model, response){
                                    utils.notifyWindow(response);
                                }
                            })}
                            that.collection.fullCollection.checkedNumber = 0;
                            that.collection.fullCollection.allChecked = false;
                            that.render();
                        },
                        buttonCancel: true
                   }
               });
            },

            runPods: function(evt){
                evt.stopPropagation();
                this.sendCommand('start');
            },

            stopPods: function(evt){
                evt.stopPropagation();
                this.sendCommand('stop');
            },

            sendCommand: function(command){
                var items = this.collection.fullCollection.filter(function(i){return i.is_checked});

                for (i in items) {
                    items[i].save({command: command}, {
                        error: function(model, response){
                            utils.notifyWindow(response);
                        }
                    });
                    items[i].is_checked = false;
                    this.collection.fullCollection.checkedNumber--;
                }
                this.collection.fullCollection.allChecked = false;
                this.render();
            },

            onBeforeDestroy: function(){
                this.trigger('pager:clear');
            }
        });
    });

    return Pods.Views.List;
});
