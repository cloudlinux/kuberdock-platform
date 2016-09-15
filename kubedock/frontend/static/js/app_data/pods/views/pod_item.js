define(['app_data/app', 'app_data/model',
        'tpl!app_data/pods/templates/layout_pod_item.tpl',
        'tpl!app_data/pods/templates/page_info_panel.tpl',
        'tpl!app_data/pods/templates/page_containers_changed.tpl',
        'tpl!app_data/pods/templates/page_containers_unchanged.tpl',
        'tpl!app_data/pods/templates/page_container_item.tpl',
        'tpl!app_data/pods/templates/pod_item_controls.tpl',
        'tpl!app_data/pods/templates/pod_item_upgrade_resources.tpl',
        'tpl!app_data/pods/templates/pod_item_upgrade_container_resources.tpl',
        'tpl!app_data/pods/templates/pod_item_graph.tpl',
        'moment-timezone', 'app_data/utils',
        'bootstrap', 'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer',
        'numeral', 'bbcode', 'tooltip'],
       function(App, Model,
                layoutPodItemTpl,
                pageInfoPanelTpl,
                pageContainersChangedTpl,
                pageContainersUnchangedTpl,
                pageContainerItemTpl,
                podItemControlsTpl,
                upgradeResourcesTpl,
                upgradeContainerResourcesTpl,
                podItemGraphTpl,
                moment, utils){

    var podItem = {};

    podItem.PodItemLayout = Backbone.Marionette.LayoutView.extend({
        template : layoutPodItemTpl,

        // TODO: move nav, header, and messages out of here
        regions: {
            nav      : '#item-navbar',
            header   : '#item-header',
            messages : '#messages-block',
            controls : '#item-controls',
            info     : '#item-info',
            contents : '#layout-contents'
        },

        ui: {
            podsList : '.podsList'
        },

        events: {
            'click @ui.podsList' : 'showPodsList',
        },

        onBeforeShow: utils.preloader.show,
        onShow: utils.preloader.hide,
        showPodsList: function(){
            App.navigate('pods', {trigger: true});
        }
    });

    // View for showing a single container item as a container in containers list
    podItem.ContainersListItem = Backbone.Marionette.ItemView.extend({
        template    : pageContainerItemTpl,
        tagName     : 'tr',
        className   : 'container-item',

        initialize: function(){
            this.model.addNestedChangeListener(this, this.render);
        },

        templateHelpers: function(){
            var before = this.model.get('before'),
                after = this.model.get('after'),
                startedAt = before && before.get('startedAt'),
                imagename = (before || after).get('image'),
                imagetag = null;

            if (/[^\/:]+:[^\/:]+$/.test(imagename)) {
                var pos = imagename.lastIndexOf(':');
                imagetag = imagename.substr(pos + 1);
                imagename = imagename.substr(0, pos);
            }

            return {
                changed: !before || before.isChanged(after),
                startedAt: startedAt
                    ? App.currentUser.localizeDatetime(startedAt)
                    : 'Not deployed yet',
                updateIsAvailable: this.model.updateIsAvailable,
                pod: before ? before.getPod() : after.getPod().editOf(),
                imagename: imagename,
                imagetag: imagetag,
                prettyState: before ? before.getPrettyStatus() : 'new',
            };
        },

        ui: {
            'copySshLink'      : '.copy-ssh-link',
            'updateContainer'  : '.container-update',
            'checkForUpdate'   : '.check-for-update',
            'copySshPassword'  : '.copy-ssh-password',
            'tooltip'          : '[data-toggle="tooltip"]'
        },

        events: {
            'click @ui.copySshLink'     : 'copySshLink',
            'click @ui.updateContainer' : 'updateItem',
            'click @ui.checkForUpdate'  : 'checkForUpdate',
            'click @ui.copySshPassword' : 'copySshPassword'
        },

        modelEvents: { 'change': 'render' },
        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },
        updateItem: function(){ this.model.get('before').update(); },
        checkForUpdate: function(){
            this.model.get('before').checkForUpdate().done(this.render);
        },
        copySshLink: function(){
            var sshAccess = this.model.get('before').getPod().get('direct_access');
            if (sshAccess) {
                var modelName = this.model.get('before').get('name'),
                    sshLink = sshAccess.links[modelName];
                utils.copyLink(sshLink, 'SSH link copied to clipboard');
            } else {
                utils.notifyWindow('SSH access credentials are outdated. Please, ' +
                'click Get SSH access to generate new link and password', 'error');
            }
        },
        copySshPassword: function(){
            var sshAccess = this.model.get('before').getPod().get('direct_access');
            if (sshAccess) {
                var sshPassword = sshAccess.auth;
                utils.copyLink(sshPassword, 'SSH password copied to clipboard');
            } else {
                utils.notifyWindow('SSH access credentials are outdated. Please, ' +
                'click Get SSH access to generate new link and password', 'error');
            }
        },
    });

    var ContainersTableBaseView = Backbone.Marionette.CompositeView.extend({
        childView: podItem.ContainersListItem,
        childViewContainer: 'tbody',
        collectionEvents: {
            'update reset change': 'toggleVisibility',
        },
        onRender: function(){ this.toggleVisibility(); },
    });

    podItem.ChangedContainersView = ContainersTableBaseView.extend({
        template: pageContainersChangedTpl,
        filter: function(model){
            return !model.get('before') || !model.get('after') ||
                model.get('before').isChanged(model.get('after'));
        },
        toggleVisibility: function(){
            this.$el.toggleClass('hidden', !this.collection.some(this.filter));
        },
    });

    podItem.UnchangedContainersView = ContainersTableBaseView.extend({
        template: pageContainersUnchangedTpl,
        ui: {
            caption: 'caption',
        },
        filter: function(model){
            return model.get('before') && model.get('after') &&
                !model.get('before').isChanged(model.get('after'));
        },
        toggleVisibility: function(){
            this.$el.toggleClass('hidden', !this.collection.some(this.filter));
            this.ui.caption.toggleClass('hidden', this.collection.all(this.filter));
        },
    });

    podItem.ContainersPanel = Backbone.Marionette.LayoutView.extend({
        template  : pageInfoPanelTpl,

        regions: {
            changed  : '#containers-list-changed',
            unchanged: '#containers-list',
        },

        initialize: function(){
            this.on('show', function(){
                this.changed.show(new podItem.ChangedContainersView(
                    {collection: this.collection}));
                this.unchanged.show(new podItem.UnchangedContainersView(
                    {collection: this.collection}));
            });
        },
    });

    podItem.ControlsPanel = Backbone.Marionette.ItemView.extend({
        template: podItemControlsTpl,
        tagName: 'div',
        className: 'pod-controls',

        ui: {
            resetSsh : '.resetSsh',
        },
        events: {
            'click .start-btn'         : 'startItem',
            'click .pay-and-start-btn' : 'payStartItem',
            'click .restart-btn'       : 'restartItem',
            'click .stop-btn'          : 'stopItem',
            'click .terminate-btn'     : 'terminateItem',
            'click @ui.resetSsh'       : 'resetSshAccess'
        },

        modelEvents: {
            'change' : 'render'
        },

        initialize: function(options){
            this.graphs = !!options.graphs;
            this.upgrade = !!options.upgrade;
        },

        templateHelpers: function(){
            var publicName = this.model.has('public_aws')
                    ? this.model.get('public_aws')
                    : '',
                kubes = this.model.getKubes(),
                pkg = App.userPackage,
                kubeId = this.model.get('kube_type'),
                kubeType = App.kubeTypeCollection.get(kubeId),
                hasPorts = this.model.get('containers').any(function(c) {
                    return c.get('ports') && c.get('ports').length;
                });

            this.model.recalcInfo(pkg);
            if (this.model.get('edited_config'))
                this.model.get('edited_config').recalcInfo(pkg);

            return {
                prettyStatus    : this.model.getPrettyStatus(),
                hasPorts        : hasPorts,
                publicIP        : this.model.get('public_ip'),
                publicName      : publicName,
                graphs          : this.graphs,
                upgrade         : this.upgrade,
                kubeType        : kubeType,
                kubes           : kubes,
                totalPrice      : this.model.totalPrice,
                limits          : this.model.limits,
                podName         : this.model.get('name'),
                period          : pkg.get('period'),
                ableTo          : _.bind(this.model.ableTo, this.model),
                currentUser     : App.currentUser
            };
        },

        resetSshAccess : function() { this.model.resetSshAccess(); },
        startItem: function(){ this.model.cmdStart(); },
        payStartItem: function(){ this.model.cmdPayAndStart(); },
        restartItem: function(){ this.model.cmdRestart(); },
        stopItem: function(){ this.model.cmdStop(); },
        terminateItem: function(){ this.model.cmdDelete(); },
    });

    podItem.PodGraphItem = Backbone.Marionette.ItemView.extend({
        template: podItemGraphTpl,

        initialize: function(options){
            this.pod = options.pod;
            this.error = options.error;
        },

        ui: {
            chart: '.graph-item'
        },

        onShow: function(){
            var lines = this.model.get('lines'),
                series = this.model.get('series'),
                error;

            if (this.error)
                error = this.error;
            else if (this.pod.get('status') === 'running')
                error = 'Collecting data... plot will be dispayed in a few minutes.';
            else
                error = 'Pod is not running...';

            var options = {
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

            var points = [];
            for (var i = 0; i < lines; i++)
                points.push([]);

            // If there is only one point, jqplot will display ugly plot with
            // weird grid and no line.
            // Remove this point to force jqplot to show noDataIndicator.
            if (this.model.get('points').length === 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                var time = App.currentUser.localizeDatetime(record[0]);
                for (var i = 0; i < lines; i++)
                    points[i].push([time, record[i + 1]]);
            });
            this.ui.chart.jqplot(points, options);
        }
    });

    podItem.PodGraph = Backbone.Marionette.CollectionView.extend({
        childView: podItem.PodGraphItem,
        childViewOptions: function() {
            return {pod: this.model, error: this.error};
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function(options){
            this.error = options.error;
            if (this.error)
                this.collection.setEmpty();
        },
    });

    podItem.UpgradeContainerResources = Backbone.Marionette.ItemView.extend({
        template: upgradeContainerResourcesTpl,
        tagName: 'tr',

        ui: {
            price: '.upgrade-price',
            kubes: '.upgrade-kubes',
            moreKubes: '.upgrade-kubes-more',
            lessKubes: '.upgrade-kubes-less',
        },

        events: {
            'click @ui.moreKubes': 'addKube',
            'click @ui.lessKubes': 'removeKube',
            'change @ui.kubes': 'changeKubes',
        },

        modelEvents: {
            'change': 'render',
        },

        viewOptions: ['pkg', 'modelOrig', 'kubesLimit'],
        initialize: function(options){
            this.mergeOptions(options, this.viewOptions);
        },

        templateHelpers: function(){
            var image = /^(.+?)(?::([^\/:]+))?$/.exec(this.model.get('image')),
                imagename = image[1],
                imagetag = image[2],
                kube = this.model.getPod().getKubeType(),
                kubesChange = this.model.get('kubes') - this.modelOrig.get('kubes');

            return {
                kubesLimit: this.kubesLimit,
                imagename: imagename,
                imagetag: imagetag,
                upgradePrice: this.pkg.getFormattedPrice(this.pkg.priceFor(kube.id) * kubesChange),
                pod: this.model.getPod(),
                limits: this.model.limits,
            };
        },

        addKube: function(){ this.ui.kubes.val(+this.ui.kubes.val() + 1).change(); },
        removeKube: function(){ this.ui.kubes.val(+this.ui.kubes.val() - 1).change(); },
        changeKubes: function(){
            var kubes = Math.max(1, Math.min(this.kubesLimit, +this.ui.kubes.val()));
            this.ui.kubes.val(kubes);
            this.model.set('kubes', kubes);
        },
    });

    podItem.UpgradeResources = Backbone.Marionette.CompositeView.extend({
        template: upgradeResourcesTpl,
        childView: podItem.UpgradeContainerResources,
        childViewContainer: 'tbody',
        childViewOptions: function(model){
            return {
                modelOrig: this.modelOrig.get('containers').get(model.id),
                pkg: this.pkg,
                kubesLimit: this.kubesLimit,
            };
        },

        ui: {
            cancel: '.cancel-upgrade',
            order: '.apply-upgrade'
        },

        events: {
            'click @ui.cancel': 'cancel',
            'click @ui.order': 'order',
        },

        modelEvents: {
            'change:containers[*].kubes': 'render',
        },

        viewOptions: ['modelOrig', 'containerName', 'kubesLimit', 'fixedPrice'],
        initialize: function(options){
            this.pkg = App.userPackage;
            this.mergeOptions(options, this.viewOptions);
        },

        filter: function (child) {
            return this.containerName == null || child.get('name') === this.containerName;
        },

        templateHelpers: function(){
            this.model.recalcInfo(this.pkg);
            return {
                period: this.pkg.get('period'),
                totalPrice: this.model.totalPrice,
                upgradePrice: this.pkg.getFormattedPrice(
                    this.model.rawTotalPrice - this.modelOrig.rawTotalPrice),
            };
        },

        cancel: function(){
            App.navigate('pods/' + this.model.id, {trigger: true});
        },

        order: function(){
            var that = this;
            App.getPodCollection().done(function(col){
                var modelOrigBackup = that.modelOrig.clone();
                col.add(that.model, {merge: true});
                if (that.fixedPrice){
                    utils.preloader.show();
                    $.ajax({  // TODO: use Backbone.model
                        authWrap: true,
                        type: 'POST',
                        contentType: 'application/json; charset=utf-8',
                        url: '/api/billing/orderKubes',
                        data: JSON.stringify({pod: JSON.stringify(that.model)}),
                    }).always(utils.preloader.hide).fail(utils.notifyWindow).done(function(xhr){
                        if (xhr.data.status.toLowerCase() === 'paid'){
                            utils.notifyWindow('Pod will be upgraded.', 'success');
                            App.navigate('pods/' + that.model.id, {trigger: true});
                        } else {
                            window.location = xhr.data.redirect;
                        }
                    }).fail(function(){ col.add(modelOrigBackup, {merge: true}); });
                } else {
                    that.model.command('redeploy')
                        .fail(function(){ col.add(modelOrigBackup, {merge: true}); })
                        .done(function(){
                            // we need to re-generate diff
                            delete that.modelOrig._containersDiffCollection;
                            utils.notifyWindow('Pod will be upgraded.', 'success');
                            App.navigate('pods/' + that.model.id, {trigger: true});
                        });
                }
            });
        },
    });

    return podItem;
});
