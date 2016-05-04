define(['app_data/app', 'app_data/model',
        'tpl!app_data/pods/templates/layout_wizard.tpl',
        'tpl!app_data/pods/templates/breadcrumb_header.tpl',
        'tpl!app_data/pods/templates/wizard_image_collection_item.tpl',
        'tpl!app_data/pods/templates/wizard_get_image.tpl',

        'tpl!app_data/pods/templates/wizard_set_container_pending_basic_settings.tpl',
        'tpl!app_data/pods/templates/editable_ports/list.tpl',
        'tpl!app_data/pods/templates/editable_ports/item.tpl',
        'tpl!app_data/pods/templates/editable_ports/empty.tpl',
        'tpl!app_data/pods/templates/editable_volume_mounts/list.tpl',
        'tpl!app_data/pods/templates/editable_volume_mounts/item.tpl',
        'tpl!app_data/pods/templates/editable_volume_mounts/empty.tpl',

        'tpl!app_data/pods/templates/wizard_set_container_settled_basic_settings.tpl',
        'tpl!app_data/pods/templates/wizard_set_container_env.tpl',
        'tpl!app_data/pods/templates/wizard_set_container_logs.tpl',
        'tpl!app_data/pods/templates/wizard_set_container_stats.tpl',
        'tpl!app_data/pods/templates/pod_item_graph.tpl',
        'tpl!app_data/pods/templates/wizard_set_container_complete.tpl',
        'app_data/utils',
        'bootstrap', 'bootstrap-editable', 'jqplot',
        'jqplot-axis-renderer', 'nicescroll', 'numeral', 'selectpicker', 'tooltip'],
       function(App, Model,
                layoutWizardTpl,
                breadcrumbHeaderTpl,
                wizardImageCollectionItemTpl,
                wizardGetImageTpl,

                wizardSetContainerPendingBasicSettingsTpl,
                portListTpl,
                portListItemTpl,
                portListEmptyTpl,
                volumeMountListTpl,
                volumeMountListItemTpl,
                volumeMountListEmptyTpl,

                wizardSetContainerSettledBasicSettingsTpl,
                wizardSetContainerEnvTpl,
                wizardSetContainerLogsTpl,
                wizardSetContainerStatsTpl,
                podItemGraphTpl,
                wizardSetContainerCompleteTpl,
                utils){

    var newItem = {};

    newItem.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: layoutWizardTpl,
        initialize: function(){
            var that = this;
            this.listenTo(this.steps, 'show', function(view){
                that.listenTo(view, 'image:selected', that.imageSelected);
                that.listenTo(view, 'image:fetched', that.imageFetched);
                that.listenTo(view, 'pager:clear', that.clearPager);
                that.listenTo(view, 'pod:save', that.podSave);
                that.listenTo(view, 'pod:pay_and_run', that.podPayAndRun);
                that.listenTo(view, 'image:searchsubmit', that.imageSearchSubmit);
                that.listenTo(view, 'image:getnextpage', that.imageGetNextPage);

                // NOTE: Container to operate with will be choosen in this way:
                // in create pod workflow, will be used podModel.lastEditedContainer
                // in show pod container workflow, will be used container model from controller
                // TODO: can we remove it?
                _([
                    'step:getimage',
                    'step:portconf',
                    'step:volconf',
                    'step:envconf',
                    'step:resconf',
                    'step:otherconf',
                    'step:statsconf',
                    'step:logsconf',
                    'step:complete',
                ]).each(function(name){
                    that.listenTo(view, name, _.bind(that.trigger, that, name));
                });
            });
        },
        regions: {
            nav    : '#navbar-steps',
            header : '#header-steps',
            steps  : '#steps',
            sidebar: '#sidebar',
            footer : '#footer-steps'
        },
        onBeforeShow: function(){
            utils.preloader.show();
        },
        onShow: function(){
            utils.preloader.hide();
        },
        imageSelected: function(image, auth){
            this.trigger('image:selected', image, auth);
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
        podPayAndRun: function(data){
            this.trigger('pod:pay_and_run', data.model);
        },
        imageSearchSubmit: function(data){
            this.trigger('image:searchsubmit', data);
        },
        imageGetNextPage: function(collection, query){
            this.trigger('image:getnextpage', collection, query);
        }
    });

    newItem.ImageListItemView = Backbone.Marionette.ItemView.extend({
        template: wizardImageCollectionItemTpl,
        tagName: 'div',
        className: 'item',

        triggers: {
            'click .add-item': 'image:selected'
        },
    });

    newItem.GetImageView = Backbone.Marionette.CompositeView.extend({
        template: wizardGetImageTpl,
        childView: newItem.ImageListItemView,
        childViewContainer: '#data-collection',
        tagName: 'div',

        initialize: function(options){
            this.registryURL = options.registryURL;
            this.query = options.query;
            this.pod = options.pod;
        },

        templateHelpers: function(){
            var showPaginator = this.collection.length ? true : false;
            return {
                showPaginator: showPaginator,
                query : this.query,
            };
        },

        ui: {
            username          : '#username',
            cancel            : '.podsList',
            password          : '#password',
            moreImage         : '.btn-more',
            privateWrapper    : '.private',
            loginPrivateUres  : '.login-user',
            selectImage       : '.select-image',
            imageSource       : '.image-source',
            selectpicker      : '.selectpicker',
            searchImageButton : '.search-image',
            loader            : 'div#load-control',
            searchControl     : 'div.search-control',
            privateField      : '#private-image-field',
            input             : 'input#search-image-field',
            label             : 'label.placeholder'
        },

        events: {
            'click @ui.selectImage'       : 'selectImage',
            'click @ui.moreImage'         : 'loadNextPage',
            'click @ui.cancel'            : 'cancel',
            'click @ui.searchImageButton' : 'onSearchClick',
            'keypress @ui.input'          : 'onInputKeypress',
            'keypress @ui.privateField'   : 'selectImageByEnterKey',
            'keypress @ui.username'       : 'selectImageByEnterKey',
            'keypress @ui.password'       : 'selectImageByEnterKey',
            'change @ui.imageSource'      : 'imageSourceOnChange',
        },

        childEvents: {
            'image:selected' : 'childImageSelected'
        },

        onRender: function(){
            this.ui.selectpicker.selectpicker();
        },

        selectImageByEnterKey: function(evt){
            if (evt.which === 13) {  // 'Enter' key
                evt.stopPropagation();
                this.selectImage();
            }
        },

        // image was selected directly by image url
        selectImage: function(){
            var image = this.ui.privateField.val(),
                auth;

            if (image.length === 0) {
                this.ui.privateField.focus();
                utils.notifyWindow('Please, enter image url');
                return;
            }
            if (this.ui.username.val() && this.ui.password.val()) {
                auth = {username: this.ui.username.val(),
                        password: this.ui.password.val()};
            }
            this.trigger('image:selected', image, auth);
        },

        imageSourceOnChange: function(){
            var val = this.ui.imageSource.val();
            if (val == "Docker Hub"){
                this.ui.input.parent().show();
                this.ui.privateWrapper.hide();
                this.ui.loginPrivateUres.slideUp();
                this.ui.searchImageButton.parent().show();
                this.ui.label.text('Search images in DockerHub');
            } else if (val == "Other registries"){
                this.ui.input.parent().hide();
                this.ui.privateWrapper.show();
                this.ui.loginPrivateUres.slideDown();
                this.ui.searchImageButton.parent().hide();
                this.ui.privateField.attr('placeholder','registry/namespace/image');
                this.ui.privateField.addClass('private-registry');
                this.ui.label.text('Select image from any registry');
            } else {
                this.ui.input.parent().hide();
                this.ui.privateWrapper.show();
                this.ui.loginPrivateUres.slideDown();
                this.ui.searchImageButton.parent().hide();
                this.ui.privateField.attr('placeholder','namespace/image');
                this.ui.privateField.removeClass('private-registry');
                this.ui.label.text('Select image from DockerHub');
            }
        },

        appendLoader: function(control){
            var loader = $('<div id="load-control" class="btn-more animation">Loading ...</div>');
            if (control === undefined) {
                this.ui.searchControl.empty().append(loader);
            } else {
                control.empty().append(loader);
            }
        },

        removeLoader: function(){
            this.ui.searchControl.empty();
        },

        onInputKeypress: function(evt){
            evt.stopPropagation();
            if (evt.which === 13) { // 'Enter' key
                if (this.ui.input.val().length !== 0){
                    this.appendLoader();
                    this.trigger('image:searchsubmit', this.ui.input.val().trim());
                } else {
                    this.ui.input.focus();
                    utils.notifyWindow('First enter image name or part of image name to search');
                }
            }
        },

        onSearchClick: function(evt){
            evt.stopPropagation();
            if (this.ui.input.val().length !== 0){
                this.appendLoader();
                this.trigger('image:searchsubmit', this.ui.input.val().trim());
            } else {
                this.ui.input.focus();
                utils.notifyWindow('First enter image name or part of image name to search');
            }
        },

        onShow: function(){
            this.ui.input.focus();
        },

        cancel: function(){
            var containers = this.pod.get('containers');
            if (this.pod.lastEditedContainer.isNew) {
                containers.remove(this.pod.lastEditedContainer.id);
                if (!containers.length) {
                    App.navigate('pods', {trigger: true});
                    return;
                }
                this.pod.lastEditedContainer = {id: containers.last().id, isNew: false};
            }
            this.trigger('step:complete');
        },

        childViewOptions: function(){
            var registryURL = this.registryURL;
            return {
                registryURL: registryURL
            };
        },

        // image was selected from search results
        childImageSelected: function(data){
            this.trigger('image:selected', data.model.get('name'));
        },

        loadNextPage: function(){
            this.ui.loader.text('Loading ...').addClass('animation');
            this.trigger('image:getnextpage', this.collection, this.query);
        }
    });

    newItem.WizardGeneralSubView = Backbone.Marionette.ItemView.extend({
        tagName: 'div',
        template: wizardSetContainerSettledBasicSettingsTpl,
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
            'click .go-to-volumes'   : 'step:volconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-resources' : 'step:resconf',
            'click .go-to-other'     : 'step:otherconf',
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

    newItem.WizardPortsSubView = Backbone.Marionette.LayoutView.extend({
        tagName: 'div',
        regions: {
            ports: '#editable-ports-list',
            volumeMounts: '#editable-vm-list',
        },
        template: wizardSetContainerPendingBasicSettingsTpl,
        className: 'container',
        id: 'add-image',

        ui: {
            input          : 'input',
            nextStep       : '.next-step',
            prevStep       : '.prev-step',
            input_command  : 'input.command',
        },

        events: {
            'focus @ui.input'          : 'removeError',
            'click @ui.prevStep'       : 'goBack',
            'click @ui.nextStep'       : 'goNext',
            'change @ui.input_command' : 'changeCommand',
        },

        initialize: function(options) {
            this.pod = this.model.getPod();
        },

        templateHelpers: function(){
            return {
                parentID: this.pod.id,
                volumes: this.pod.get('volumes'),
                updateIsAvailable: this.model.updateIsAvailable,
                kube_type: this.pod.getKubeType(),
                restart_policy: this.pod.get('restartPolicy'),
                podName: this.pod.get('name')
            };
        },

        onBeforeShow: function(){
            this.ports.show(new newItem.PortCollection({
                model: this.model,
                collection: this.model.get('ports')
            }), {replaceElement: true});
            this.volumeMounts.show(new newItem.VolumeMountCollection({
                model: this.model,
                collection: this.model.get('volumeMounts')
            }), {replaceElement: true});
        },

        removeError: function(evt){
            var target = $(evt.target);
            if (target.hasClass('error')) target.removeClass('error');
        },

        changeCommand: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target),
                cmd = tgt.val().trim();
            if (!cmd){
                // Explicitly replace empty command with CMD from image
                // (in case of empty command in container spec, docker will use
                // CMD from image)
                tgt.val(this.filterCommand(this.model.get('args')));
                return;
            }
            this.model.set('args', _.map(
                cmd.match(/(?:[^\s"']+|("|').*?\1)/g),
                function(i){ return i.replace(/^["']|["']$/g, ''); })
            );
        },

        goNext: function(evt){
            var that = this;

            // remove empty ports and volumeMounts
            this.model.set('ports', this.model.get('ports').filter(
                function(port){ return port.get('containerPort'); }));
            this.model.set('volumeMounts', this.model.get('volumeMounts').filter(
                function(v){
                    var path = v.get('mountPath');
                    if (!path) that.pod.deleteVolumes([v.name]);
                    return path;
                }));

            /* mountPath and persistent disk check */
            var volumes = this.pod.get('volumes'),
                vm = this.model.get('volumeMounts');

            for (var i = 0; i < vm.length; i++) {
                var volumeMount = vm.at(i),
                    name = volumeMount.get('name'),
                    vol = _.findWhere(volumes, {name: name});

                if (vol.hasOwnProperty('persistentDisk')) {
                    var pd = vol.persistentDisk;
                    if (!pd.pdSize || !pd.pdName) {
                        utils.notifyWindow('Persistent options must be set!');
                        return;
                    } else if (pd.pdSize > that.pod.pdSizeLimit){
                        utils.notifyWindow('A persistent disk size isn\'t expected '
                                           + 'to exceed ' + that.pod.pdSizeLimit + ' GB');
                        return;
                    }
                }
            }

            /* check CMD and ENTRYPOINT */
            if (!this.model.get('command').length && !this.model.get('args').length
                    && !this.model.originalCommand.length && !this.model.originalArgs.length){
                utils.notifyWindow('Please, specify value of the Command field.');
                utils.scrollTo(this.ui.input_command);
                return;
            }

            /* check ports */
            var showDublicatePortError = function(dublicatePort){
                var container = dublicatePort.container,
                    type = dublicatePort.isPod ? 'pod' : 'container',
                    where = container === that.model ? 'this container!'
                        : ' other container (' + container.get('image') + ')!';
                utils.notifyWindow('You have a duplicate ' + type + ' port ' +
                                   dublicatePort.port + ' in ' + where);
            };

            try {
                this.model.get('ports').each(function(port, i){
                    that.pod.get('containers').each(function(container2){
                        container2.get('ports').each(function(port2, j){
                            if (container2 == that.model && i === j) return;
                            if (port.get('containerPort') === port2.get('containerPort'))
                                throw {container: container2, port: port.get('containerPort')};
                            var hostPort = port.get('hostPort') || port.get('containerPort'),
                                hostPort2 = port2.get('hostPort') || port2.get('containerPort');
                            if (hostPort === hostPort2)
                                throw {container: container2, port: hostPort, isPod: true};
                        });
                    });
                });
            } catch (e) {
                showDublicatePortError(e);
                return;
            }
            this.trigger('step:envconf', this);
        },

        goBack: function(evt){
            this.pod.deleteVolumes(this.model.get('volumeMounts').pluck('name'));
            this.trigger('step:getimage');
        },

        onRender: function(){
            this.ui.input_command.val(this.filterCommand(this.model.get('args')));
        },

        filterCommand: function(command) {
            command = _.map(command, function(e) {
                return e.indexOf(' ') > 0 ? '"' + e + '"': e;
            });
            return command.join(' ');
        }
    });

    newItem.PortListItem = Backbone.Marionette.ItemView.extend({
        template : portListItemTpl,
        tagName : 'tr',

        ui: {
            podPort        : '.hostPort .ieditable',
            publicIp       : 'input.public',
            iseditable     : '.iseditable',  // TODO: rename (it's protocol)
            removePort     : '.remove-port',
            containerPort  : '.containerPort .ieditable',
        },
        events: {
            'click @ui.removePort' : 'removePortEntry',
            'click @ui.publicIp'   : 'togglePublic',
        },

        removePortEntry: function(evt){
            evt.stopPropagation();
            this.model.collection.remove(this.model);
        },
        togglePublic: function(evt){
            evt.stopPropagation();
            this.model.set('isPublic', !this.model.get('isPublic'));
        },

        onRender: function(){
            var that = this;

            var validatePort = function(newValue) {
                newValue = parseInt(newValue);
                if (isNaN(newValue) || newValue < 1 || newValue > 65535) {
                    utils.notifyWindow('Port must be a number in range 1-65535.');
                    return ' ';  // return string - means validation not passed
                }
                return {newValue: newValue};
            };

            this.ui.podPort.editable({
                type: 'text',
                mode: 'inline',
                validate: function(newValue) {
                    if (newValue === '') return;  // host port accepts empty value
                    return validatePort(newValue);
                },
                success: function(response, newValue) {
                    that.model.set('hostPort', newValue === '' ? null : newValue);
                },
            });

            this.ui.containerPort.editable({
                type: 'text',
                mode: 'inline',
                validate: validatePort,
                success: function(response, newValue) {
                    that.model.set('containerPort', newValue);
                },
            });

            this.ui.iseditable.editable({
                type: 'select',
                value: 'tcp',
                source: [{value: 'tcp', text: 'tcp'}, {value: 'udp', text: 'udp'}],
                mode: 'inline',
                showbuttons: false,
                success: function(response, newValue) {
                    that.model.set('protocol', newValue);
                },
            });
        },
    });

    newItem.PortCollection = Backbone.Marionette.CompositeView.extend({
        template: portListTpl,
        tagName: 'div',
        className: 'row',
        childViewContainer: 'tbody',
        childView: newItem.PortListItem,
        emptyView: Backbone.Marionette.ItemView.extend({
            template : portListEmptyTpl,
            tagName  : 'tr',
        }),

        ui: {
            containerPort : '.containerPort .ieditable',
            podPort       : '.hostPort .ieditable',
            addPort       : '.add-port',
        },

        events: {
            'click @ui.addPort' : 'addItem',
        },

        addItem: function(evt){ this.collection.add(new Model.Port()); },
    });

    newItem.VolumeMountListItem = Backbone.Marionette.ItemView.extend({
        template : volumeMountListItemTpl,
        tagName : 'tr',

        ui: {
            mountPath      : '.mountPath.ieditable',
            pdSelect       : '.pd-select',
            pdSelectSearch : '.pd-select .bs-searchbox input',
            persistent     : '.persistent',
            removeVolume   : '.remove-volume',
            pdName         : '.pd-name',
            pdSize         : '.pd-size',
        },
        events: {
            'input @ui.pdSelectSearch'      : 'searchPD',
            'hide.bs.select @ui.pdSelect'   : 'selectPD',
            'change @ui.pdSize'             : 'changeSize',
            'keyup @ui.pdSize'              : 'changeSize',
            'click @ui.persistent'          : 'togglePersistent',
            'click @ui.removeVolume'        : 'removeVolumeEntry',
        },

        templateHelpers: function(){
            return {
                isPersistent: !!this.volume.persistentDisk,
                persistentDisk: this.getPDModel(),
                persistentDrives: this.pod.persistentDrives,
                pdSizeLimit: this.pod.pdSizeLimit,
                pod: this.pod,
            };
        },

        initialize: function(options){
            this.container = this.model.getContainer();
            this.pod = this.container.getPod();
            var volumes = this.pod.get('volumes');
            this.volume = _.findWhere(volumes, {name: this.model.get('name')});
            if (this.volume === undefined) {
                this.volume = {name: this.model.get('name')};
                volumes.push(this.volume);
            } else if (this.volume.persistentDisk){
                this.listenTo(this.pod.persistentDrives, 'refreshSelects', this.render);
            }
        },

        getPDModel: function(name){
            name = name || (this.volume.persistentDisk||{}).pdName;
            if (!name || !this.pod.persistentDrives) return;
            return this.pod.persistentDrives.findWhere({name: name});
        },

        nameFormat: /^[a-z]+[\w-]*$/i,

        searchPD: function(evt){
            var name = evt.target.value = evt.target.value.trim(),
                pd = this.getPDModel(name);
            this.ui.pdSelect.find('.add-new-pd, .invalid-name-pd').remove();

            if (name){
                var error = !this.nameFormat.test(name) ? 'Only "-", "_" and alphanumeric symbols are allowed.'
                    : name.length > 36 ? 'Maximum length is 36 symbols.'
                    : null;
                if (error){
                    this.ui.pdSelect.prepend($('<option disabled/>')
                        .addClass('invalid-name-pd').val(name).text(error)
                        // also add name, so selectpicker won't hide this "option"
                        .append($('<span class="hidden"/>').text(name))
                    );
                    this.ui.pdSelect.selectpicker('refresh');
                    $(evt.target).addClass('error');
                    return;
                }
                if (pd === undefined){  // add option "create new pd" in select
                    this.ui.pdSelect.prepend($('<option/>')
                        .val(name).text(name + ' (new)').addClass('add-new-pd')
                    );
                }
            }
            this.ui.pdSelect.selectpicker('refresh');
        },

        selectPD: function(){
            // if there was an error message, remove it
            this.ui.pdSelect.find('.invalid-name-pd').remove();
            this.ui.pdSelect.selectpicker('refresh');

            var name = (this.ui.pdSelect.val() || '').trim();
            if (!name || !this.nameFormat.test(name)) {
                var current = this.getPDModel();
                if (current != null)
                    this.ui.pdSelect.val(current.get('name')).selectpicker('render');
                return;
            }

            this.releasePersistentDisk();
            var pd = this.getPDModel(name);
            this.ui.pdSize.prop('disabled', pd !== undefined);
            if (pd === undefined){  // new pd
                pd = new Model.PersistentStorageModel({name: name});
                pd.isNewPD = true;
                pd = this.pod.persistentDrives.add(pd);
            }
            pd.set('in_use', true);
            this.volume.persistentDisk.pdName = name;
            this.volume.persistentDisk.pdSize = pd.get('size');
            this.ui.pdSize.val(pd.get('size'));

            var conflicts = pd.conflictsWith(this.pod);
            if (conflicts.length){
                utils.notifyWindow('Persistent Disk ' + name + ' conflicts with '
                                   + conflicts.pluck('name').join(', ')
                                   + '. All disks must be on the same node. '
                                   + 'You need to eliminate this conflict to save the pod.');
            }

            this.pod.persistentDrives.trigger('refreshSelects');
        },

        changeSize: function(evt){
            evt.stopPropagation();
            // TODO: wants rethinking.
            var size = evt.target.value;
            if (_.some( [_.isUndefined(size), _.isNaN(size), _.isEmpty(size)] )){
                this.ui.pdSize.addClass('error');
                return;
            } else if (size < 1 || this.pdSizeLimit !== undefined && size > this.pdSizeLimit) {
                this.ui.pdSize.addClass('error');
                utils.notifyWindow('Max size of persistent volume should be '
                                   + 'more than zero and less than '
                                   + this.pdSizeLimit + ' GB');
            }
            this.getPDModel().set('size', size);
            this.volume.persistentDisk.pdSize = size;
        },

        togglePersistent: function(evt){
            evt.stopPropagation();
            var that = this;

            if (!this.model.get('mountPath')){
                utils.notifyWindow('Mount path must be set!');
                this.ui.mountPath.click();
                return false;
            } else {
                if (this.pod.persistentDrives === undefined) {
                    var persistentDrives = new Model.PersistentStorageCollection();
                    utils.preloader.show();
                    $.when(persistentDrives.fetch({wait: true}),
                           App.getSystemSettingsCollection())
                        .always(utils.preloader.hide)
                        .fail(utils.notifyWindow)
                        .done(function(drives, settings){
                            var conf = settings.byName('persitent_disk_max_size');
                            that.pod.pdSizeLimit = conf == null ? 10 : parseInt(conf.get('value'));
                            that.pod.persistentDrives = persistentDrives;
                            that.toggleVolumeEntry();
                            that.render();
                            that.ui.pdSelect.selectpicker('toggle');
                        });
                } else {
                    that.toggleVolumeEntry();
                    that.render();
                    that.ui.pdSelect.selectpicker('toggle');
                }
            }
        },

        toggleVolumeEntry: function(){
            if (this.volume.persistentDisk) {
                this.releasePersistentDisk();
                delete this.volume.persistentDisk;
                this.stopListening(this.pod.persistentDrives, 'refreshSelects', this.render);
                this.pod.persistentDrives.trigger('refreshSelects');
            } else {
                this.listenTo(this.pod.persistentDrives, 'refreshSelects', this.render);
                this.volume.persistentDisk = {pdName: null, pdSize: null};
            }
        },

        // If volume uses PD, release it. If this PD is new, remove it.
        releasePersistentDisk: function(){
            if (!_.has(this.volume, 'persistentDisk') ||
                this.pod.persistentDrives === undefined) return;
            var disk = this.getPDModel();
            if (disk === undefined) return;
            if (disk.isNewPD){
                this.pod.persistentDrives.remove(disk);
                return;
            }
            disk.set('in_use', false);
        },

        removeVolumeEntry: function(evt){
            evt.stopPropagation();
            this.releasePersistentDisk();
            this.model.collection.remove(this.model);
            var volumes = this.pod.get('volumes');
            volumes.splice(volumes.indexOf(this.volume), 1);
            if (this.volume.persistentDisk)
                this.pod.persistentDrives.trigger('refreshSelects');
        },

        onRender: function(){
            var that = this;

            this.ui.mountPath.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var value = newValue.trim(),
                        error = Model.Container.validateMountPath(value);
                    // TODO: style for editable validation errors
                    // if (error) return error;
                    if (error) {
                        utils.notifyWindow(error);
                        return '';
                    }

                    that.model.set('mountPath', value);
                }
            });
            this.ui.pdSelect.selectpicker({
                liveSearch: true,
                title: 'Select Persistent Disk',
                liveSearchPlaceholder: 'Enter the name',
                dropupAuto: false,
            });
            this.ui.pdSelect.selectpicker('val', (this.volume.persistentDisk||{}).pdName);
        },

    });

    newItem.VolumeMountCollection = Backbone.Marionette.CompositeView.extend({
        template: volumeMountListTpl,
        tagName: 'div',
        className: 'row',
        childViewContainer: 'tbody',
        childView: newItem.VolumeMountListItem,
        emptyView: Backbone.Marionette.ItemView.extend({
            template : volumeMountListEmptyTpl,
            tagName  : 'tr',
        }),

        ui: {
            addVolume : '.add-volume',
        },

        events: {
            'click @ui.addVolume' : 'addVolume',
        },

        addVolume: function(evt){ this.collection.add(new Model.VolumeMount()); },
    });


    newItem.WizardEnvSubView = Backbone.Marionette.ItemView.extend({
        template: wizardSetContainerEnvTpl,
        tagName: 'div',

        ui: {
            ieditable  : '.ieditable',
            table      : '#data-table',
            reset      : '.reset-button',
            input      : '.change-input',
            addItem    : '.add-env',
            removeItem : '.remove-env',
            nameField  : 'input.name',
            valueField : 'input.value',
            next       : '.next-step',
            navButtons : '.nav-buttons',

            stopContainer  : '#stopContainer',
            startContainer : '#startContainer',
            updateContainer: '.container-update',
            checkForUpdate : '.check-for-update',
        },

        events: {
            'click @ui.addItem'    : 'addItem',
            'click @ui.removeItem' : 'removeItem',
            'click @ui.reset'      : 'resetFielsdsValue',
            'change @ui.input'     : 'onChangeInput',
            'click @ui.next'       : 'finalStep',
            'focus @ui.input'      : 'removeError',

            'click @ui.stopContainer'  : 'stopContainer',
            'click @ui.startContainer' : 'startContainer',
            'click @ui.updateContainer': 'updateContainer',
            'click @ui.checkForUpdate' : 'checkContainerForUpdate',
        },

        triggers: {
            'click .prev-step'       : 'step:volconf',
            'click .go-to-ports'     : 'step:portconf',
            'click .go-to-volumes'   : 'step:volconf',
            'click .go-to-resources' : 'step:resconf',
            'click .go-to-other'     : 'step:otherconf',
            'click .go-to-stats'     : 'step:statsconf',
            'click .go-to-logs'      : 'step:logsconf',
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function() {
            var that = this;
            App.getPodCollection().done(function(podCollection){
                that.podCollection = podCollection;
            });
        },

        onDomRefresh: function(){
            if (utils.hasScroll()) {
                this.ui.navButtons.addClass('fixed');
            } else {
                this.ui.navButtons.removeClass('fixed');
            }
        },

        templateHelpers: function(){
            var pod = this.model.getPod();
            pod.recalcInfo();
            return {
                parentID: pod.id,
                updateIsAvailable: this.model.updateIsAvailable,
                sourceUrl: this.model.get('sourceUrl'),
                detached: pod.detached,
                ip: this.model.get('ip'),
                kube_type: pod.getKubeType(),
                limits: this.model.limits,
                restart_policy: pod.get('restartPolicy'),
                podName: pod.get('name'),
            };
        },

        startContainer: function(){ this.model.getPod().cmdStart(); },
        stopContainer: function(){ this.model.getPod().cmdStop(); },
        updateContainer: function(){ this.model.update(); },
        checkContainerForUpdate: function(){
            this.model.checkForUpdate().done(this.render);
        },

        removeError: function(evt){ utils.removeError($(evt.target)); },

        finalStep: function(){
            var that = this,
                valid = true,
                env = this.model.get('env'),
                paternFirstSumbol = /^[a-zA-Z]/,
                paternValidName = /^[a-zA-Z0-9-_\.]*$/;

            /* get only not empty env from model */
            this.model.set('env', env = _.filter(env, function(item){ return item.name; }));

            /* validation & triming extra spacing */
            _.each(env, function(envItem, indexEnv){
                var name = that.ui.nameField[indexEnv];
                envItem.name = name.value.trim();
                $(name).val(envItem.name);
                if (!paternFirstSumbol.test(envItem.name)){
                    utils.notifyInline('First symbol must be letter in variables name',name);
                    valid = false;
                }
                if (!paternValidName.test(envItem.name)){
                    utils.notifyInline('Variable name should contain only Latin letters or ".", "_", "-" symbols',name);
                    valid = false;
                }
                if (envItem.name.length > 255){
                    utils.notifyInline('Max length is 255 symbols',name);
                    valid = false;
                }

                var value = that.ui.valueField[indexEnv];
                envItem.value = value.value.trim();
                $(value).val(envItem.value);
                if (!envItem.value){
                    utils.notifyInline('Variables value must be set',value);
                    valid = false;
                }
            });

            /* check to uniq values */
            var uniqEnvs = _.uniq(env, function(item){ return item.name; }),
                difference = _.difference(env, uniqEnvs);

            if (difference.length != 0){
                _.each(difference, function(item){
                    _.each(that.ui.nameField, function(field){
                        if (field.value == item.name){
                            $(field).addClass('error');
                            utils.notifyInline('Duplicate variable names are not allowed',field);
                        }
                    });
                });
                difference.length = 0;
                valid = false;
            }

            /* scroling to error */
            if (this.ui.nameField.hasClass('error')) utils.scrollTo($('input.error').first());

            /* save data & navigate to next step */
            if (valid){
                this.model.set('env', env);
                this.trigger('step:complete');
            }
        },

        addItem: function(evt){
            evt.stopPropagation();
            var env = this.model.get('env');
            env.push({name: null, value: null});
            this.render();
        },


        removeItem: function(evt){
            var env = this.model.get('env'),
                item = $(evt.target),
                index = item.parents('tr').index();
            item.parents('tr').remove();
            env.splice(index, 1);

            this.render();
        },

        resetFielsdsValue: function(){
            this.model.set('env', _.map(this.model.origEnv, _.clone));
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

    newItem.WizardStatsSubItemView = Backbone.Marionette.ItemView.extend({
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

    newItem.WizardStatsSubView = Backbone.Marionette.CompositeView.extend({
        childView: newItem.WizardStatsSubItemView,
        childViewContainer: "div.container-stats #monitoring-page",
        template: wizardSetContainerStatsTpl,
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
            'click .go-to-volumes'   : 'step:volconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-resources' : 'step:resconf',
            'click .go-to-other'     : 'step:otherconf',
            'click .go-to-stats'     : 'step:statsconf',
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
                detached: pod.detached,
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

    newItem.WizardLogsSubView = Backbone.Marionette.ItemView.extend({
        template: wizardSetContainerLogsTpl,
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
            'click .go-to-volumes'   : 'step:volconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-resources' : 'step:resconf',
            'click .go-to-other'     : 'step:otherconf',
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

    newItem.WizardCompleteSubView = Backbone.Marionette.ItemView.extend({
        template: wizardSetContainerCompleteTpl,
        tagName: 'div',

        initialize: function(options){
            this.pkg = App.userPackage;
            this.model.recalcInfo(this.pkg);
            this.hasBilling = options.hasBilling;
            this.payg = options.payg;
            this.kubesLimit = options.kubesLimit;

            // TODO: package change, package-kube relationship change
            this.listenTo(App.kubeTypeCollection, 'change add remove reset', this.pricingChanged);
        },

        templateHelpers: function() {
            var kubeTypes = this.pkg.getKubeTypes();
            kubeTypes.each(function(kt){
                var conflicts = kt.conflicts.pluck('name').join(', ');
                kt.formattedName = kt.get('name') + ' ' + (
                    !kt.get('available') ? '(currently not available)'
                        : kt.conflicts.length ? '(conflict with disk ' + conflicts + ')'
                            : '');
                kt.disabled = kt.get('available') && !kt.conflicts.length;
            });

            return {
                last_edited      : this.model.lastEditedContainer.id,
                isPublic         : this.model.isPublic,
                isPerSorage      : this.model.isPerSorage,
                limits           : this.model.limits,
                containerPrices  : _.pluck(this.model.get('containers').models, 'price'),
                totalPrice       : this.model.totalPrice,
                kubeTypes        : kubeTypes,
                kubesLimit       : this.kubesLimit,
                restart_policies : {'Always': 'Always', 'Never': 'Never', 'OnFailure': 'On Failure'},
                restart_policy   : this.model.get('restartPolicy'),
                image_name_id    : this.model.get('lastAddedImageNameId'),
                period           : this.pkg.get('period'),
                price_ip         : this.pkg.getFormattedPrice(this.pkg.get('price_ip')),
                price_pstorage   : this.pkg.getFormattedPrice(this.pkg.get('price_pstorage')),
                hasBilling       : this.hasBilling,
                payg             : this.payg    // Pay-As-You-Go billing method
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
            'tooltip'                 : '[data-toggle="tooltip"]'
        },

        events: {
            'click .prev-step'       : 'goBack',
            'click .delete-item'     : 'deleteItem',
            'click .edit-item'       : 'editItem',
            'click .add-more'        : 'addItem',
            'click .node'            : 'toggleNode',
            'change .replicas'       : 'changeReplicas',
            'change @ui.kubeTypes'   : 'changeKubeType',
            'change .kube-quantity'  : 'changeKubeQuantity',
            'change @ui.policy'      : 'changePolicy',
            'click @ui.editPolicy'   : 'editPolicy',
            'click @ui.editKubeType' : 'editKubeType',
        },

        triggers: {
            'click .save-container'     : 'pod:save',
            'click .pay-and-run-container' : 'pod:pay_and_run',
        },

        deleteItem: function(evt){
            evt.stopPropagation();
            var name = $(evt.target).closest('tr').children('td:first').attr('id');
            if (this.model.get('containers').length >= 2) {
                this.model.get('containers').remove(name);
                if (name == this.model.lastEditedContainer.id) {
                    this.model.lastEditedContainer.isNew = false;
                    this.model.lastEditedContainer.id = this.model
                        .get('containers').last().id;
                }
                this.model.recalcInfo(this.pkg);
                this.model.solveKubeTypeConflicts();
                this.render();
            } else {
                utils.modalDialogDelete({
                    title: "Delete",
                    body: "After deleting the last container, you will go " +
                          "back to the main page. Delete this container?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            App.navigate('pods', {trigger: true});
                        },
                        buttonCancel: true
                    }
                });
            }
        },

        editItem: function(evt){
            evt.stopPropagation();
            var tgt = evt.target,
                name = $(tgt).closest('tr').children('td:first').attr('id');
            this.model.lastEditedContainer = {id: name};
            this.trigger('step:portconf', name);
        },

        addItem: function(evt){
            evt.stopPropagation();
            this.model.lastEditedContainer = {id: null, isNew: true};
            this.trigger('step:getimage');
        },

        // edit env vars of the last edited container
        goBack: function(evt){
            evt.stopPropagation();
            this.trigger('step:envconf');
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
            var num = parseInt(evt.target.value);
            this.getCurrentContainer().set('kubes', num);

            this.model.recalcInfo(this.pkg);
            this.render();
            $('.kube-quantity button span').text(num);
        },

        changeKubeType: function(evt){
            evt.stopPropagation();
            var kube_id = parseInt(evt.target.value);
            this.model.set('kube_type', kube_id);

            this.model.recalcInfo(this.pkg);
            this.render();
        },

        changePolicy: function(evt){
            evt.stopPropagation();
            var restart_policy = $(evt.target).val();
            this.model.set('restartPolicy', restart_policy);
        },

        getCurrentContainer: function() {
            var containers = this.model.get('containers');
            return containers.get(this.model.lastEditedContainer.id);
        },

        /**
         * Got "change" event for package or kube types
         */
        pricingChanged: function(){
            if (!this.model.getKubeType().get('available'))
                this.model.unset('kube_type');  // no longer available
            this.render();
        },

        onRender: function() {
            this.ui.selectpicker.selectpicker();
            this.ui.tooltip.tooltip();
            this.ui.kubeTypes.selectpicker({
                noneSelectedText: this.model.get('kube_type') === Model.KubeType.noAvailableKubeTypes
                    ? 'No available kube types' : 'Select kube type',
            });
            this.ui.kubeQuantity.selectpicker('val', this.getCurrentContainer().get('kubes'));
            if (this.model.get('kube_type') === undefined)
                this.ui.kubeTypes.val('').selectpicker('render');  // unselect
            else
                this.ui.kubeTypes.selectpicker('val', this.model.get('kube_type'));
        },

        editPolicy: function(){
            this.ui.editPolicy.hide();
            this.ui.editPolycyDescription.hide();
            this.ui.policy.attr('disabled',false);
            this.$('.policy .disabled').removeClass('disabled');
        },

        editKubeType: function(){
            this.ui.editKubeType.hide();
            this.ui.editKubeTypeDescription.hide();
            this.ui.kubeTypes.attr('disabled', false);
            this.ui.kubeTypes.removeClass('disabled');
            this.$('.kube-type-wrapper button.disabled').removeClass('disabled');
        },
    });

    return newItem;
});
