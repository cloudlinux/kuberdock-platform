define(['marionette', 'paginator'],
       function (Marionette, PageableCollection) {

    var NotificationsApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    NotificationsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        var unwrapper = function(response) {
            if (response.hasOwnProperty('data'))
                return response['data'];
            return response;
        };

        Data.TemplateModel = Backbone.Model.extend({
            urlRoot: '/api/notifications/',
            parse: unwrapper
        });
        Data.TemplatesCollection = Backbone.Collection.extend({
            url: '/api/notifications/',
            model: Data.TemplateModel
        });

    });

    NotificationsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        Views.TemplateItem = Backbone.Marionette.ItemView.extend({
            template: '#template-item-template',
            tagName: 'tr',

            events: {
                'click button#deleteTemplate': 'deleteTemplate_btn',
                'click button#editTemplate' : 'editTemplate_btn'
            },

            deleteTemplate_btn: function(){
                var n = App.Data.templates.get(this.model.id).attributes.name;
                if(!confirm('Are you sure you want to delete "' + n + '" event template?'))
                    return false;
                this.model.destroy({wait: true});
            },

            editTemplate_btn: function(){
                App.router.navigate('/edit/' + this.model.id + '/', {trigger: true});
            }

        });

        Views.TemplatesEmptyListView = Backbone.Marionette.ItemView.extend({
            template: '#template-emptyitem-template'
        });

        Views.TemplatesListView = Backbone.Marionette.CompositeView.extend({
            template: '#templates-list-template',
            childView: Views.TemplateItem,
            childViewContainer: "tbody",
            emptyView: Views.TemplatesEmptyListView,

            events: {
                'click button#create_template' : 'createTemplate'
            },

            createTemplate: function(){
                App.router.navigate('/create/', {trigger: true});
            }
        });

        Views.TemplateCreateView = Backbone.Marionette.ItemView.extend({
            template: '#template-create-template',

            ui: {
                'event'      : 'select#id_event',
                'text_plain' : 'textarea#id_text_plain',
                'text_html'  : 'textarea#id_text_html',
                'as_html'    : 'input#id_as_html',
                'event_keys' : '#event_keys'
            },

            events: {
                'click button#template-add-btn': 'onSave',
                'change select#id_event': 'onSelectEvent'
            },
            onRender: function() {
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));
            },

            onSave: function(){
                // temp validation
                App.Data.templates.create({
                    'event': this.ui.event.val(),
                    'text_plain': this.ui.text_plain.val(),
                    'text_html': this.ui.text_html.val(),
                    'as_html': this.ui.as_html.prop('checked')
                }, {
                    wait: true,
                    success: function(){
                        App.router.navigate('/', {trigger: true})
                    },
                    error: function(){
                        alert('error while saving! Maybe some fields required.')
                    }
                });
            },
            onSelectEvent: function(){
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));
            }

        });

        Views.TemplatesEditView = Views.TemplateCreateView.extend({     // inherit

            onRender: function(){
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));

                this.ui.event.val(this.model.get('event')).attr('disabled', true);
                this.ui.text_plain.val(this.model.get('text_plain'));
                this.ui.text_html.val(this.model.get('text_html'));
                this.ui.as_html.prop('checked', this.model.get('as_html'));
            },

            onSave: function(){
                // temp validation
                var data = {
                    'event': this.ui.event.val(),
                    'text_plain': this.ui.text_plain.text(),
                    'text_html': this.ui.text_html.text(),
                    'as_html': this.ui.as_html.prop('checked')
                };

                this.model.set(data);

                this.model.save(undefined, {
                    wait: true,
                    success: function(){
                        App.router.navigate('/', {trigger: true})
                    },
                    error: function(){
                        alert('error while updating! Maybe some fields required.')
                    }
                });
            }

        });

        Views.TemplatsLayout = Marionette.LayoutView.extend({
            template: '#templates-layout-template',
            regions: {
                main: 'div#main',
                pager: 'div#pager'
            }
        });
    });


    NotificationsApp.module('NotificationsCRUD', function(NotificationsCRUD, App, Backbone, Marionette, $, _){

        NotificationsCRUD.Controller = Marionette.Controller.extend({
            showTemplates: function(){
                var layout_view = new App.Views.TemplatsLayout();
                var collection = NotificationsApp.Data.templates;
                var templates_list_view = new App.Views.TemplatesListView({
                    collection: collection});
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(templates_list_view);
                });
                App.contents.show(layout_view);
            },

            showCreateTemplate: function(){
                var layout_view = new App.Views.TemplatsLayout();
                var template_create_view = new App.Views.TemplateCreateView();

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(template_create_view);
                });

                App.contents.show(layout_view);
            },

            showEditTemplate: function(template_id){
                var layout_view = new App.Views.TemplatsLayout();
                var template_edit_view = new App.Views.TemplatesEditView({
                    model: App.Data.templates.get(parseInt(template_id))
                });
                this.listenTo(layout_view, 'show', function () {
                    layout_view.main.show(template_edit_view);
                    $('#template-header h2').text('Edit');
                });
                App.contents.show(layout_view);
            }
        });

        NotificationsCRUD.addInitializer(function(){
            var controller = new NotificationsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    '': 'showTemplates',
                    'create/': 'showCreateTemplate',
                    'edit/:id/': 'showEditTemplate'
                }
            });
        });

    });

    NotificationsApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/notifications/', pushState: true});
        }
    });
    return NotificationsApp;
});
