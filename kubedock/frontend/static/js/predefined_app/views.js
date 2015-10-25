define(['app', 'marionette',
        'tpl!predefined_app/templates/main.tpl',
        'tpl!predefined_app/templates/breadcrumbs.tpl',
        'tpl!predefined_app/templates/app_list_empty.tpl',
        'tpl!predefined_app/templates/app_list_item.tpl',
        'tpl!predefined_app/templates/app_list.tpl',
        'tpl!predefined_app/templates/app_load_form.tpl',
        '../utils', 'bootstrap'],
       function(App, Marionette,
                mainTpl, breadcrumbsTpl, appListEmptyTpl,
                appListItemTpl, appListTpl, appLoadFormTpl, utils){

        var views = {};

        views.MainLayout = Marionette.LayoutView.extend({
            template: mainTpl,

            regions: {
                breadcrumbs: '#breadcrumbs',
                main: '#main'
            },

            initialize: function(){
                var that = this;
                console.log(this);
                this.listenTo(this.breadcrumbs, 'show', function(view){
                    that.listenTo(view, 'app:showloadcontrol', that.showLoadControl);
                });
                this.listenTo(this.main, 'show', function(view){
                    that.listenTo(view, 'app:save', that.saveApp);
                    that.listenTo(view, 'app:cancel', that.cancelApp);
                    that.listenTo(view, 'app:edit', that.editApp);
                });
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
                'cancel'   : '.cancel-app'
            },

            events: {
                'click @ui.save'      : 'saveApp',
                'change @ui.uploader' : 'handleUpload'
            },

            triggers: {
                'click @ui.cancel' : 'app:cancel'
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
                    template = this.ui.display.val();
                if ((!name) || (!template)) {
                    utils.notifyWindow('Name and template is expected to be filled');
                    return;
                }
                this.model.set({name: name,
                    template: template});
                this.trigger('app:save', this.model);
                $.notify('Predefined application "' + name + '" is added', {
                    autoHideDelay: 5000,
                    clickToHide: true,
                    globalPosition: 'bottom left',
                    className: 'success'
                });
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
                return {
                    urlPath: this.urlPath
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
                    name = this.model.get('name'),
                    preloader = $('#page-preloader');

                utils.modalDialogDelete({
                    title: 'Delete "' + name + '"',
                    body: 'Are you sure want to delete "' + name + '" predefined application?',
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            that.model.destroy({
                                wait: true,
                                success: function(){
                                    preloader.hide();
                                    that.remove();
                                    $.notify('Predefined application "' + name + '" is removed', {
                                        autoHideDelay: 5000,
                                        clickToHide: true,
                                        globalPosition: 'bottom left',
                                        className: 'success',
                                    });
                                },
                                error: function(){
                                    preloader.hide();
                                }
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

            copyLink: function(){
                $.notify('Link copied to buffer', {
                    autoHideDelay: 5000,
                    clickToHide: true,
                    globalPosition: 'bottom left',
                    className: 'success',
                });
            }
        });

        views.AppList = Marionette.CompositeView.extend({
            template            : appListTpl,
            childView           : views.AppListItem,
            tagName             : 'div',
            className           : 'container',
            emptyView           : views.AppListEmpty,
            childViewContainer  : 'tbody',

            childEvents: {
                'app:edit:item': 'appEditItem'
            },

            appEditItem: function(view, id){
                this.trigger('app:edit', id);
            }
        });

    return views;
});