import App from 'app_data/app';
import * as utils from 'app_data/utils';

/* Node tabs */
import nodeDetailedLayoutTpl from 'app_data/nodes/templates/node_tabs/layout.tpl';
import nodeGeneralTabTpl from 'app_data/nodes/templates/node_tabs/general.tpl';
import nodeLogsTabTpl from 'app_data/nodes/templates/node_tabs/logs.tpl';
import nodeMonitoringTabTpl from 'app_data/nodes/templates/node_tabs/monitoring/list.tpl';
import nodeItemGraphTpl from 'app_data/nodes/templates/node_tabs/monitoring/item.tpl';
import nodeTimelinesTabTpl from 'app_data/nodes/templates/node_tabs/timelines.tpl';
import statusLineTpl from 'app_data/nodes/templates/node_tabs/status_line.tpl';
import sidebarTpl from 'app_data/nodes/templates/node_tabs/sidebar.tpl';

/* Node list */
import nodeEmptyTpl from 'app_data/nodes/templates/node_list/empty.tpl';
import nodeItemTpl from 'app_data/nodes/templates/node_list/item.tpl';
import nodeListTpl from 'app_data/nodes/templates/node_list/list.tpl';

/* Add node */
import nodeAddStepTpl from 'app_data/nodes/templates/add_node.tpl';
import nodeLayoutTpl from 'app_data/nodes/templates/layout.tpl';

import 'jqplot';
import 'jqplot-axis-renderer';
import 'bootstrap-select';
import 'tooltip';

export const NodeEmpty = Backbone.Marionette.ItemView.extend({
    template: nodeEmptyTpl,
    tagName: 'tr'
});

export const NodeItem = Backbone.Marionette.ItemView.extend({
    template: nodeItemTpl,
    tagName: 'tr',

    ui: {
        'deleteNode' : '.deleteNode',
        'tooltip'    : '[data-toggle="tooltip"]'
    },

    events: {
        'click @ui.deleteNode' : 'deleteNode'
    },

    modelEvents: { 'change': 'render' },
    templateHelpers(){
        var model = this.model,
            kubeType = App.kubeTypeCollection.get(model.get('kube_type'));
        return {
            'kubeType': kubeType ? kubeType.get('name') : '',
        };
    },

    onDomRefresh(){ this.ui.tooltip.tooltip(); },

    deleteNode() {
        var that = this,
            name = that.model.get('hostname');

        utils.modalDialogDelete({
            title: 'Delete ' + name + '?',
            body: "Are you sure you want to delete node '" + name + "'?",
            small: true,
            show: true,
            footer: {
                buttonOk() {
                    utils.preloader.show();
                    that.model.save({command: 'delete'}, {patch: true})
                        .always(utils.preloader.hide)
                        .fail(utils.notifyWindow);
                },
                buttonCancel: true
            }
        });
    }
});

export const NodesListView = Backbone.Marionette.CompositeView.extend({
    template           : nodeListTpl,
    childView          : NodeItem,
    emptyView          : NodeEmpty,
    childViewContainer : 'tbody',
    className          : 'container',

    ui: {
        th : 'table th'
    },

    events: {
        'click @ui.th' : 'toggleSort'
    },

    initialize(){
        this.collection.order = [
            {key: 'hostname', order: 1},
            {key: 'ip', order: 1},
            {key: 'kube_type', order: 1},
            {key: 'status', order: 1}
        ];
        this.collection.fullCollection.sort();
        this.collection.on('update reset', function(){
            this.fullCollection.sort();
        });
    },

    templateHelpers(){
        return {
            sortingType: this.collection.orderAsDict()
        };
    },

    search(data){
        this.collection.searchString = data;
        this.collection.refilter();
    },

    toggleSort(e) { //TODO move filter to model
        var targetClass = e.target.className;
        if (!targetClass) return;
        this.collection.toggleSort(targetClass);
        this.render();
    }
});

