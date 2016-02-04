define(['app_data/app', 'app_data/utils', 'marionette',
        'tpl!app_data/papps/templates/main.tpl',
        'tpl!app_data/papps/templates/breadcrumbs.tpl',
        'tpl!app_data/papps/templates/app_list_empty.tpl',
        'tpl!app_data/papps/templates/app_list_item.tpl',
        'tpl!app_data/papps/templates/app_list.tpl',
        'tpl!app_data/papps/templates/app_load_form.tpl',
        'bootstrap'],
    function(App, utils, Marionette, mainTpl, breadcrumbsTpl, appListEmptyTpl,
             appListItemTpl, appListTpl, appLoadFormTpl){
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
                this.listenTo(this.breadcrumbs, 'show', function(view){
                    that.listenTo(view, 'app:showloadcontrol', that.showLoadControl);
                });
                this.listenTo(this.main, 'show', function(view){
                    that.listenTo(view, 'app:save', that.saveApp);
                    that.listenTo(view, 'app:cancel', that.cancelApp);
                    that.listenTo(view, 'app:edit', that.editApp);
                });
            },

            onBeforeShow: function(){
                utils.preloader.show();
            },

            onShow: function(){
                utils.preloader.hide();
            },

            ui: {
                'cancel' : '.cancel-app'
            },

            triggers: {
                'click @ui.cancel' : 'app:cancel'
            },

            showLoadControl: function(){
                this.trigger('app:showloadcontrol');
            },

            saveApp: function(data){
                this.trigger('app:save', data);
            },

            cancelApp: function(){
                this.trigger('app:cancel');
            },

            editApp: function(id){
                this.trigger('app:showloadcontrol', id);
            }
        });

        views.Breadcrumbs = Marionette.ItemView.extend({
            template: breadcrumbsTpl,
            tagName: 'div',
            className: 'breadcrumbs-wrapper',

            ui: {
                'pod_search'  : 'input#nav-search-input',
                'navSearch'   : '.nav-search',
                'addItem'     : 'a#add_pod'
            },

            events: {
                'keyup @ui.pod_search'  : 'filterCollection',
                'click @ui.navSearch'   : 'showSearch',
                'blur @ui.pod_search'   : 'closeSearch',
                'click @ui.addItem'     : 'showLoadControl'
            },

            filterCollection: function(evt){
                evt.stopPropagation();
                this.trigger('collection:filter', evt.target.value);
            },

            showSearch: function(){
                this.ui.navSearch.addClass('active');
                this.ui.pod_search.focus();
            },

            closeSearch: function(){
                this.ui.navSearch.removeClass('active');
            },

            showLoadControl: function(evt){
                evt.stopPropagation();
                evt.preventDefault();
                this.trigger('app:showloadcontrol');
            },

            triggerUpload: function(evt){
                evt.stopPropagation();
                evt.preventDefault();
                this.trigger('app:triggerUpload');
            }
        });

        views.AppLoader = Marionette.ItemView.extend({
            template: appLoadFormTpl,
            tagName : 'div',

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
                'change @ui.uploader' : 'handleUpload'
            },

            triggers: {
                'click @ui.cancel' : 'app:cancel'
            },

            templateHelpers: function(){
                return {
                    isNew: this.model.id === undefined,
                };
            },

            handleUpload: function(evt){
                var file = evt.target.files[0],
                    reader = new FileReader(),
                    that = this;
                reader.onload = function(evt){
                    that.ui.display.empty().append(evt.target.result);
                };
                reader.readAsText(file);
            },

            saveApp: function(env){
                env.stopPropagation();
                env.preventDefault();
                var name = this.ui.appname.val(),
                    origin = this.ui.origin.val(),
                    template = this.ui.display.val();
                if ((!name) || (!template)) {
                    utils.notifyWindow('Name and template is expected to be filled');
                    return;
                }
                this.model.set({name: name, origin: origin, template: template});
                this.trigger('app:save', this.model);
            }
        });

        views.AppListEmpty = Marionette.ItemView.extend({
            template : appListEmptyTpl,
            tagName  : 'tr',
        });

        views.AppListItem = Marionette.ItemView.extend({
            template    : appListItemTpl,
            tagName     : 'tr',

            initialize: function(){
                this.urlPath = window.location.protocol
                        + '//'
                        + window.location.host
                        + '/apps/';
            },

            templateHelpers: function(){
                var modified = this.model.get('modified');

                return {
                    urlPath: this.urlPath,
                    modified: modified ? App.currentUser.localizeDatetime(modified) : 'Not modified yet',
                };
            },

            ui: {
                deleteItem : 'span.delete-item',
                editItem   : 'span.edit-item',
                copyLink   : '.copy-link'
            },

            events: {
                'click @ui.deleteItem' : 'deleteItem',
                'click @ui.editItem'   : 'editItem',
                'click @ui.copyLink'   : 'copyLink'
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

            editItem: function(){
                this.trigger('app:edit:item', this.model.get('id'));
            },

            copyLink: function(evt){
                var successful,
                    target = $(evt.target),
                    link = target.parent().find('textarea');

                link.select();
                successful = document.execCommand('copy');

                if (successful) {
                    utils.notifyWindow('Link copied to buffer', 'success');
                } else {
                    utils.notifyWindow('Your browser does not support this action. Click on application name and copy link from address bar.');
                }
            }
        });

        views.AppList = Marionette.CompositeView.extend({
            template            : appListTpl,
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

            childEvents: {
                'app:edit:item': 'appEditItem'
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

            appEditItem: function(view, id){
                this.trigger('app:edit', id);
            },

            toggleSort: function(e) {
                var targetClass = e.target.className;
                if (!targetClass) return;
                this.collection.toggleSort(targetClass);
                this.render();
            },
        });

    return views;
});
