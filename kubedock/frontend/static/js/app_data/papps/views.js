define(['app_data/app', 'app_data/utils', 'marionette', 'js-yaml',

        'app_data/papps/templates/main.tpl',

        'app_data/papps/templates/app_list/empty.tpl',
        'app_data/papps/templates/app_list/item.tpl',
        'app_data/papps/templates/app_list/list.tpl',

        'app_data/papps/templates/load_form.tpl',
        'app_data/papps/templates/yaml_textarea.tpl',

        'tooltip'],
    function(App, utils, Marionette, jsyaml,

            mainTpl,

            listEmptyTpl,
            listItemTpl,
            listTpl,

            appLoadFormTpl,
            YAMLTextareaTpl
            ){
        'use strict';
        var views = {};

        views.MainLayout = Marionette.LayoutView.extend({
            template: mainTpl,

            regions: {
                nav: '#nav',
                breadcrumbs: '#breadcrumbs',
                main: '#main',
                pager: '#footer',
            },

            initialize: function(){
                var that = this;
                this.listenTo(this.main, 'show', function(view){
                    that.listenTo(view, 'app:save', that.saveApp);
                    that.listenTo(view, 'app:saveAnyway', that.saveAppAnyway);
                });
            },

            saveApp: function(data){ this.trigger('app:save', data); },
            saveAppAnyway: function(data){ this.trigger('app:saveAnyway', data); },
        });

        views.AppLoader = Marionette.LayoutView.extend({
            template: appLoadFormTpl,
            tagName: 'div',
            regions: {
                textarea: '.yaml-textarea-wrapper'
            },

            ui: {
                'uploader' : 'input#app-upload',
                'display'  : 'textarea#app-contents',
                'appname'  : 'input#app-name',
                'save'     : 'button.save-app',
                'cancel'   : '.cancel-app',
                'origin'   : 'input#app-origin'
            },

            events: {
                'click @ui.save'      : 'saveApp',
                'change @ui.uploader' : 'handleUpload',
                'focus @ui.appname'   : 'removeError',
                'focus @ui.display'   : 'removeError'
            },

            onDomRefresh: function(){
                this.textarea.show(new views.YAMLTextarea({model: this.model}));
                this.bindUIElements();
                if (this.logScroll === null)  // stick to bottom
                    this.ui.display.scrollTop(this.ui.display[0].scrollHeight);
                else  // stay at the same position
                    this.ui.display.scrollTop(this.logScroll);
            },

            templateHelpers: function(){
                return {
                    isNew: this.model.isNew(),
                    jsyaml: jsyaml,
                    errorData: this.errorData
                };
            },

            handleUpload: function(evt){
                var file = evt.target.files[0],
                    reader = new FileReader(),
                    mimeRegEx = /(?:application\/(?:(?:x-)?yaml|json)|text.*)/,
                    that = this;
                // reset file input, so event would fire even if user
                // selects the same file
                that.ui.uploader.val('');

                if (file.type && !file.type.match(mimeRegEx)){
                    utils.notifyWindow('Please, upload an yaml file.');
                    return;
                }
                reader.onload = function(evt){
                    that.ui.display.empty().val(evt.target.result);
                    that.ui.display.trigger('change');
                };
                reader.readAsText(file);
            },

            removeError: function(evt){
                var target = $(evt.target);

                if (target.hasClass('error')) target.removeClass('error');
                if (this.ui.save.hasClass('anyway')){
                    this.ui.save.removeClass('anyway');
                    this.ui.save.text(this.model.isNew() ? 'Add' : 'Save');
                }
            },

            saveApp: function(env){
                env.stopPropagation();
                env.preventDefault();
                var target = $(env.target),
                    name = this.ui.appname.val(),
                    origin = this.ui.origin.val(),
                    template = this.ui.display.val();

                if (name.length > 30){
                    utils.scrollTo(this.ui.appname);
                    this.ui.appname.addClass('error');
                    utils.notifyWindow('Max length 30 symbols');
                    return;
                }
                if (!name) {
                    utils.notifyWindow('Name is expected to be filled');
                    this.ui.appname.addClass('error');
                    utils.scrollTo(this.ui.appname);
                    return;
                }
                if (!template){
                    utils.notifyWindow('Template is expected to be filled');
                    this.ui.display.addClass('error');
                    utils.scrollTo(this.ui.display);
                    return;
                }
                this.model.set({name: name, origin: origin, template: template});
                if (target.hasClass('anyway')){
                    this.trigger('app:saveAnyway', this.model);
                } else {
                    this.trigger('app:save', this.model);
                }
            }
        });

        views.AppListEmpty = Marionette.ItemView.extend({
            template : listEmptyTpl,
            tagName  : 'tr',
        });

        views.AppListItem = Marionette.ItemView.extend({
            template    : listItemTpl,
            tagName     : 'tr',

            initialize: function(){
                this.urlPath = window.location.protocol +
                    '//' + window.location.host + '/apps/';
            },

            templateHelpers: function(){
                var modified = this.model.get('modified');

                return {
                    urlPath: this.urlPath,
                    modified: modified
                        ? App.currentUser.localizeDatetime(modified)
                        : 'Not modified yet',
                };
            },

            ui: {
                deleteItem : 'span.delete-item',
                copyLink   : '.copy-link',
                tooltip    : '[data-toggle="tooltip"]'
            },

            events: {
                'click @ui.deleteItem' : 'deleteItem',
                'click @ui.copyLink'   : 'copyLink'
            },

            onShow: function(){
                this.ui.tooltip.tooltip();
            },

            deleteItem: function(){
                var that = this,
                    name = this.model.get('name');

                utils.modalDialogDelete({
                    title: 'Delete "' + name + '"',
                    body: 'Are you sure you want to delete "' + name + '" predefined application?',
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            utils.preloader.show();
                            that.model.destroy({wait: true})
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow)
                                .done(function(){
                                    that.remove();
                                    utils.notifyWindow('Predefined application "' +
                                                           name + '" is removed',
                                                       'success');
                                });
                            that.render();
                        },
                        buttonCancel: true
                   }
               });
            },

            copyLink: function(){
                var link = this.urlPath + this.model.get('qualifier');
                utils.copyLink( link, 'Link copied to buffer');
            }
        });

        views.AppList = Marionette.CompositeView.extend({
            template            : listTpl,
            childView           : views.AppListItem,
            tagName             : 'div',
            className           : 'container',
            emptyView           : views.AppListEmpty,
            childViewContainer  : 'tbody',

            ui: {
                'th' : 'thead th'
            },

            events: {
                'click @ui.th' : 'toggleSort',
            },

            initialize: function(){
                this.counter = 1;
                this.collection.order = [{key: 'name', order: 1},
                                         {key: 'modified', order: -1}];
                this.collection.fullCollection.sort();
                this.collection.on('change', function(){ this.fullCollection.sort(); });
            },

            templateHelpers: function(){
                return {
                    sortingType : this.collection.orderAsDict(),
                };
            },

            toggleSort: function(e) {
                var targetClass = e.target.className;
                if (!targetClass) return;
                this.collection.toggleSort(targetClass);
                this.render();
            },
        });

        views.YAMLTextarea = Marionette.ItemView.extend({
            template: YAMLTextareaTpl,
            ui: {
                textarea: 'textarea',
                numbers: '.yaml-textarea-line-numbers',
            },
            events: {
                'input @ui.textarea': 'renderNumbers',
                'keyup @ui.textarea': 'renderNumbers',
            },
            onDomRefresh: function(){
                this.oldNumberOfLines = 0;
                this.renderNumbers();
                this.ui.textarea.on('scroll', _.bind(function(){
                    this.ui.numbers.scrollTop(this.ui.textarea.scrollTop());
                }, this));
            },
            renderNumbers: function(){
                var numberOfLines = this.ui.textarea.val().split('\n').length,
                    oldNumberOfLines = this.oldNumberOfLines || 0,
                    change = numberOfLines - oldNumberOfLines;
                if (!change) return;
                if (change < 0){
                    this.ui.numbers.find('div:nth-last-child(' + (1 - change) + ') ~ div').remove();
                } else {
                    this.ui.numbers.append(
                        _.map(_.range(oldNumberOfLines, numberOfLines), function(i){
                            return '<div class="yaml-textarea-number-' + (i + 1) +
                                ' yaml-textarea-number">' + (i + 1) + '</div>';
                        }).join('')
                    );
                }
                this.oldNumberOfLines = numberOfLines;
            },
        });

    return views;
});