export const NodeAddStep = Backbone.Marionette.ItemView.extend({
    template: nodeAddStepTpl,

    ui: {
        'nodeAddBtn'     : 'button#node-add-btn',
        'nodeTypeSelect' : 'select.kube_type',
        'node_name'      : 'input#node_address',
        'selectpicker'   : '.selectpicker',
        'add_field'      : '.add',
        'remove_field'   : '.remove',
        'block_device'   : '.block-device',
        'input'          : 'input'
    },

    events:{
        'click @ui.add_field'       : 'addField',
        'click @ui.remove_field'    : 'removeField',
        'click @ui.nodeAddBtn'      : 'complete',
        'focus @ui.input'           : 'removeError',
        'change @ui.nodeTypeSelect' : 'changeKubeType',
        'change @ui.block_device'   : 'changeLsDevices',
        'change @ui.node_name'      : 'changeHostname'
    },

    initialize(options){
        this.setupInfo = options.setupInfo;
        if (!this.setupInfo.AWS && this.setupInfo.ZFS){
            this.model.set('lsdevices', ['']);
        }
    },

    changeKubeType(){ this.model.set('kube_type', Number(this.ui.nodeTypeSelect.val())); },
    changeHostname(){ this.model.set('hostname', this.ui.node_name.val()); },

    changeLsDevices(evt){
        var target = $(evt.target),
            index = target.parent().index() - 1;
        this.model.get('lsdevices')[index] = target.val().trim();
    },

    templateHelpers(){
        return {
            kubeTypes: App.kubeTypeCollection.filter(function(kube){
                return kube.id !== -1;  // "Internal service" kube-type
            }),
            setupInfo: this.setupInfo
        };
    },

    onRender(){
        this.model.set('kube_type', Number(this.ui.nodeTypeSelect.val()));
        this.ui.selectpicker.selectpicker();
    },

    removeError(evt){ $(evt.target).removeClass('error'); },

    addField(){
        this.model.get('lsdevices').push('');
        this.render();
    },

    removeField(evt){
        var target = $(evt.target),
            index = target.parents('.relative').index() - 1;
        this.model.get('lsdevices').splice(index, 1);
        this.render();
    },

    validate(data){
        let pattern = /^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$/i;  // eslint-disable-line max-len
        if (!data){
            return false;
        } else if (!data.hostname){
            this.ui.node_name.addClass('error');
            utils.notifyWindow('Hostname can\'t be empty');
            return false;
        } else if (!pattern.test(data.hostname)){
            this.ui.node_name.addClass('error');
            utils.notifyWindow(
                'Hostname can\'t contain some special symbols like ' +
                '"#", "%", "/" or start with "."');
            return false;
        } else if (data.lsdevices && !data.lsdevices.length){
            utils.notifyWindow('Block devices name can\'t be empty.');
            this.ui.block_device.addClass('error');
            return false;
        } else {
            return true;
        }
    },

    complete() {
        let data = [],
            that = this,
            zfs = this.setupInfo.ZFS,
            aws = this.setupInfo.AWS,
            hostname = this.ui.node_name.val();

        hostname = hostname.replace(/\s+/g, '');
        this.ui.node_name.val(hostname);

        if (zfs && !aws) {
            data = {
                hostname: hostname,
                status: 'pending',
                kube_type: that.model.get('kube_type'),
                lsdevices: _.compact(that.model.get('lsdevices')),
                install_log: ''
            };
        } else {
            data = {
                hostname: hostname,
                status: 'pending',
                kube_type: that.model.get('kube_type'),
                install_log: ''
            };
        }

        if (this.validate(data)) {
            App.getNodeCollection().done(function(nodeCollection){
                utils.preloader.show();
                nodeCollection.create(data, {
                    wait: true,
                    complete: utils.preloader.hide,
                    success:  function(){
                        App.navigate('nodes', {trigger: true});
                        utils.notifyWindow(
                            'Node "' + hostname + '" is added successfully',
                            'success'
                        );
                    },
                    error: function(collection, response){
                        that.ui.node_name.addClass('error');
                        utils.notifyWindow(response);
                    },
                });
            });
        }
    }
});

