define(['app_data/app',
        'tpl!app_data/pods/templates/layout_pod_list.tpl',
        'tpl!app_data/pods/templates/pod_list_item.tpl',
        'tpl!app_data/pods/templates/pod_list_empty.tpl',
        'tpl!app_data/pods/templates/pod_list.tpl',
        'app_data/utils',
        'bootstrap'],
       function(App, layoutPodListTpl, podListItemTpl, podListEmptyTpl, podListTpl, utils){
    'use strict';

    var podList = {};

    podList.PodListLayout = Backbone.Marionette.LayoutView.extend({
        template: layoutPodListTpl,

        regions: {
            nav: '#layout-nav',
            header: '#layout-header',
            list: '#layout-list',
            pager: '#layout-footer'
        },

        initialize: function(){
            var that = this;
            this.listenTo(this.list, 'show', function(view){
                that.listenTo(view, 'pager:clear', that.clearPager);
            });
        },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        clearPager: function(){
            this.trigger('pager:clear');
        },
    });

    podList.PodListEmpty = Backbone.Marionette.ItemView.extend({
        template : podListEmptyTpl,
        tagName  : 'tr',
    });

    // View for showing a single pod item as a container in pods list
    podList.PodListItem = Backbone.Marionette.ItemView.extend({
        template    : podListItemTpl,
        tagName     : 'tr',
        className   : function(){
            return 'pod-item ' + this.model.get('status')
                 + (this.model.is_checked ? ' checked' : '');
        },
        attributes: function(){
            var attrs = {};
            if (this.model.get('status') === 'deleting')
                attrs['title'] = 'Pod will be deleted soon.';
            return attrs;
        },

        initialize: function(options){
            this.index = options.childIndex;
        },

        templateHelpers: function(){
            return {
                kubes: this.model.getKubes(),
                kubeType: this.model.getKubeType(),
                checked: !!this.model.is_checked,
                ableTo: _.bind(this.model.ableTo, this.model),
            };
        },

        ui: {
            start      : '.start-btn',
            restart      : '.restart-btn',
            paystart   : '.pay-and-start-btn',
            stop       : '.stop-btn',
            remove     : '.terminate-btn',
            checkbox   : 'label.custom span',
            podPageBtn : '.poditem-page-btn'
        },

        events: {
            'click @ui.start'      : 'startItem',
            'click @ui.restart'    : 'restartItem',
            'click @ui.paystart'   : 'payStartItem',
            'click @ui.stop'       : 'stopItem',
            'click @ui.remove'     : 'deleteItem',
            'click @ui.podPageBtn' : 'podPage',
            'click @ui.checkbox'   : 'toggleItem'
        },

        modelEvents: {
            'change': 'render'
        },

        podPage: function(evt){
            evt.stopPropagation();
            App.navigate('pods/' + this.model.id, {trigger: true});
        },

        startItem: function(){ this.model.cmdStart(); },
        payStartItem: function(){ this.model.cmdPayAndStart(); },
        restartItem: function(){ this.model.cmdRestart(); },
        stopItem: function(){ this.model.cmdStop(); },
        deleteItem: function(){ this.model.cmdDelete(); },

        toggleItem: function(evt){
            evt.stopPropagation();
            this.model.is_checked = !this.model.is_checked;
            this.trigger('item:clicked');
        }
    });

    podList.PodCollection = Backbone.Marionette.CompositeView.extend({
        template            : podListTpl,
        childView           : podList.PodListItem,
        tagName             : 'div',
        className           : 'container',
        emptyView           : podList.PodListEmpty,
        childViewContainer  : 'tbody',

        ui: {
            'runPods'       : '.runPods',
            'stopPods'      : '.stopPods',
            'restartPods'   : '.restartPods',
            'removePods'    : '.removePods',
            'toggleCheck'   : 'thead label.custom span',
            'th'            : 'table th'
        },

        events: {
            'click @ui.runPods'    : 'runPods',
            'click @ui.stopPods'   : 'stopPods',
            'click @ui.restartPods': 'restartPods',
            'click @ui.toggleCheck': 'toggleCheck',
            'click @ui.removePods' : 'removePods',
            'click @ui.th'         : 'toggleSort'
        },

        onShow: function(){
            utils.preloader.hide();
        },

        templateHelpers: function(){
            return {
                allChecked: this.collection.allChecked(),
                checked: this.collection.checkedItems(),
                isCollection : this.collection.fullCollection.length < 1 ? 'disabled' : '',
                sortingType : this.collection.orderAsDict(),
                collection: this.collection,
            };
        },

        initialize: function(options){
            this.counter = 1;
            this.collection.order = options.order || [
                // sort by status (asc), but if statuses are equal,
                // sort by name (asc), and so on...
                {key: 'status', order: 1}, {key: 'name', order: 1},
                {key: 'kube_type', order: 1}, {key: 'kubes', order: -1}
            ];
            this.collection.fullCollection.sort();
            this.collection.on('change', function(){ this.fullCollection.sort(); });
        },

        toggleSort: function(e) {
            var targetClass = e.target.className;
            if (!targetClass) return;
            this.collection.toggleSort(targetClass);
            this.render();
        },

        toggleCheck: function(evt){
            evt.stopPropagation();
            if (this.collection.fullCollection.length > 0){
                if (this.collection.allChecked()){
                    this.collection.fullCollection.each(function(m){ m.is_checked = false; });
                } else {
                    this.collection.fullCollection.each(function(m){
                        m.is_checked = m.get('status') !== 'deleting';
                    });
                }
            }
            this.render();
        },

        childViewOptions: function(model, index){
            return {
                childIndex: index
            };
        },

        childEvents: {
            'item:clicked': 'render',
        },

        removePods: function(evt){
            evt.stopPropagation();
            var body,
                that = this,
                items = that.collection.checkedItems();
            if (items.length > 1){
                body = 'Are you sure you want to delete selected pods?';
            } else {
                body = 'Are you sure you want to delete "' +
                    _.escape(items[0].get('name')) + '" pod?';
            }
            utils.modalDialogDelete({
                title: "Delete",
                body: body,
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        var deferreds = _.map(items, function(item) {
                            if (!item.ableTo('delete')) return;
                            return item.destroy({wait: true})
                                .fail(utils.notifyWindow);
                        }, this);
                        $.when.apply($, deferreds).always(utils.preloader.hide);

                        that.collection.fullCollection.each(
                            function(model){ model.is_checked = false; });
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

        restartPods: function(){
            var that = this,
                items = _.filter(this.collection.checkedItems(),
                                 function(pod){ return pod.ableTo('redeploy'); }),
                many = items.length > 1,
                successMsg = 'Pod' + (many ? 's' : '') + ' will be restarted soon',
                title = 'Confirm restarting of ' + items.length
                    + ' application' + (many ? 's' : '');
            utils.modalDialog({
                title: title,
                body: 'You can wipe out all the data and redeploy the '
                    + 'application' + (many ? 's' : '') + ' or you can just '
                    + 'restart and save data in Persistent storages of your '
                    + 'application' + (many ? 's' : '') + '.',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.sendCommand('redeploy')
                            .done(function(){ utils.notifyWindow(successMsg, 'success'); });
                    },
                    buttonCancel: function(){
                        utils.modalDialog({
                            title: title,
                            body: 'Are you sure you want to delete all data? You will '
                                + 'not be able to recover this data if you continue.',
                            small: true,
                            show: true,
                            footer: {
                                buttonOk: function(){
                                    that.sendCommand('redeploy', {wipeOut: true})
                                        .done(function(){ utils.notifyWindow(successMsg, 'success'); });
                                },
                                buttonOkText: 'Continue',
                                buttonOkClass: 'btn-danger',
                                buttonCancel: true
                            }
                        });
                    },
                    buttonOkText: 'Just Restart',
                    buttonCancelText: 'Wipe Out',
                    buttonCancelClass: 'btn-danger',
                }
            });
        },

        stopPods: function(evt){
            evt.stopPropagation();
            this.sendCommand('stop');
        },

        sendCommand: function(command, options){
            var items = this.collection.checkedItems();

            utils.preloader.show();
            var deferreds = _.map(items, function(item) {
                item.is_checked = false;
                if (!item.ableTo(command)) return;
                return item.command(command, options)
                    .fail(utils.notifyWindow);
            }, this);
            this.render();
            return $.when.apply($, deferreds).always(utils.preloader.hide);
        },

        onBeforeDestroy: function(){
            this.trigger('pager:clear');
        }
    });

    return podList;
});
