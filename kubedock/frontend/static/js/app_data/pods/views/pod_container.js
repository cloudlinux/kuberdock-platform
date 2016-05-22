define(['app_data/app', 'app_data/model', 'app_data/utils',
        'tpl!app_data/pods/templates/layout_wizard.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_general.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_env.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_logs.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_stats.tpl',
        'tpl!app_data/pods/templates/pod_item_graph.tpl',
        'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer', 'nicescroll',
        'selectpicker', 'tooltip'],
       function(App, Model, utils,
                layoutWizardTpl,

                podContainerGeneralTabTpl,
                podContainerEnvTabTpl,
                podContainerLogsTabTpl,
                podContainerStatsTabTpl,
                podItemGraphTpl){

    var views = {};

    views.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: layoutWizardTpl,
        initialize: function(){
            var that = this;
            this.listenTo(this.steps, 'show', function(view){
                // TODO: can we remove it?
                _([
                    'step:portconf',
                    'step:envconf',
                    'step:statsconf',
                    'step:logsconf',
                ]).each(function(name){
                    that.listenTo(view, name, _.bind(that.trigger, that, name));
                });
            });
        },
        regions: {
            // TODO: 1) move menu and breadcrumbs regions into App;
            //       2) pull common parts out of "steps" into separate regions;
            nav    : '#navbar-steps',
            header : '#header-steps',
            steps  : '#steps',
        },
        onBeforeShow: utils.preloader.show,
        onShow: utils.preloader.hide,
    });

    views.WizardGeneralSubView = Backbone.Marionette.ItemView.extend({
        tagName: 'div',
        template: podContainerGeneralTabTpl,
        id: 'container-page',

        ui: {
            stopContainer  : '#stopContainer',
            startContainer : '#startContainer',
            updateContainer: '.container-update',
            checkForUpdate : '.check-for-update',
        },

        events: {
            'click @ui.stopContainer'  : 'stopContainer',
            'click @ui.startContainer' : 'startContainer',
            'click @ui.updateContainer': 'updateContainer',
            'click @ui.checkForUpdate' : 'checkContainerForUpdate',
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function(options) {
            this.pod = this.model.getPod();
        },

        triggers: {
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-stats'     : 'step:statsconf',
            'click .go-to-logs'      : 'step:logsconf',
        },

        templateHelpers: function(){
            this.pod.recalcInfo();
            return {
                parentID: this.pod.id,
                volumes: this.pod.get('volumes'),
                updateIsAvailable: this.model.updateIsAvailable,
                kube_type: this.pod.getKubeType(),
                restart_policy: this.pod.get('restartPolicy'),
                podName: this.pod.get('name'),
                limits: this.model.limits,
            };
        },

        startContainer: function(){ this.pod.cmdStart(); },
        stopContainer: function(){ this.pod.cmdStop(); },
        updateContainer: function(){ this.model.update(); },
        checkContainerForUpdate: function(){
            this.model.checkForUpdate().done(this.render);
        },
    });

    views.WizardEnvSubView = Backbone.Marionette.ItemView.extend({
        template: podContainerEnvTabTpl,
        tagName: 'div',

        ui: {
            stopContainer  : '#stopContainer',
            startContainer : '#startContainer',
            updateContainer: '.container-update',
            checkForUpdate : '.check-for-update',
        },

        events: {
            'click @ui.stopContainer'  : 'stopContainer',
            'click @ui.startContainer' : 'startContainer',
            'click @ui.updateContainer': 'updateContainer',
            'click @ui.checkForUpdate' : 'checkContainerForUpdate',
        },

        triggers: {
            'click .go-to-ports'  : 'step:portconf',
            'click .go-to-stats'  : 'step:statsconf',
            'click .go-to-logs'   : 'step:logsconf',
        },

        modelEvents: {
            'change': 'render'
        },

        templateHelpers: function(){
            var pod = this.model.getPod();
            pod.recalcInfo();
            return {
                parentID: pod.id,
                updateIsAvailable: this.model.updateIsAvailable,
                sourceUrl: this.model.get('sourceUrl'),
                kube_type: pod.getKubeType(),
                limits: this.model.limits,
                restart_policy: pod.get('restartPolicy'),
            };
        },

        startContainer: function(){ this.model.getPod().cmdStart(); },
        stopContainer: function(){ this.model.getPod().cmdStop(); },
        updateContainer: function(){ this.model.update(); },
        checkContainerForUpdate: function(){
            this.model.checkForUpdate().done(this.render);
        },
    });

    views.WizardStatsSubItemView = Backbone.Marionette.ItemView.extend({
        template: podItemGraphTpl,

        initialize: function(options){ this.container = options.container; },

        ui: {
            chart: '.graph-item'
        },

        onShow: function(){
            var lines = this.model.get('lines'),
                running = this.container.get('state') === 'running',
                series = this.model.get('series'),
                options = {
                title: this.model.get('title'),
                axes: {
                    xaxis: {label: 'time', renderer: $.jqplot.DateAxisRenderer},
                    yaxis: {label: this.model.get('ylabel'), min: 0}
                },
                seriesDefaults: {
                    showMarker: false,
                    rendererOptions: {
                        smooth: true
                    }
                },
                series: series,
                grid: {
                    background: '#ffffff',
                    drawBorder: false,
                    shadow: false
                },
                legend: {
                    show: true,
                    placement: 'insideGrid'
                },
                noDataIndicator: {
                    show: true,
                    indicator: !running ? 'Container is not running...' :
                        'Collecting data... plot will be dispayed in a few minutes.',
                    axes: {
                        xaxis: {
                            min: App.currentUser.localizeDatetime(+new Date() - 1000*60*20),
                            max: App.currentUser.localizeDatetime(),
                            tickOptions: {formatString:'%H:%M'},
                            tickInterval: '5 minutes',
                        },
                        yaxis: {min: 0, max: 150, tickInterval: 50}
                    }
                },
            };

            var points = [];
            for (var i=0; i<lines;i++)
                points.push([]);

            // If there is only one point, jqplot will display ugly plot with
            // weird grid and no line.
            // Remove this point to force jqplot to show noDataIndicator.
            if (this.model.get('points').length === 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                var time = App.currentUser.localizeDatetime(record[0]);
                for (var i=0; i<lines; i++)
                    points[i].push([time, record[i+1]]);
            });
            this.ui.chart.jqplot(points, options);
        }
    });

    views.WizardStatsSubView = Backbone.Marionette.CompositeView.extend({
        childView: views.WizardStatsSubItemView,
        childViewContainer: "div.container-stats #monitoring-page",
        template: podContainerStatsTabTpl,
        tagName: 'div',

        childViewOptions: function() {
            return {container: this.model};
        },

        events: {
            'click #stopContainer'    : 'stopContainer',
            'click #startContainer'   : 'startContainer',
            'click .container-update' : 'updateContainer',
            'click .check-for-update' : 'checkContainerForUpdate',
        },

        triggers: {
            'click .go-to-ports'     : 'step:portconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-logs'      : 'step:logsconf'
        },

        modelEvents: {
            'change': 'render'
        },

        templateHelpers: function(){
            var pod = this.model.getPod();
            pod.recalcInfo();
            return {
                updateIsAvailable: this.model.updateIsAvailable,
                parentID: pod.id,
                image: this.model.get('image'),
                name: this.model.get('name'),
                state: this.model.get('state'),
                kube_type: pod.getKubeType(),
                limits: this.model.limits,
                restart_policy: pod.get('restartPolicy'),
                kubes: this.model.get('kubes'),
                podName: pod.get('name'),
            };

        },

        startContainer: function(){ this.model.getPod().cmdStart(); },
        stopContainer: function(){ this.model.getPod().cmdStop(); },
        updateContainer: function(){ this.model.update(); },
        checkContainerForUpdate: function(){
            this.model.checkForUpdate().done(this.render);
        },
    });

    views.WizardLogsSubView = Backbone.Marionette.ItemView.extend({
        template: podContainerLogsTabTpl,
        tagName: 'div',

        ui: {
            ieditable          : '.ieditable',
            textarea           : '.container-logs',
            stopItem           : '#stopContainer',
            startItem          : '#startContainer',
            updateContainer    : '.container-update',
            checkForUpdate     : '.check-for-update',
            editContainerKubes : '.editContainerKubes',
            changeKubeQty      : 'button.send',
            cancelChange       : 'button.cancel',
            kubeVal            : '.editForm input',
        },

        events: {
            'click @ui.stopItem'           : 'stopItem',
            'click @ui.startItem'          : 'startItem',
            'click @ui.updateContainer'    : 'updateContainer',
            'click @ui.checkForUpdate'     : 'checkContainerForUpdate',
            'click @ui.changeKubeQty'      : 'changeKubeQty',
            'click @ui.editContainerKubes' : 'editContainerKubes',
            'click @ui.cancelChange'       : 'closeChange',
            'keyup @ui.kubeVal'            : 'kubeVal'
        },

        triggers: {
            'click .go-to-ports'     : 'step:portconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-stats'     : 'step:statsconf'
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function() {
            _.bindAll(this, 'getLogs');
            this.getLogs();
        },

        templateHelpers: function(){
            var pod = this.model.getPod();
            pod.recalcInfo();
            return {
                parentID: pod.id,
                updateIsAvailable: this.model.updateIsAvailable,
                sourceUrl: this.model.get('sourceUrl'),
                podName: pod.get('name'),
                kube_type: pod.getKubeType(),
                limits: this.model.limits,
                restart_policy: pod.get('restartPolicy'),
                logs: this.model.logs,
                logsError: this.model.logsError,
                editKubesQty : this.model.editKubesQty,
                kubeVal : this.model.kubeVal
            };
        },

        onBeforeRender: function () {
            var el = this.ui.textarea;
            if (typeof el !== 'object' || (el.scrollTop() + el.innerHeight()) === el[0].scrollHeight)
                this.logScroll = null;  // stick to bottom
            else
                this.logScroll = el.scrollTop();  // stay at this position
        },

        onRender: function () {
            if (this.logScroll === null)  // stick to bottom
                this.ui.textarea.scrollTop(this.ui.textarea[0].scrollHeight);
            else  // stay at the same position
                this.ui.textarea.scrollTop(this.logScroll);

            if (this.niceScroll !== undefined)
                this.niceScroll.remove();
            this.niceScroll = this.ui.textarea.niceScroll({
                cursorcolor: "#69AEDF",
                cursorwidth: "12px",
                cursorborder: "none",
                cursorborderradius: "none",
                background: "#E7F4FF",
                autohidemode: false,
                railoffset: 'bottom'
            });
        },

        onBeforeDestroy: function () {
            delete this.model.kubeVal;
            delete this.model.editKubesQty;
            this.destroyed = true;
            clearTimeout(this.model.get('timeout'));
            if (this.niceScroll !== undefined)
                this.niceScroll.remove();
        },

        getLogs: function() {
            var that = this;
            this.model.getLogs(/*size=*/100).always(function(){
                // callbacks are called with model as a context
                if (!that.destroyed) {
                    this.set('timeout', setTimeout(that.getLogs, 10000));
                    that.render();
                }
            });
        },

        editContainerKubes: function(){
            this.model.editKubesQty = true;
            this.model.kubeVal = this.model.get('kubes');
            this.render();
        },

        kubeVal: function(){
            this.model.kubeVal = this.ui.kubeVal.val();
        },

        changeKubeQty: function(){
            //TODO add change Request
            this.closeChange();
        },

        closeChange: function(){
            delete this.model.kubeVal;
            delete this.model.editKubesQty;
            this.render();
        },

        startItem: function(){ this.model.getPod().cmdStart(); },
        stopItem: function(){ this.model.getPod().cmdStop(); },

        updateContainer: function(){ this.model.update(); },
        checkContainerForUpdate: function(){
            this.model.checkForUpdate().done(this.render);
        }
    });

    return views;
});