export const NodeDetailedSatusLine = Backbone.Marionette.ItemView.extend({
    template: statusLineTpl,
    className: 'status-line',
    modelEvents: { 'change': 'render' },
    ui: { 'delete' : '.terminate-btn' },
    events: { 'click @ui.delete' : 'deleteNode' },

    initialize(options) {
        var that = this;
        App.getNodeCollection().done(function(nodeCollection){
            that.nodeId = options.nodeId;
            that.model = nodeCollection.get(options.nodeId);
        });
    },

    deleteNode() {
        var that = this;
        App.getNodeCollection().done(function(nodeCollection){
            var model = nodeCollection.get(that.nodeId),
                name = model.get('hostname');
            utils.modalDialogDelete({
                title: 'Delete ' + name + '?',
                body: "Are you sure you want to delete node '" + name + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk(){
                        utils.preloader.show();
                        model.save({command: 'delete'}, {patch: true})
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow);
                    },
                    buttonCancel: true
                }
            });
        });
    }
});

export const NodeDetailedSidebar = Backbone.Marionette.ItemView.extend({
    template: sidebarTpl,
    tagName: 'ul',
    className: 'nav nav-sidebar',

    initialize(options){
        this.tab = options.tab;
        this.nodeId = options.nodeId;
    },

    templateHelpers(){
        return {
            tab : this.tab,
            id : this.nodeId
        };
    }
});

export const NodeDetailedLayout = Backbone.Marionette.LayoutView.extend({
    template: nodeDetailedLayoutTpl,

    regions: {
        nav: '#nav',
        breadcrumbs: '#breadcrumbs',
        sidebar: '#sidebar',
        statusLine: '#status-line',
        tabContent: '.content'
    },

    templateHelpers(){
        return {
            hostname: this.model ? this.model.get('hostname') : 'hostname'
        };
    }
});

export const NodeGeneralTabView = Backbone.Marionette.ItemView.extend({
    template: nodeGeneralTabTpl,
    ui: { 'logSpollerButton' : '.spoiler-btn.log' },
    events: { 'click @ui.logSpollerButton' : 'logSpoller' },
    onBeforeShow: utils.preloader.show,
    onShow: utils.preloader.hide,
    modelEvents: { 'change': 'render' },
    logSpoller(){
        this.ui.logSpollerButton.parent().children('.spoiler-body').collapse('toggle');
    },

    initialize() {
        this.listenTo(this.model, 'update_install_log', this.render);
        this.listenTo(this.model.collection, 'reset', this.render);
    }
});

export const NodeLogsTabView = Backbone.Marionette.ItemView.extend({
    template: nodeLogsTabTpl,
    ui: { textarea: '.node-logs' },
    modelEvents: { 'change': 'render' },
    onBeforeShow: utils.preloader.show,
    onShow: utils.preloader.hide,

    initialize() {
        var that = this;
        _.bindAll(this, 'getLogs');
        App.getNodeCollection().done(function(nodeCollection){
            that.listenTo(nodeCollection, 'reset', that.render);
            that.getLogs();
        });
    },

    getLogs() {
        var that = this;
        this.model.getLogs(/*size=*/100).always(function(){
            // callbacks are called with model as a context
            if (!that.destroyed) {
                this.set('timeout', setTimeout(that.getLogs, 10000));
                that.render();
            }
        });
    },

    onBeforeRender() {
        var el = this.ui.textarea;
        if (typeof el !== 'object' ||
                (el.scrollTop() + el.innerHeight()) === el[0].scrollHeight)
            this.logScroll = null;  // stick to bottom
        else
            this.logScroll = el.scrollTop();  // stay at this position
    },

    onRender() {
        if (this.logScroll === null)  // stick to bottom
            this.ui.textarea.scrollTop(this.ui.textarea[0].scrollHeight);
        else  // stay at the same position
            this.ui.textarea.scrollTop(this.logScroll);
    },

    onBeforeDestroy() {
        this.destroyed = true;
        clearTimeout(this.model.get('timeout'));
    }
});

