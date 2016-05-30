define(['app_data/app',
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
       function(App,
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

        regions: {
            nav      : '#item-navbar',
            header   : '#item-header',
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
        /*className   : function(){
            return this.model.is_checked ? 'container-item checked' : 'container-item';
        },*/

        initialize: function(){
            this.model.addNestedChangeListener(this, this.render);
        },

        templateHelpers: function(){
            var before = this.model.get('before'),
                after = this.model.get('after'),
                startedAt = before && before.get('startedAt'),
                imagename = (before || after).get('image'),
                imagetag = null;

            if (/[^/:]+:[^/:]+$/.test(imagename)) {
                var pos = imagename.lastIndexOf(':');
                imagetag = imagename.substr(pos + 1);
                imagename = imagename.substr(0, pos);
            }

            return {
                changed: !before || before.isChanged(after),
                startedAt: startedAt ? App.currentUser.localizeDatetime(startedAt) : 'Not deployed yet',
                updateIsAvailable: this.model.updateIsAvailable,
                pod: before ? before.getPod() : after.getPod().editOf(),
                imagename: imagename,
                imagetag: imagetag
            };
        },

        ui: {
            'updateContainer'  : '.container-update',
            'checkForUpdate'   : '.check-for-update',
            'tooltip'          : '[data-toggle="tooltip"]',
        },

        events: {
            'click @ui.updateContainer'    : 'updateItem',
            'click @ui.checkForUpdate'     : 'checkForUpdate',
        },

        modelEvents: {
            'change': 'render'
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },
        updateItem: function(){ this.model.get('before').update(); },
        checkForUpdate: function(){
            this.model.get('before').checkForUpdate().done(this.render);
        },
    });

    var ContainersTableBaseView = Backbone.Marionette.CompositeView.extend({
        childView: podItem.ContainersListItem,
        childViewContainer: "tbody",
        collectionEvents: {  // TODO: do not re-render whole layout
            'add remove change reset': 'render',
        },
        className: function(){
            return this.collection.some(this.filter) ? '' : 'hidden';
        },
        onRender: function(){
            if (this.collection.some(this.filter))
                this.$el.removeClass('hidden');
            else
                this.$el.addClass('hidden');
        },
    });

    podItem.ChangedContainersView = ContainersTableBaseView.extend({
        template: pageContainersChangedTpl,
        filter: function(model){
            return !model.get('before') || !model.get('after')
                || model.get('before').isChanged(model.get('after'));
        },
    });

    podItem.UnchangedContainersView = ContainersTableBaseView.extend({
        template: pageContainersUnchangedTpl,
        filter: function(model){
            return model.get('before') && model.get('after')
                && !model.get('before').isChanged(model.get('after'));
        },
        templateHelpers: function(){
            return {
                partial: this.collection.some(_.negate(this.filter)),
            };
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
                this.changed.show(new podItem.ChangedContainersView({collection: this.collection}));
                this.unchanged.show(new podItem.UnchangedContainersView({collection: this.collection}));
            });
        },
    });

    podItem.ControlsPanel = Backbone.Marionette.ItemView.extend({
        template: podItemControlsTpl,
        tagName: 'div',
        className: 'pod-controls',

        ui: {
            close : 'span.close',
            message: '.message-wrapper'
        },
        onShow: function(){
            if (this.model.get('postDescription'))
                this.ui.close.parents('.message-wrapper').slideDown();
        },

        events: {
            'click .start-btn'        : 'startItem',
            'click .pay-and-apply'    : 'applyChanges',
            'click .apply'            : 'applyChanges',
            'click .reset-changes'    : 'resetChanges',
            'click .pay-and-start-btn': 'payStartItem',
            'click .restart-btn'      : 'restartItem',
            'click .stop-btn'         : 'stopItem',
            'click .terminate-btn'    : 'terminateItem',
            'click @ui.close'         : 'closeMessage'
        },

        modelEvents: {
            'change': 'render',
        },

        initialize: function(options){
            this.graphs = !!options.graphs;
            this.upgrade = !!options.upgrade;
            this.fixedPrice = !!options.fixedPrice;
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
                }),
                postDesc = this.model.get('postDescription'),
                changed = this.model.isChanged(this.model.get('edited_config')),
                changesRequirePayment;

            this.model.recalcInfo(pkg);

            if (this.model.get('edited_config')){
                this.model.get('edited_config').recalcInfo(pkg);
                var diff = this.model.get('edited_config').rawTotalPrice - this.model.rawTotalPrice;
                if (diff > 0)
                    changesRequirePayment = pkg.getFormattedPrice(diff);
            }

            return {
                changesRequirePayment: changesRequirePayment,
                fixedPrice           : this.fixedPrice,
                changed         : changed,
                hasPorts        : hasPorts,
                postDescription : this.preparePostDescription(postDesc),
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
            };
        },

        onDomRefresh: function(){
            if (this.model.get('postDescription') || this.model.get('edited_config'))
                this.ui.message.show();
        },

        closeMessage: function(){
            var model = this.model;
            this.ui.close.parents('.message-wrapper').slideUp({
                complete: function(){
                    model.unset('postDescription');
                    model.command('set', {postDescription: null});
                }
            });
        },

        startItem: function(){ this.model.cmdStart(); },
        payStartItem: function(){ this.model.cmdPayAndStart(); },
        restartItem: function(){ this.model.cmdRestart(); },
        stopItem: function(){ this.model.cmdStop(); },
        terminateItem: function(){ this.model.cmdDelete(); },
        applyChanges: function(){
            utils.preloader.show();
            this.model.cmdApplyChanges()
                .always(utils.preloader.hide)
                .done(function(){
                    utils.notifyWindow('Pod will be restarted with the new '
                                       + 'configuration soon', 'success');
                });
        },
        resetChanges: function(){
            var model = this.model,
                oldEdited = model.get('edited_config');
            utils.modalDialog({
                title: 'Are you sure?',
                body: 'Reset all unapplied changes?',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        model.set('edited_config', null).command('edit')
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow,
                                  function(){ model.set('edited_config', oldEdited); });
                    },
                    buttonCancel: true,
                    buttonOkText: 'Reset',
                }
            });
        },

        preparePostDescription: function(val){
            if (val == null)
                return;
            val = val.replace(/(%PUBLIC_ADDRESS%)/gi,
                              this.model.get('public_ip') || '...');
            var parser = new BBCodeParser(BBCodeParser.defaultTags());
            return parser.parseString(val);
        }
    });

    podItem.PodGraphItem = Backbone.Marionette.ItemView.extend({
        template: podItemGraphTpl,

        initialize: function(options){ this.pod = options.pod; },

        ui: {
            chart: '.graph-item'
        },

        onShow: function(){
            var lines = this.model.get('lines'),
                running = this.pod.get('status') === 'running',
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
                    indicator: !running ? 'Pod is not running...' :
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
            if (this.model.get('points').length == 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                var time = App.currentUser.localizeDatetime(record[0]);
                for (var i=0; i<lines; i++)
                    points[i].push([time, record[i+1]]);
            });
            this.ui.chart.jqplot(points, options);
        }
    });

    podItem.PodGraph = Backbone.Marionette.CollectionView.extend({
        childView: podItem.PodGraphItem,
        childViewOptions: function() {
            return {pod: this.model};
        },

        modelEvents: {
            'change': 'render'
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
            var image = /^(.+?)(?::([^/:]+))?$/.exec(this.model.get('image')),
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
                        if(xhr.data.status.toLowerCase() == 'paid'){
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
                            utils.notifyWindow('Pod will be upgraded.', 'success');
                            App.navigate('pods/' + that.model.id, {trigger: true});
                        });
                }
            });
        },
    });

    return podItem;
});
