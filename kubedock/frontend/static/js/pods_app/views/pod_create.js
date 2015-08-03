define(['pods_app/app',
        'tpl!pods_app/templates/layout_wizard.tpl',
        'tpl!pods_app/templates/breadcrumb_header.tpl',
        'tpl!pods_app/templates/wizard_image_collection_item.tpl',
        'tpl!pods_app/templates/wizard_get_image.tpl',
        'tpl!pods_app/templates/wizard_set_container_ports.tpl',
        'tpl!pods_app/templates/wizard_set_container_env.tpl',
        'tpl!pods_app/templates/wizard_set_container_logs.tpl',
        'tpl!pods_app/templates/wizard_set_container_stats.tpl',
        'tpl!pods_app/templates/pod_item_graph.tpl',
        'tpl!pods_app/templates/wizard_set_container_complete.tpl',
        'pods_app/utils',
        'scroll-model', 'scroll-view', 'bootstrap', 'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer', 'numeral'],
       function(Pods,
                layoutWizardTpl,
                breadcrumbHeaderTpl,
                wizardImageCollectionItemTpl,
                wizardGetImageTpl,
                wizardSetContainerPortsTpl,
                wizardSetContainerEnvTpl,
                wizardSetContainerLogsTpl,
                wizardSetContainerStatsTpl,
                podItemGraphTpl,
                wizardSetContainerCompleteTpl,
                utils){

    Pods.module('Views.NewItem', function(NewItem, App, Backbone, Marionette, $, _){

        NewItem.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
            template: layoutWizardTpl,
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
                    that.listenTo(view, 'step:statsconf', that.statsConf);
                    that.listenTo(view, 'step:logsconf', that.logsConf);
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
            imageSelected: function(image, url){
                this.trigger('image:selected', image, url);
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
            statsConf: function(data){
                this.trigger('step:statsconf', data.model);
            },
            logsConf: function(data){
                this.trigger('step:logsconf', data.model);
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

        NewItem.PodHeaderView = Backbone.Marionette.ItemView.extend({
            template: breadcrumbHeaderTpl,
            tagName: 'div',

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
                    success: function(response, newValue) {
                        that.model.set({name: newValue});
                    },
                    validate: function(newValue) {
                        var model = App.WorkFlow.getCollection().find(
                            function(item) {
                                return item.get('name') == newValue;
                            }
                        );
                        if (model) {
                            return 'Pod with name "' + newValue +
                                '" already exists. Try another name.'
                        }
                    }
                });
            }
        });

        NewItem.ImageListItemView = Backbone.Marionette.ItemView.extend({
            template: wizardImageCollectionItemTpl,
            tagName: 'div',
            className: 'item',

            events: {
                'click .add-item'  : 'addItem',
            },

            addItem: function(evt){
                evt.stopPropagation();
                // it is used?
                this.trigger('image:selected');
            }
        });

        var imageSearchURL = 'registry.hub.docker.com';
        NewItem.GetImageView = Backbone.Marionette.CompositeView.extend({
            template: wizardGetImageTpl,
            childView: NewItem.ImageListItemView,
            childViewContainer: '#data-collection',
            tagName: 'div',

            initialize: function(options){
                this.collection = new App.Data.ImageCollection();
                this.listenTo(this.collection, 'reset', this.render);
            },

            triggers: {
                'click .next-step' : 'step:next'
            },

            events: {
                'click .search-image'              : 'onSearchClick',
                'keypress #search-image-field'     : 'onInputKeypress',
                'click #search-image-default-repo' : 'onChangeRepoURL',
                'click @ui.buttonNext'             : 'nextStep',
                'change @ui.select'                : 'selectChanche'
            },

            childEvents: {
                'image:selected' : 'childImageSelected'
            },

            ui: {
                buttonNext      : '.nextStep',
                repo_url_repr   : 'span#search-image-default-repo',
                input           : 'input#search-image-field',
                spinner         : '#data-collection',
                searchControl   : '.search-control',
                loginForm       : '.login-user',
                select          : '.image-source'
            },

            onRender: function(){
                var that = this;
                this.ui.repo_url_repr.editable({
                    type: 'text',
                    title: 'Change repository url',
                    success: function(response, newValue) {
                        imageSearchURL = newValue;
                        that.ui.repo_url_repr.text(imageSearchURL);
                    }
                });
            },

            onInputKeypress: function(evt){
                evt.stopPropagation();
                if (evt.which === 13) { // 'Enter' key
                    this.fetchCollection(this.ui.input.val().trim());
                }
            },

            onSearchClick: function(evt){
                evt.stopPropagation();
                this.ui.searchControl.show();
                this.fetchCollection(this.ui.input.val().trim());

            },
            selectChanche: function(evt){
                var index = this.ui.select.find('option:selected').index();
                if (index == 1){
                    this.ui.loginForm.slideDown();
                } else {
                    this.ui.loginForm.slideUp();
                }
            },

            fetchCollection: function(query){
                var that = this;
                var options = {
                    columnsSelector: "#data-collection",
                    itemTemplateSelector: "#image-collection-item-template",
                    itemClasses: "item",
                    dataUrl: "/api/images/search",
                    disableAutoscroll: true,
                    requestData: {searchkey: query, url: imageSearchURL},
                    onAddItem: function(count, $col, $item, data){
                        $item.find('.add-item').on('click', function() {
                            that.trigger('image:selected', data.name, data.url);
                        });
                        return $item;
                    }
                };
                var scrollModel = new ScrollModel({options: options});
                new ScrollView({
                    el: $("#search-results-scroll"),
                    model: scrollModel,
                    options: options
                });
            },

            onShow: function(){
                this.ui.input.focus();
            },

            nextStep : function(evt){
                // it is used?
                this.trigger('image:selected', this.ui.buttonNext.data('name'));
            },

            onBeforeDestroy: function(){
                this.trigger('pager:clear');
            },

            childImageSelected: function(data){
                // it is used?
                this.trigger('image:selected', data.model.get('name'));
            }
        });

        NewItem.WizardPortsSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerPortsTpl,
            tagName: 'div',


            ui: {
                ieditable      : '.ieditable',
                iseditable     : '.iseditable',
                iveditable     : '.iveditable',
                addPort        : '.add-port',
                addDrive       : '.add-drive',
                nextStep       : '.next-step',
                persistent     : '.persistent',
                addVolume      : '.add-volume',
                removePort     : '.remove-port',
                'public'         : 'input.public',
                input_command  : 'input.command',
                removeVolume   : '.remove-volume',
                restartPolicy  : '.restart-policy',
                addDriveCancel : '.add-drive-cancel',
                containerPort  : '.containerPort',
                podPorts       : '.hostPort'
            },

            events: {
                'click @ui.nextStep'       : 'goNext',
                'click @ui.addPort'        : 'addItem',
                'click @ui.addDrive'       : 'addDrive',
                'click @ui.addVolume'      : 'addVolume',
                'click @ui.public'         : 'togglePublic',
                'click @ui.addDriveCancel' : 'cancelAddDrive',
                'click @ui.removePort'     : 'removePortEntry',
                'click @ui.persistent'     : 'togglePersistent',
                'click @ui.removeVolume'   : 'removeVolumeEntry',
                'change @ui.restartPolicy' : 'changePolicy',
                'change @ui.input_command' : 'changeCommand',
            },

            triggers: {
                'click .complete'        : 'step:complete',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-envs'      : 'step:envconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf',
                'click .go-to-logs'      : 'step:logsconf',
            },

            changePolicy: function(evt){
                evt.stopPropagation();
                this.model.set('restartPolicy', $(evt.target).val())
            },

            changeCommand: function(evt){
                evt.stopPropagation();
                var cmd = $(evt.target).val();
                if (cmd != '') {
                    this.model.set('command', [cmd])
                }
            },

            templateHelpers: function(){
                var model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID')),
                    kubeType;
                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }

                return {
                    isPending: !this.model.has('parentID'),
                    hasPersistent: this.model.has('persistentDrives'),
                    showPersistentAdd: this.hasOwnProperty('showPersistentAdd'),
                    ip: this.model.get('ip'),
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                    podName: model !== undefined ? model.get('name') : '',
                };
            },

            initialize: function(options){
                var image = options.model.get('lastAddedImage');
                if (image === undefined) {
                    this.model = options.model
                } else {
                    this.model = new App.Data.Image(_.last(options.model.get('containers')));
                }
                if (!this.model.has('volumeMounts')) {
                    this.model.set({'volumeMounts': []});
                }
                this.modelOptions = options;
            },

            addItem: function(evt){
                evt.stopPropagation();
                this.model.get('ports').push({containerPort: null, hostPort: null, protocol: 'tcp', isPublic: false});
                this.render();
            },

            addVolume: function(evt){
                evt.stopPropagation();
                this.model.get('volumeMounts').push({mountPath: null, readOnly: false, isPersistent: false});
                this.render();
            },

            addDrive: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target);
                if (this.hasOwnProperty('showPersistentAdd')) {
                    var cells = tgt.closest('div').children('span'),
                        pdName = cells.eq(0).children('input').first().val().trim(),
                        pdSize = parseInt(cells.eq(1).children('input').first().val().trim());
                    this.model.get('persistentDrives').push({pdName: pdName, pdSize: pdSize});
                    this.persistentDefault = pdName;
                    if (this.hasOwnProperty('currentIndex')) {
                        this.model.get('volumeMounts')[this.currentIndex].persistentDisk = {pdName: pdName, pdSize: pdSize};
                    }
                    delete this.showPersistentAdd;
                }
                else {
                    this.showPersistentAdd = true;
                    this.currentIndex = tgt.closest('tr').index();
                }
                this.render();
            },

            cancelAddDrive: function(evt){
                evt.stopPropagation();
                if (this.hasOwnProperty('showPersistentAdd')) {
                    delete this.showPersistentAdd;
                }
                this.render();
            },

            togglePublic: function(evt){
                evt.stopPropagation();
                var index = $(evt.target).closest('tr').index(),
                    entry = this.model.get('ports')[index];
                if (entry.isPublic) {
                    entry.isPublic = false;
                }
                else {
                    entry.isPublic = true;
                }
                this.render();
            },

            togglePersistent: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    index = tgt.closest('tr').index(),
                    row = this.model.get('volumeMounts')[index],
                    that = this;
                if (row.isPersistent) {
                    row.isPersistent = false;
                    to_be_released = _.filter(this.model.get('persistentDrives'), function(d){
                    if (row.hasOwnProperty('persistentDisk')) {
                        return row.persistentDisk.pdName === d.pdName;
                    }
                    return false;
                });
                _.each(to_be_released, function(d){ delete d.used; });
                    this.render();
                }
                else {
                    if (!this.model.has('persistentDrives')) {
                        var rqst = $.ajax({
                            type: 'GET',
                            url: '/api/nodes/lookup'
                        });
                        rqst.done(function(rs){
                            that.model.set({persistentDrives: _.map(rs['data'], function(i){return {pdName: i, pdSize: null}})});
                            row.isPersistent = true;
                            row.persistentDisk = {pdName: null};
                            that.render();
                        });
                    }
                    else {
                        row.isPersistent = true;
                        row.persistentDisk = {pdName: null};
                        that.render();
                    }
                }
            },

            removePortEntry: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    index = tgt.closest('tr').index(),
                    ports = this.model.get('ports');
                ports.splice(index, 1);
                this.render();
            },

            removeVolumeEntry: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    index = tgt.closest('tr').index(),
                    volumes = this.model.get('volumeMounts');
                to_be_released = _.filter(this.model.get('persistentDrives'), function(d){
                    if (volumes[index].hasOwnProperty('persistentDisk')) {
                        return volumes[index].persistentDisk.pdName === d.pdName;
                    }
                    return false;
                });
                _.each(to_be_released, function(d){ delete d.used; });
                volumes.splice(index, 1);
                this.render();
            },

            goNext: function(evt){
                var that = this,
                    podContainersPorts = [],
                    uniqueContainerPorts = [],
                    podContainersHostPorts = [],
                    uniqueContainerHostPorts = [],
                    vm = this.model.get('volumeMounts'),
                    containers = this.modelOptions.model.get('containers');

                /* mountPath check */
                for (var i=0; i<vm.length; i++) {
                    if (!vm[i].mountPath) {
                        utils.modelError('Mount path must be set!');
                        return;
                    }
                    var itemName = vm[i].mountPath.charAt(0) === '/' ? vm[i].mountPath.substring(1) : vm[i].mountPath;
                    vm[i].name = itemName.replace(new RegExp('/','g'), '-') + _.map(_.range(10), function(i){return _.random(1, 10);}).join('');
                };

                /* check ports */
                _.each(containers, function(container){
                    _.filter(container.ports, function(item){return item});
                    _.each(container.ports, function(item){
                        var port = parseInt(item.containerPort,10),
                            hostPort = parseInt(item.hostPort,10);

                        if (port) podContainersPorts.push(port);
                        if (hostPort) podContainersHostPorts.push(hostPort);
                    })
                })

                uniqueContainerPorts = _.uniq(podContainersPorts);
                uniqueContainerHostPorts = _.uniq(podContainersHostPorts);

                if (podContainersPorts.length != uniqueContainerPorts.length){
                    utils.modelError('You have a duplicate container port in ' + this.model.get('name') + ' container!');
                }  else if (podContainersHostPorts.length != uniqueContainerHostPorts.length){
                    utils.modelError('You have a duplicate pod port in ' + this.model.get('name') + ' container!');
                } else {
                    this.trigger('step:envconf', this);
                }
            },

            onRender: function(){
                var that = this,
                    disks = [];

                this.ui.input_command.val(this.filterCommand(this.model.get('command')));

                if (this.model.has('persistentDrives')) {
                    disks = _.map(this.model.get('persistentDrives'), function(i){
                        var item = {value: i.pdName, text: i.pdName};
                        if (i.hasOwnProperty('used')) { item.disabled = true; }
                        return item;
                    });
                }

                this.ui.ieditable.editable({
                    type: 'text',
                    mode: 'inline',
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index(),
                            className = $(this).parent().attr('class'),
                            item = $(this);

                        if (className !== undefined) {
                            that.model.get('ports')[index][className] = parseInt(newValue);
                        }
                        else if (item.hasClass('mountPath')) {
                            that.model.get('volumeMounts')[index]['mountPath'] = newValue;
                        }
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
                this.ui.iveditable.editable({
                    type: 'select',
                    value: null,
                    source: disks,
                    mode: 'inline',
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index(),
                            entry = that.model.get('volumeMounts')[index],
                            pEntry = _.filter(that.model.get('persistentDrives'), function(i){ return i.pdName === newValue; })[0];
                        entry['persistentDisk'] = pEntry;
                        pEntry['used'] = true;
                    }
                });
            },
            filterCommand: function(command) {
                command = _.map(command, function(e) {
                    return e.indexOf(' ') > 0 ? '"' + e + '"': e;
                });
                return command.join(' ');
            }
        });

        NewItem.WizardEnvSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerEnvTpl,
            tagName: 'div',

            ui: {
                ieditable  : '.ieditable',
                table      : '#data-table',
                reset      : '.reset-button',
                input      : '.change-input',
                addItem    : '.add-env',
                removeItem : '.remove-env',
                nameField  : '.name',
            },

            events: {
                'click @ui.addItem'    : 'addItem',
                'click @ui.removeItem' : 'removeItem',
                'click @ui.reset'      : 'resetFielsdsValue',
                'change @ui.input'     : 'onChangeInput',
                'change @ui.nameField' : 'validation',
            },


            templateHelpers: function(){
                var model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID')),
                    kubeType;
                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }

                return {
                    isPending: !this.model.has('parentID'),
                    hasPersistent: this.model.has('persistentDrives'),
                    showPersistentAdd: this.hasOwnProperty('showPersistentAdd'),
                    ip: this.model.get('ip'),
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                    podName: model !== undefined ? model.get('name') : '',
                    };
            },

            triggers: {
                'click .complete'        : 'step:complete',
                'click .next-step'       : 'step:complete',
                'click .prev-step'       : 'step:volconf',
                'click .go-to-ports'     : 'step:portconf',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf',
                'click .go-to-logs'      : 'step:logsconf',
            },

            addItem: function(evt){
                evt.stopPropagation();
                var env = this.model.get('env');
                env.push({name: null, value: null});
                this.render();
            },

            validation: function(){
                var valName = this.ui.nameField.val();

                if (!/^[a-zA-Z][a-zA-Z0-9-_\.]/.test(valName)){
                    alert('First symbol must be letter');
                    this.ui.nameField.val('');
                    return false;
                };
            },
            removeItem: function(evt){
                var env = this.model.get('env'),
                    item = $(evt.target);
                    index = item.parents('tr').index();
                    item.parents('tr').remove();
                    env.splice(index, 1);

                    this.render();
            },

            resetFielsdsValue: function(){
                var env = this.model.get('env');

                env.forEach(function(item, i){
                    env[i] = {name: null, value: null}
                })
                this.render();
            },

            onChangeInput: function(evt){
                var env = this.model.get('env'),
                    tgt = $(evt.target),
                    row = tgt.closest('tr'),
                    index = row.index();
                if (tgt.hasClass('name')) {
                    env[index].name = tgt.val().trim();
                }
                else if (tgt.hasClass('value')) {
                    env[index].value = tgt.val().trim();
                }
            },
        });

        NewItem.WizardStatsSubItemView = Backbone.Marionette.ItemView.extend({
            template: podItemGraphTpl,

            ui: {
                chart: '.graph-item'
            },

            onShow: function(){
                var lines = this.model.get('lines');
                var options = {
                    title: this.model.get('title'),
                    axes: {
                        xaxis: {label: 'time', renderer: $.jqplot.DateAxisRenderer},
                        yaxis: {label: this.model.get('ylabel')}
                    },
                    seriesDefaults: {
                        showMarker: false,
                        rendererOptions: {
                            smooth: true
                        }
                    },
                    grid: {
                        background: '#ffffff',
                        drawBorder: false,
                        shadow: false
                    }
                };

                var points = [];
                for (var i=0; i<lines; i++) {
                    if (points.length < i+1) {
                        points.push([])
                    }
                }

                this.model.get('points').forEach(function(record){
                    for (var i=0; i<lines; i++) {
                        points[i].push([record[0], record[i+1]])
                    }
                });
                this.ui.chart.jqplot(points, options);
            }
        });

        NewItem.WizardStatsSubView = Backbone.Marionette.CompositeView.extend({
            childView: NewItem.WizardStatsSubItemView,
            childViewContainer: "div.container-stats #monitoring-page",
            template: wizardSetContainerStatsTpl,
            tagName: 'div',

            initialize: function(options){
                this.containerModel = options.containerModel;
            },

            events: {
                'click .go-to-ports'     : 'onPortsClick',
                'click .go-to-volumes'   : 'onVolumesClick',
                'click .go-to-envs'      : 'onEnvsClick',
                'click .go-to-resources' : 'onResClick',
                'click .go-to-other'     : 'onOtherClick',
                'click .go-to-logs'      : 'onLogsClick'
            },


            templateHelpers: function(){
                var parentID = this.containerModel.get('parentID'),
                    model = App.WorkFlow.getCollection().fullCollection.get(parentID),
                    kubeType;
                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }

                return {
                    parentID: parentID,
                    isPending: !this.containerModel.has('parentID'),
                    image: this.containerModel.get('image'),
                    name: this.containerModel.get('name'),
                    state: this.containerModel.get('state'),
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                    kubes: this.containerModel.get('kubes'),
                    podName: model !== undefined ? model.get('name') : '',
                };

            },

            onPortsClick: function(evt){
                evt.stopPropagation();
                this.trigger('step:portconf', {model: this.containerModel});
            },

            onVolumesClick: function(evt){
                evt.stopPropagation();
                this.trigger('step:volconf', {model: this.containerModel});
            },

            onEnvsClick: function(evt){
                evt.stopPropagation();
                this.trigger('step:envconf', {model: this.containerModel});
            },

            onResClick: function(evt){
                evt.stopPropagation();
                this.trigger('step:resconf', {model: this.containerModel});
            },

            onOtherClick: function(evt){
                evt.stopPropagation();
                this.trigger('step:otherconf', {model: this.containerModel});
            },

            onLogsClick: function(evt){
                evt.stopPropagation();
                this.trigger('step:logsconf', {model: this.containerModel});
            }
        });

        NewItem.WizardLogsSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerLogsTpl,
            tagName: 'div',

            ui: {
                ieditable : '.ieditable',
                textarea  : '.container-logs',
                stopItem  : '#stopContainer',
                startItem : '#startContainer',
            },

            events: {
                'click @ui.stopItem'  : 'stopItem',
                'click @ui.startItem' : 'startItem',
            },

            templateHelpers: function(){
                var model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID')),
                    kubeType;
                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }
                return {
                    isPending: !this.model.has('parentID'),
                    podName: model !== undefined ? model.get('name') : '',
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                };
            },

            triggers: {
                'click .go-to-ports'     : 'step:portconf',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-envs'      : 'step:envconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf'
            },

            initialize: function() {
                this.model.set('logs', []);
                function get_logs() {
                    var parent_id = this.model.get('parentID'),
                        parent_model = App.WorkFlow.getCollection().fullCollection.get(parent_id),
                        node = parent_model.get('host'),
                        index = 'docker-*',
                        container_id = this.model.get('containerID'),
                        size = 100,
                        url = '/logs/' + node + '/' + index +
                            '/_search?q=container_id:"' + container_id + '"' +
                            '&size=' + size + '&sort=@timestamp:desc';
                    $.ajax({
                        url: url,
                        dataType : 'json',
                        context: this,
                        success: function(data) {
                            var lines = _.map(data['hits']['hits'], function(line) {
                                return line['_source'];
                            });
                            lines.reverse();
                            this.model.set('logs', lines);
                            this.render();
                            _.defer(function(caller){
                                caller.ui.textarea.scrollTop(caller.ui.textarea[0].scrollHeight);
                            }, this);
                        }
                    });
                    this.model.set('timeout', setTimeout($.proxy(get_logs, this), 10000));
                }
                $.proxy(get_logs, this)();
            },

            command: function(evt, cmd){
                var that = this,
                    preloader = $('#page-preloader');
                preloader.show();
                evt.stopPropagation();
                var model = App.WorkFlow.getCollection().fullCollection.get(
                    this.model.get('parentID')),
                    _containers = [],
                    host = null;
                _.each(model.get('containers'), function(itm){
                    if(itm.name == that.model.get('name'))
                        _containers.push(itm.containerID);
                        host = model.get('host');
                });

                $.ajax({
                    url: '/api/podapi/' + model.get('id'),
                    data: {command: cmd, host: host, containers: _containers.join(',')},
                    type: 'PUT',
                    dataType: 'JSON',
                    success: function(rs){
                        preloader.hide();
                    },
                    error: function(xhr){
                        utils.modelError(xhr);
                    }
                });

                //$.ajax({
                //    url: '/api/pods/containers',
                //    data: {action: cmd, host: host, containers: _containers.join(','),
                //           pod_uuid: model.get('id')},
                //    type: 'PUT',
                //    dataType: 'JSON',
                //    success: function(rs){
                //        preloader.hide();
                //    },
                //    error: function(xhr){
                //        modelError(xhr);
                //    }
                //});
            },

            startItem: function(evt){
                this.command(evt, 'start');
            },
            stopItem: function(evt){
                this.command(evt, 'stop');
            },
            onBeforeDestroy: function () {
                clearTimeout(this.model.get('timeout'));
            },
        });

        NewItem.WizardCompleteSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerCompleteTpl,
            tagName: 'div',

            templateHelpers: function() {
                this.package = this.getUserPackage();

                var isPublic = isPerSorage = false,
                    containers = this.model.get('containers');

                _.each(containers, function(container){
                    _.each(container.ports, function(port){
                        if (port.isPublic) isPublic = true
                    })
                    _.each(container.volumeMounts, function(volume){
                        if (volume.isPersistent) isPerSorage = true
                    })
                })

                return {
                    isPublic : isPublic,
                    isPerSorage : isPerSorage,
                    cpu_data: this.cpu_data,
                    ram_data: this.ram_data,
                    container_price: this.container_price,
                    total_price: this.total_price,
                    kube_types: kubeTypes,
                    restart_policies: {'Always': 'Always', 'Never': 'Never', 'OnFailure': 'On Failure'},
                    restart_policy: this.model.get('restartPolicy'),
                    image_name_id: this.model.get('lastAddedImageNameId'),
                    package: this.package,
                    price_ip: this.getFormattedPrice(this.package.price_ip),
                    price_pstorage: this.getFormattedPrice(this.package.price_pstorage)
                };
            },

            ui: {
                'ieditable'               : '.ieditable',
                'policy'                  : 'select.restart-policy',
                'kubeTypes'               : 'select.kube_type',
                'kubeQuantity'            : 'select.kube-quantity',
                'editPolicy'              : '.edit-policy',
                'editPolycyDescription'   : '.edit-polycy-description',
                'editKubeType'            : '.edit-kube-type',
                'editKubeTypeDescription' : '.edit-kube-type-description',
                'main'                    : '#add-image',
                'selectpicker'            : '.selectpicker',
            },

            events: {
                'click .delete-item'     : 'deleteItem',
                'click .cluster'         : 'toggleCluster',
                'click .node'            : 'toggleNode',
                'change .replicas'       : 'changeReplicas',
                'change .kube_type'      : 'changeKubeType',
                'change .kube-quantity'  : 'changeKubeQuantity',
                'change @ui.policy'      : 'changePolicy',
                'click @ui.editPolicy'   : 'editPolicy',
                'click @ui.editKubeType' : 'editKubeType',
            },

            triggers: {
                'click .add-more'           : 'step:getimage',
                'click .prev-step'          : 'step:envconf',
                'click .save-container'     : 'pod:save',
                'click .save-run-container' : 'pod:run',
            },

            deleteItem: function(evt){
                evt.stopPropagation();
                var name = $(evt.target).closest('tr').children('td:first').attr('id');
                this.model.attributes.containers = _.filter(this.model.get('containers'),
                function(i){ return i.name !== this.name }, {name: name});
                delete this.container_price;
                delete this.cpu_data;
                this.render();
            },

            toggleCluster: function(evt){
                evt.stopPropagation();
                if (this.model.get('replicationController')) {
                    this.model.set('replicationController', false);
                }
                else {
                    var obj = {replicationController: true};
                    this.model.set(obj);
                }
                this.render();
            },

            toggleNode: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    node = tgt.closest('td').next('td').text().trim();
                this.model.set('node', node);
                this.render();
            },

            changeReplicas: function(evt){
                evt.stopPropagation();
                this.model.set('replicas', parseInt($(evt.target).val().trim()));
            },

            changeKubeQuantity: function(evt){
                evt.stopPropagation();
                var num = parseInt(evt.target.value),
                    kube_id = parseInt(this.ui.kubeTypes.find(':selected').val()),
                    containers = this.model.get('containers'),
                    image_name_id = this.ui.main.attr('image_name_id'),
                    container = _.find(containers, function(c) { return c.name == image_name_id }),
                    container = container ? container : _.last(containers),
                    kube_price = this.getKubePrice(kube_id);
                container.kubes = num;
                this.container_price = this.getFormattedPrice(kube_price * num);
                this.total_price = this.getFormattedPrice(_.reduce(containers,
                    function(sum, c) { return sum + kube_price * c.kubes; }, 0));
                this.render();
                this.ui.kubeTypes.val(kube_id);
                this.ui.kubeQuantity.val(num);
                $('.kube-quantity button span').text(num);
            },

            changeKubeType: function(evt){
                this.model.set('kube_type', parseInt(evt.target.value));
                evt.stopPropagation();
                var kube_id = parseInt(evt.target.value),
                    num = parseInt(this.ui.kubeQuantity.find(':selected').text()),
                    containers = this.model.get('containers'),
                    kube_data = _.find(kubeTypes, function(k){
                        return k.id === kube_id
                    }),
                    kube_price = this.getKubePrice(kube_id);
                this.model.set('kube_type', kube_id);
                if (kube_data.length === 0) {
                    this.cpu_data = '0 Cores';
                    this.ram_data = '0 MB';
                } else {
                    this.cpu_data = kube_data.cpu + ' Cores';
                    this.ram_data = kube_data.memory + ' ' + kube_data.memory_units;
                }
                this.container_price = this.getFormattedPrice(kube_price * num);
                this.total_price = this.getFormattedPrice(_.reduce(containers,
                    function(sum, c) { return sum + kube_price * c.kubes; }, 0));
                this.render();
                this.ui.kubeTypes.val(kube_id);
                this.ui.kubeQuantity.val(num);
                $('.kube-quantity button span').text(num);
            },

            changePolicy: function(evt){
                evt.stopPropagation();
                var restart_policy = $(evt.target).val();
                this.model.set('restartPolicy', restart_policy)
                if (restart_policy == 'Always') {
                    this.model.set('replicationController', true);
                } else {
                    this.model.set('replicationController', false);
                }
            },

            getKubePrice: function(kubeId) {
                var packageId = this.package.id;
                var packageKube = _.find(packageKubes, function(p) {
                    return p.package_id == packageId && p.kube_id == kubeId;
                });

                return packageKube ? packageKube.kube_price : 0;
            },

            getUserPackage: function() {
                return _.find(packages, function(p) {  // 'packages' && 'userPackage' is taken from index.html
                    return p.id === userPackage
                })
            },

            getFormattedPrice: function(price, format) {
                format = typeof format !== 'undefined' ? format : '0.00';
                return this.package.prefix + numeral(price).format(format) + this.package.suffix;
            },

            onRender: function() {
                if (!this.model.get('kube_type'))
                    this.model.set('kube_type', parseInt(kubeTypes[0].id));
                if(!this.container_price) {
                    this.$('.kube-quantity').trigger('change');
                }
                if(!this.cpu_data) {
                    this.$('.kube_type').trigger('change');
                }
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
                            that.model.set('port', parseInt(newValue));
                        }
                        else {
                            console.log('oops!');
                        }
                    }
                });
                this.ui.selectpicker.selectpicker();
            },

            editPolicy: function(){
                this.ui.editPolicy.hide();
                this.ui.editPolycyDescription.hide()
                this.ui.policy.attr('disabled',false);
                this.$('.policy .disabled').removeClass('disabled');
            },

            editKubeType: function(){
                this.ui.editKubeType.hide();
                this.ui.editKubeTypeDescription.hide()
                this.ui.kubeTypes.attr('disabled',false);
                this.$('.kube-type-wrapper .disabled').removeClass('disabled');
            },
        });

    });

    return Pods.Views.NewItem;
});