export const NodeMonitoringTabViewItem = Backbone.Marionette.ItemView.extend({
    template: nodeItemGraphTpl,
    ui: { chart: '.graph-item' },

    initialize(options) {
        this.node = options.node;
        this.error = options.error;
        this.listenTo(this.node.collection, 'reset', this.render);
    },

    makeGraph(){
        var lines = this.model.get('lines'),
            points = [],
            error;

        if (this.error)
            error = this.error;
        else if (this.node.get('status') === 'running')
            error = 'Collecting data... plot will be dispayed in a few minutes.';
        else
            error = "Couldn't connect to the node (maybe it's rebooting)...";

        var options = {
            title: this.model.get('title'),
            axes: {
                xaxis: {
                    label: 'time',
                    renderer: $.jqplot.DateAxisRenderer,
                },
                yaxis: {label: this.model.get('ylabel'), min: 0}
            },
            seriesDefaults: {
                showMarker: false,
                rendererOptions: {
                    smooth: true,
                    animation: {
                        show: true
                    }
                }
            },
            series: this.model.get('series'),
            legend: {
                show: true,
                placement: 'insideGrid'
            },
            grid: {
                background: '#ffffff',
                drawBorder: false,
                shadow: false
            },
            noDataIndicator: {
                show: true,
                indicator: error,
                axes: {
                    xaxis: {
                        min: App.currentUser.localizeDatetime(+new Date() - 1000 * 60 * 20),
                        max: App.currentUser.localizeDatetime(),
                        tickOptions: {formatString:'%H:%M'},
                        tickInterval: '5 minutes',
                    },
                    yaxis: {min: 0, max: 150, tickInterval: 50}
                }
            },
        };

        if (this.model.has('seriesColors')) {
            options.seriesColors = this.model.get('seriesColors');
        }

        for (var i = 0; i < lines; i++) {
            if (points.length < i + 1) {
                points.push([]);
            }
        }

        // If there is only one point, jqplot will display ugly plot with
        // weird grid and no line.
        // Remove this point to force jqplot to show noDataIndicator.
        if (this.model.get('points').length === 1)
            this.model.get('points').splice(0);

        this.model.get('points').forEach(function(record){
            for (var i = 0; i < lines; i++) {
                points[i].push([
                    App.currentUser.localizeDatetime(record[0]),
                    record[i + 1]
                ]);
            }
        });
        this.ui.chart.jqplot(points, options);
    },

    onDomRefresh(){
        try {
            this.makeGraph();
        } catch (e){
            console.log('Cannot display graph' + e); // eslint-disable-line no-console
        }
    },
});

export const NodeMonitoringTabView = Backbone.Marionette.CompositeView.extend({
    template: nodeMonitoringTabTpl,
    childView: NodeMonitoringTabViewItem,
    childViewContainer: '.graphs',
    childViewOptions(){
        return {node: this.model, error: this.error};
    },
    onBeforeRender: utils.preloader.show,
    onShow: utils.preloader.hide,
    modelEvents: { 'change': 'render' },

    initialize(options){
        this.error = options.error;
        if (this.error)
            this.collection.setEmpty();
    },
});

export const NodeTimelinesTabView = Backbone.Marionette.ItemView.extend({
    template: nodeTimelinesTabTpl
});

export const NodesLayout = Backbone.Marionette.LayoutView.extend({
    template: nodeLayoutTpl,
    regions: {
        nav: 'div#nav',
        breadcrumbs: 'div#breadcrumbs',
        main: 'div#main',
        pager: 'div#pager'
    },
    onBeforeShow: utils.preloader.show,
    onShow:utils.preloader.hide
});
