/**
 * This module provides view for displaying data
 */

function modalDialog(options){
    var modal = $('.modal');
    if(options.title) modal.find('.modal-title').html(options.title);
    if(options.body) modal.find('.modal-body').html(options.body);
    if(options.large) modal.addClass('bs-example-modal-lg');
    if(options.small) modal.addClass('bs-example-modal-sm');
    if(options.show) modal.modal('show');
    return modal;
}

KubeDock.module('Views', function(Views, App, Backbone, Marionette, $, _){

    // this layout view shows the main page: basic pods list
    Views.PodListLayout = Backbone.Marionette.LayoutView.extend({
        template: '#layout-pod-list-template',

        events: {
            'click .start-checked': 'startItems',
            'click .stop-checked': 'stopItems',
            'click .terminate-checked': 'terminateItems',
            'click .table th input[type=checkbox]': 'itemsAllHandler'
        },

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
            masthead: '#masthead-title',
            list: '#layout-list',
            pager: '#layout-footer'
        },

        startItems: function(evt){
            var preloader = $('#page-preloader');
                preloader.show(); 
            initPodCollection.forEach(function(i){
                if (i.get('checked') === true){
                   /* i.set({'command': 'start'});*/
                    i.save({'command': 'start'}, {
                        success: function(){
                            preloader.hide();
                        },
                        error: function(){
                            var errorText = 'errorText',
                                errorTitle = 'errorTitle';
                            preloader.hide();
                            modalDialog({
                                title: errorTitle,
                                body: errorText,
                                show: true
                            });
                        }
                    });
                }
            });
        },

        stopItems: function(evt){
            var preloader = $('#page-preloader');
                preloader.show();
            initPodCollection.forEach(function(i){
                if (i.get('checked') === true){
                   /* i.set({'command': 'stop'});*/
                    i.save({'command': 'stop'}, {
                        wait: true,
                        success: function(){
                            initPodCollection.remove(i);
                        },
                        error: function(){
                            var errorTitle = 'errorTitle',
                                errorText = 'errorText';
                            preloader.hide();
                            modalDialog({
                                title: errorTitle,
                                body: errorText,
                                show: true
                            });
                        }
                    });
                }

            });
        },

        terminateItems: function(evt){
            var preloader = $('#page-preloader');
                preloader.show();
            initPodCollection.forEach(function(i){
                if (i.get('checked') === true){
                    i.destroy({
                        wait: true,
                        success: function(){
                            initPodCollection.remove(i);
                        },
                        error: function(){
                            var errorTitle = 'errorTitle',
                                errorText = 'errorText';
                            preloader.hide();
                            modalDialog({
                                title: errorTitle,
                                body: errorText,
                                show: true
                            });
                        }
                    });
                }
            });
        },
        itemsAllHandler: function(evt){
            var target = $(evt.currentTarget),
                pods_actions_btn = $('.pods-actions-btn'),
                inputs = target.parents('.table').find('tbody tr td:first-child input[type=checkbox]');

            if( target.is(':checked') ) {
                inputs.prop('checked',true);
                pods_actions_btn.removeClass('disabled');
            } else {
                inputs.prop('checked',false);
                pods_actions_btn.addClass('disabled');
            }
        }
    });

    // View for showing a single pod item as a row in pods list
    Views.PodListItem = Backbone.Marionette.ItemView.extend({
        template: '#pod-list-item-template',
        tagName: 'tr',
        className: 'pod-item',

        ui: {
            checkbox: '.check-item',
            reditable: '.reditable'
        },

        onRender: function(){
            var that = this;
            this.ui.reditable.editable({
                type: 'text',
                title: 'Change replicas number',
                success: function(response, newValue) {
                    that.model.set({
                        'command': 'resize',
                        'replicas': parseInt(newValue.trim())
                    });
                    that.model.save();
                }
            });
        },

        events: {
            'change .check-item': 'checkItem',
            'click .start-btn': 'startItem',
            'click .stop-btn': 'stopItem',
            'click .terminate-btn': 'terminateItem',
            'click @ui.checkbox': 'inputHandler'
        },

        checkItem: function(evt){
            this.model.set('checked', this.ui.checkbox.is(':checked'));
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
                    var errorText = 'errorText',
                        errorTitle = 'errorTitle';
                    that.render();
                    preloader.hide();
                    modalDialog({
                        title: errorTitle,
                        body: errorText,
                        show: true
                    });
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
                    var errorText = 'errorText',
                        errorTitle = 'errorTitle';
                    that.render();
                    preloader.hide();
                    modalDialog({
                        title: errorTitle,
                        body: errorText,
                        show: true
                    });
                }
            });
        },

        terminateItem: function(evt){
            evt.stopPropagation();
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
               error: function(e, data){
                    var errorText = 'errorText',
                        errorTitle = 'errorTitle';
                    that.render();
                    preloader.hide();
                    modalDialog({
                        title: errorTitle,
                        body: errorText,
                        show: true
                    });
                }
            });
        },
        inputHandler: function(evt){
            evt.stopPropagation();

            var target = $(evt.currentTarget),
                tbody = target.parents('.table tbody'),
                switcher = target.parents('.table').find('thead tr:first-child input[type=checkbox]')[0],
               	pods_actions_btn = $('.pods-actions-btn'),   //for bliss ты обещал посмотреть как избегать подобного кода если элемент не динамический //
                inputsLength = 0,
                counter = 0;

            tbody.find('tr td:first-child input').each(function(){
                if (this.checked) {
                    counter+=1;
                    pods_actions_btn.removeClass('disabled');
                }
                inputsLength+=1;
            });
            if (counter == 0 ){
                pods_actions_btn.addClass('disabled');
            }
            if (counter == inputsLength) {
               switcher.checked = true;
               pods_actions_btn.removeClass('disabled');
            }
            else {
                switcher.checked = false;
            }
        }
    });

    Views.PodCollection = Backbone.Marionette.CompositeView.extend({
        childView: Views.PodListItem,
        tagName: 'div',
        className: 'row',
        childViewContainer: 'tbody',
        template: '#pod-list-template',

        onBeforeDestroy: function(){
            this.trigger('pager:clear');
        }
    });

    // this layout view shows details a pod details page
    Views.PodItemLayout = Backbone.Marionette.LayoutView.extend({
        template: '#layout-pod-item-template',

        regions: {
            masthead: '#masthead-title',
            controls: '#item-controls',
            info: '#item-info',
            aside: '#layout-aside',
            contents: '#layout-contents'
        },

        initialize: function(){
            var that = this;
            this.listenTo(this.info, 'show', function(view){
                that.listenTo(view, 'display:pod:stats', that.showPodStats);
            });
        },

        showPodStats: function(data){
             this.trigger('display:pod:stats', data.model)
         }
    });

    Views.PageHeader = Backbone.Marionette.ItemView.extend({
        template: '#page-header-title-template'
    });

    Views.InfoPanel = Backbone.Marionette.ItemView.extend({
        template: '#page-info-panel-template',
        tagName: 'div',
        className: 'row',

        triggers: {
            'click .stats': 'display:pod:stats'
        }
    });

    Views.ControlsPanel = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-controls-template',
        tagName: 'div',
        className: 'pod-controls',

        events: {
            'click .start-btn': 'startItem',
            'click .stop-btn': 'stopItem',
            'click .terminate-btn': 'terminateItem'
        },

        getItem: function(){
            return initPodCollection.fullCollection.get(this.model.id);
        },

        startItem: function(evt){
            var item = this.getItem(),
                that = this,
                preloader = $('#page-preloader');
                preloader.show(); 
            evt.stopPropagation();
            //item.set({'command': 'start'});
            item.save({command: 'start'}, {
                wait: true,
                success: function(model, response, options){
                    that.render();
                    preloader.hide();
                },
                error: function(e, data){
                    var errorText = 'errorText',
                        errorTitle = 'errorTitle';
                    preloader.hide();
                    modalDialog({
                        title: errorTitle,
                        body: errorText,
                        show: true
                    });
                }
            });
        },

        stopItem: function(evt){
            var item = this.getItem(),
                that = this,
                preloader = $('#page-preloader');
                preloader.show(); 
            evt.stopPropagation();
            //item.set({'command': 'stop'});
            item.save({command: 'stop'}, {
                wait: true,
                success: function(model, response, options){
                    that.render();
                    preloader.hide();
                },
                error: function(e, data){
                    var errorText = 'errorText',
                        errorTitle = 'errorTitle';
                    preloader.hide();
                    modalDialog({
                        title: errorTitle,
                        body: errorText,
                        show: true
                    });
                }
            });
        },

        terminateItem: function(evt){
            evt.stopPropagation();
            var item = this.getItem(),
                name = item.get('name'),
                preloader = $('#page-preloader');
                preloader.show();
            item.destroy({
                wait: true,
                success: function(){
                    initPodCollection.remove(item);
                    window.location.href = '/#pods';
                    preloader.hide();
                },
                error: function(e, data){
                    var errorTitle = 'errorTitle';
                    preloader.hide();
                    modalDialog({
                        title: errorTitle,
                        body: 'Could not remove ' + name,
                        show: true
                    });
                }
            });
        }
    });

    Views.PodGraphItem = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-graph-template',
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
            console.log(points);
            this.ui.chart.jqplot(points, options);
        }
    });

    Views.PodGraph = Backbone.Marionette.CollectionView.extend({
        childView: Views.PodGraphItem
    });

    Views.PodItemMain = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-main-template'
    });

    Views.PodItemContainer = Backbone.Marionette.ItemView.extend({
        template: '#pod-item-container-template'
    });

    // View for display pod and its containers in the whole
    Views.PodItem = Backbone.Marionette.CollectionView.extend({
        childView: Views.PodItemContainer
    });

    // Layout view for wizard
    Views.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: '#layout-wizard-template',
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
        imageSelected: function(data){
            this.trigger('image:selected', data);
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

    Views.PodHeaderView = Backbone.Marionette.ItemView.extend({
        template: _.template('<h2 class="peditable"><%- name %></h2>'),
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

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
                title: 'Change container name',
                success: function(response, newValue) {
                    // TODO: check pod name
                    $.ajax({
                        url: '/api/pods/checkName',
                        data: {'name': newValue},
                        dataType: 'JSON',
                        success: function(rs){
                            if(rs.status == 'OK')
                                that.model.set({name: newValue});
                        },
                        error: function(xhr, status, erorr){
                            modalDialog({
                                title: 'Wrong name',
                                body: JSON.parse(xhr.responseText).status,
                                show: true
                            });
                            that.ui.peditable.editable('option', 'value', 'Unnamed');
                        }
                    })
                }
            });
        }
    });

    // Images collection item view
    Views.ImageListItemView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-image-collection-item-template',
        tagName: 'div',
        className: 'item',

        events: {
            'click .add-item': 'addItem'
        },

        addItem: function(evt){
            evt.stopPropagation();
            this.trigger('image:selected');
        }
    });

    // Images collection view
    var imageSearchURL = 'https://registry.hub.docker.com/';
    Views.GetImageView = Backbone.Marionette.CompositeView.extend({
        template: '#wizard-get-image-template',
        childView: Views.ImageListItemView,
        childViewContainer: '#data-collection',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        initialize: function(options){
            this.collection = new App.Data.ImageCollection();
            this.listenTo(this.collection, 'reset', this.render);
        },

        triggers: {
            'click .next-step' : 'step:next'
        },

        events: {
            'click .search-image': 'onSearchClick',
            'keypress #search-image-field': 'onInputKeypress',
            'click #search-image-default-repo': 'onChangeRepoURL'
        },

        childEvents: {
            'image:selected': 'childImageSelected'
        },

        ui: {
            repo_url_repr: 'span#search-image-default-repo',
            input: 'input#search-image-field',
            spinner: '#data-collection'
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
            this.fetchCollection(this.ui.input.val().trim());
        },

        fetchCollection: function(query){
            // query string validation
            if(query.split('/').length > 2) {
                if(query.substr(0, 4) != 'http') {
                    modalDialog({
                        title: 'Wrong image name',
                        body: 'Wrong image name. If you want to search in your own ' +
                          'repository, please type full URL path, e.g.: <br/>' +
                          'https://registry.hub.docker.com/<i>UserName/ImageName</i> <br/>' +
                          'or <i>UserName/ImageName</i><br/> or simple <i>ImageName</i>',
                        show: true
                    });
                    this.ui.input.focus();
                    return;
                } else {}
            }
            var that = this;
            this.ui.spinner.spin({color: '#437A9E'});
            this.collection.fetch({
                data: {searchkey: query, url: imageSearchURL},
                reset: true,
                success: function(){
                    that.ui.spinner.spin(false);
                    that.trigger('image:fetched', that);
                    that.ui.repo_url_repr.text(imageSearchURL);
                }
            });
        },

        onShow: function(){
            this.ui.input.focus();
        },

        onBeforeDestroy: function(){
            this.trigger('pager:clear');
        },

        childImageSelected: function(data){
            this.trigger('image:selected', data.model.get('name'));
        }
    });

    Views.LoadingView = Backbone.Marionette.ItemView.extend({
        template: _.template('<div id="spinner"></div>'),
        ui: {
            spinner: '#spinner'
        },
        onRender: function(){
            this.ui.spinner.spin({color: '#437A9E'});
        }
    });

    Views.WizardPortsSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-ports-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },

        initialize: function(options){
            try {
                var image = options.model.get('lastAddedImage');
                this.model = new App.Data.Image(options.model.getContainerByImage(image));
            }
            catch(e){
                if (e.constructor === TypeError) {
                    this.model = options.model
                }
            }
        },

        ui: {
            ieditable: '.ieditable',
            iseditable: '.iseditable'
        },

        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:volconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-resources': 'step:resconf',
            'click .go-to-other': 'step:otherconf',
        },

        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var index = $(this).closest('tr').index(),
                        item = $(this).parent().attr('class');
                    that.model.get('ports')[index][item] = newValue;
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
        }
    });

    Views.WizardVolumesSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-volumes-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',
        
        initialize: function(){
            if (!this.model.has('volumeMounts')) {
                this.model.set({'volumeMounts': []});
            }
        },

        ui: {
            ieditable: '.ieditable'
        },

        events: {
            'click .readonly': 'toggleReadOnly',
            'click .add-vol': 'addItem',
        },

        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },

        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:envconf',
            'click .prev-step' : 'step:portconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-resources': 'step:resconf',
            'click .go-to-other': 'step:otherconf',
        },

        addItem: function(env){
            env.stopPropagation();
            this.model.get('volumeMounts').push({name: null, mountPath: null, readOnly: false});
            this.render();
        },
        
        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var index = $(this).closest('tr').index();
                    if (item.hasClass('name')) {
                        that.model.get('volumeMounts')[index]['name'] = newValue;
                    }
                    else if (item.hasClass('mountPath')) {
                        that.model.get('volumeMounts')[index]['mountPath'] = newValue;
                    }
                }
            });
        },
        toggleReadOnly: function(evt){
            evt.stopPropagation();
            index = $(evt.target).closest('tr').index()
            var on = this.model.get('volumeMounts')[index]['readOnly'];
            if (on) {
                this.model.get('volumeMounts')[index]['readOnly'] = false;
            }
            else {
                this.model.get('volumeMounts')[index]['readOnly'] = true;
            }
            this.render();
        }
    });

    Views.WizardEnvSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-env-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        ui: {
            ieditable: '.ieditable',
            table: '#data-table',
        },

        events: {
            'click .add-env': 'addItem',
        },

        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },

        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:resconf',
            'click .prev-step' : 'step:volconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-resources': 'step:resconf',
            'click .go-to-other': 'step:otherconf',
        },

        addItem: function(env){
            env.stopPropagation();
            this.model.get('env').push({name: null, value: null});
            this.render();
        },

        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    var item = $(this);
                    index = item.closest('tr').index();
                    if (item.hasClass('name')) {
                        that.model.get('env')[index]['name'] = newValue;
                    }
                    else if (item.hasClass('value')) {
                        that.model.get('env')[index]['value'] = newValue;
                    }
                }
            });
        }
    });

    Views.WizardResSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-resources-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        ui: {
            ieditable: '.ieditable'
        },

        triggers: {
            'click .complete' : 'step:complete',
            'click .next-step' : 'step:otherconf',
            'click .prev-step' : 'step:envconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-other': 'step:otherconf',
        },

        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },

        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    if ($(this).hasClass('cpu')) {
                        that.model.set('cpu', parseInt(newValue));
                    }
                    else if ($(this).hasClass('memory')) {
                        that.model.set('memory', parseInt(newValue));
                    }
                }
            });
        }

    });

    Views.WizardOtherSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-other-template',
        tagName: 'div',
        className: 'col-md-8 col-md-offset-2',

        ui: {
            ieditable: '.ieditable'
        },

        templateHelpers: function(){
            return {
                isPending: !this.model.has('parentID')
            };
        },

        triggers: {
            'click .complete' : 'step:complete',
            'click .prev-step' : 'step:resconf',
            'click .go-to-ports': 'step:portconf',
            'click .go-to-volumes': 'step:volconf',
            'click .go-to-envs': 'step:envconf',
            'click .go-to-resources': 'step:resconf',
        },

        onRender: function(){
            var that = this;
            this.ui.ieditable.editable({
                type: 'text',
                mode: 'inline',
                success: function(response, newValue) {
                    if ($(this).hasClass('working-dir')) {
                        that.model.set('workingDir', [newValue]);
                    }
                    else if ($(this).hasClass('command')) {
                        that.model.set('command', newValue.split(' '));
                    }
                }
            });
        }
    });

    Views.WizardCompleteSubView = Backbone.Marionette.ItemView.extend({
        template: '#wizard-set-container-complete-template',
        tagName: 'div',
        className: 'row',

        ui: {
            ieditable: '.ieditable'
        },

        events: {
            'click .delete-item': 'deleteItem',
            'click .cluster': 'toggleCluster',
            'change .replicas': 'changeReplicas',
            'change .kubes': 'changeKubes'
        },

        triggers: {
            'click .add-more' : 'step:getimage',
            'click .prev-step' : 'step:envconf',
            'click .save-container': 'pod:save',
            'click .save-run-container': 'pod:run'
        },

        deleteItem: function(evt){
            evt.stopPropagation();
            var image = $(evt.target).closest('tr').children('td:first').text().trim();
            this.model.attributes.containers = _.filter(this.model.get('containers'),
            function(i){ return i.image !== this.image }, {image: image});
            this.render();
        },

        toggleCluster: function(evt){
            evt.stopPropagation();
            if (this.model.get('cluster')) {
                this.model.set('cluster', false);
            }
            else {
                if (this.model.get('port') === null) {
                    var containers = this.model.get('containers'),
                        port = containers[0]['ports'][0]['containerPort'],
                        obj = {cluster: true, port: port, service: true};
                }
                else {
                    var obj = {cluster: true};
                }
                this.model.set(obj);
            }
            this.render();
        },

        changeReplicas: function(evt){
            evt.stopPropagation();
            this.model.set('replicas', parseInt($(evt.target).val().trim()));
        },

        changeKubes: function(evt){
            evt.stopPropagation();
            this.model.set('kubes', parseInt($(evt.target).val().trim()));
        },

        onRender: function(){
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
                        that.model.set('port', newValue);
                    }
                    else {
                        console.log('oops!');
                    }
                }
            });
        }
    });

    Views.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: '#paginator-template',

        initialize: function(options) {
            this.model = new Backbone.Model({
                v: options.view,
                c: options.view.collection
            });
            this.listenTo(options.view.collection, 'remove', this.render);
        },

        events: {
            'click li.pseudo-link': 'paginateIt'
        },

        paginateIt: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target);
            if (tgt.hasClass('paginatorFirst')) this.model.get('c').getFirstPage();
            else if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
            else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
            else if (tgt.hasClass('paginatorLast')) this.model.get('c').getLastPage();
            this.model.get('v').render();
            this.render();
        }
    });
});
