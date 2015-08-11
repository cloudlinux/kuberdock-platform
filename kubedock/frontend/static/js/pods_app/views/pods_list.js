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
            className   : 'pod-item',

            initialize: function(options){
                this.index = options.childIndex;
            },

            templateHelpers: function(){
                var kubes = _.reduce(this.model.get('containers'), function(memo, c) {
                        return memo + c.kubes
                    }, 0),
                    checked = this.model.is_checked ? true : false;
                return {
                    index: this.index+1,
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
            },
        });

        List.PodCollection = Backbone.Marionette.CompositeView.extend({
            template            : podListTpl,
            childView           : List.PodListItem,
            tagName             : 'div',
            className           : 'container',
            childViewContainer  : 'tbody',

            initialize: function(){
                if (!this.collection.hasOwnProperty('checkedNumber')) {
                    this.collection.checkedNumber = 0;
                }
            },

            templateHelpers: function(){
                return {
                    allChecked: this.collection.allChecked ? true : false
                }
            },

            ui: {
                'runPods'    : '.runPods',
                'stopPods'   : '.stopPods',
                'removePods' : '.removePods',
                'toggleCheck'   : 'thead label.custom span'
            },

            events: {
                'click @ui.runPods'    : 'runPods',
                'click @ui.stopPods'   : 'stopPods',
                'click @ui.toggleCheck': 'toggleCheck',
                'click @ui.removePods' : 'removePods',
            },

            toggleCheck: function(evt){
                var tgt = evt.target,
                    thead = this.$('thead th:not(:first)'),
                    count = this.$('.count'),
                    podsControl = this.$('.podsControl');
                evt.stopPropagation();
                if (this.collection.allChecked){
                    this.collection.allChecked = false;
                    this.collection.checkedNumber = 0;
                    this.collection.each(function(m){m.is_checked = false;});
                    $('tbody tr').each(function(i, el){
                        $(el).find('input:checkbox').get(0).checked = false;
                    });
                    thead.removeClass('min-opacity');
                    podsControl.hide();
                    tgt.checked = false;
                }
                else {
                    this.collection.allChecked = true;
                    this.collection.checkedNumber = this.collection.length;
                    this.collection.each(function(m){m.is_checked = true;});
                    $('tbody tr').each(function(i, el){
                        $(el).find('input:checkbox').get(0).checked = true;
                    });
                    count.text(this.collection.length + (this.collection.length > 1 ? ' Items' : ' Item'))
                    thead.addClass('min-opacity');
                    podsControl.show();
                    tgt.checked = true;
                }
            },

            childViewOptions: function(model, index){
                return {
                    childIndex: index
                };
            },

            childEvents: {
                'item:clicked': function(view){
                    var model = this.collection.at(view.index),
                        thead = this.$('thead th:not(:first)'),
                        allChecker = this.$('thead th:first input:checkbox').get(0),
                        count = this.$('.count'),
                        podsControl = this.$('.podsControl');

                    if (model.is_checked) {
                        model.is_checked = false;
                        this.collection.checkedNumber--;
                    }
                    else {
                        model.is_checked = true;
                        this.collection.checkedNumber++;
                    }

                    if (this.collection.checkedNumber && !thead.hasClass('min-opacity')){
                        thead.addClass('min-opacity');
                        podsControl.show();
                    } else if (!this.collection.checkedNumber && thead.hasClass('min-opacity')) {
                        thead.removeClass('min-opacity');
                        podsControl.hide();
                        if (allChecker.checked) { allChecker.checked = false; }
                    }
                    count.text(this.collection.checkedNumber + (this.collection.checkedNumber > 1 ? ' Items' : ' Item'))
                }
            },

            removePods: function(evt){
                evt.stopPropagation();
                var that = this;
                utils.modalDialogDelete({
                    title: "Delete",
                    body: "Are you sure want to delete selected pods?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            var items = that.collection.filter(function(i){return i.is_checked});
                            for (i in items) {items[i].destroy({wait: true})}
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
                var items = this.collection.filter(function(i){return i.is_checked});
                for (i in items) {items[i].save({command: command}, {wait: true})}
            },

            onBeforeDestroy: function(){
                this.trigger('pager:clear');
            }
        });
    });

    return Pods.Views.List;
});
