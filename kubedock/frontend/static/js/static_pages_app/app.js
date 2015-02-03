define(['marionette', 'ckeditor'], function () {
    var tree = $('#menus-tree');

    var StaticPages = new Backbone.Marionette.Application({
        regions: {
            contents: '#form-block'
        }
    });

    StaticPages.module('Data', function(Data, App, Backbone, Marionette, $, _){

        var unwrapper = function(response) {
            if (response.hasOwnProperty('data'))
                return response['data'];
            return response;
        };

        Data.MenuModel = Backbone.Model.extend({
            urlRoot: URLS.staticPages.api.menu,
            parse: unwrapper
        });
        Data.MenuItemModel = Backbone.Model.extend({
            urlRoot: URLS.staticPages.api.menuItem,
            parse: unwrapper
        });
        Data.MenuItemsCollection = Backbone.Collection.extend({
            url: URLS.staticPages.api.menuItem,
            model: Data.MenuItemModel
        });
        Data.PageModel = Backbone.Model.extend({
            urlRoot: URLS.staticPages.api.page + '/:id',
            parse: unwrapper
        });
    });

    StaticPages.module('Views', function(Views, App, Backbone, Marionette, $, _) {

        Views.MenuItemForm = Backbone.Marionette.ItemView.extend({
            template: '#menu-item-form-template',
            ui: {
                'unbind_page': 'input#id_unbind_page',
                'page_form': 'div#page-form',
                // Menu item fields
                'path': 'input#id_path',
                'name': 'input#id_name',
                'is_active': 'input#id_is_active',
                'assign_page': 'input#id_assign_page',
                'role_select': 'select#role-select',
                // Page fields
                'page_slug': 'input#id_slug',
                'page_title': 'input#id_title'
            },
            events: {
                'click button#save-btn': 'saveBtn',
                'click button#delete-btn' : 'deleteBtn',
                'change input#id_unbind_page': 'unbindPage',
                'change input#id_assign_page': 'assignPage',
                'keyup input#id_title': 'slugifyPageTitle'
            },
            onRender: function() {
                var data = this.model.attributes,
                    labelPath = this.ui.path.prev();
                console.log(data)
                this.ui.role_select.val(data.roles);
                if(data.absolute_url){
                    labelPath.html(
                        'Path: <i class="text-success"><a href="' + data.absolute_url +
                        '" target="_blank">' + data.absolute_url + '</a></i>');
                    if(data.absolute_url.substr(0, 5) == '/page'){
                        this.ui.path.val(data.absolute_url);
                        if(data.page) this.ui.path.prop('disabled', true);
                    }
                }
            },
            slugifyPageTitle: function(){
                return this.ui.page_slug.val(
                    this.ui.page_title.val()
                        .toLowerCase()
                        .replace(/-+/g, '')
                        .replace(/\s+/g, '-')
                        .replace(/[^a-z0-9-]/g, '')
                );
            },
            unbindPage: function(){
                var unbind_page = false;
                if(this.ui.unbind_page.is(':checked')){
                    unbind_page = confirm('Page will be deleted!');
                    this.ui.unbind_page.prop('checked', unbind_page);
                }
                if(unbind_page) {
                    this.ui.page_form.hide();
                    this.ui.path.prop('disabled', false);
                } else {
                    this.ui.page_form.show();
                    this.ui.path.prop('disabled', true);
                }
            },
            assignPage: function(){
                if(this.ui.assign_page.is(':checked'))
                    this.ui.path.prop('disabled', true);
                else
                    this.ui.path.prop('disabled', false);
            },
            saveBtn: function(){
                try{
                    var ui = this.ui;
                    var data = {
                        path: ui.path.val(),
                        name: ui.name.val(),
                        is_active: ui.is_active.is(':checked'),
                        assign_page: ui.assign_page.is(':checked'),
                        unbind_page: ui.unbind_page.is(':checked'),
                        roles: ui.role_select.val(),
                        page_slug: ui.page_slug.val(),
                        page_title: ui.page_title.val()
                    };
                    var key = this.model.id,
                        page_content_id = "id_content" + key;
                    if(key == 0) {
                        data['parent'] = this.model.attributes.parent;
                        data['region'] = this.model.attributes.region;
                    }
                    if(CKEDITOR.instances[page_content_id])
                        data['page_content'] = CKEDITOR.instances[page_content_id].getData();
                    //TODO: validation
                    $.ajax({
                        url: URLS.staticPages.api.menuItem + '/' + this.model.id,
                        type: 'PUT',
                        data: data,
                        dataType: 'JSON',
                        success: function(rs){
                            if(rs.status != 'OK') alert(rs.status);
                            else buildMenus();
                        },
                        error: function(rs){
                            console.log(rs)
//                            alert(rs.responseJSON.status);
                        }
                    });
                } catch (e){
                    console.log(e)
                }
                return false;
            },
            deleteBtn: function(){
                if(this.model.id == 0) return false;
                if(!confirm('Are you sure want delete this menu item? Assigned page will be deleted too!'))
                    return false;
                $.ajax({
                    url: URLS.staticPages.api.deleteMenuItem + '/' + this.model.id,
                    type: 'POST',
                    data: {oid: this.model.id},
                    dataType: 'JSON',
                    success: function(rs){
                        if(rs.error) alert(rs.error);
                        else{
                            window.location.reload();
                        }
                    }
                });

            }
        });
    });

    StaticPages.module('spCRUD', function(spCRUD, App, Backbone, Marionette, $, _){
        spCRUD.Controller = Marionette.Controller.extend({
            showMenusTree: function(){
                buildMenus();
            }
        });
        spCRUD.addInitializer(function(){
            var controller = new spCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    '': 'showMenusTree'
                }
            });
        });

    });

//    function

    function buildMenus(){
        tree.empty();
        $.ajax({
            url: URLS.staticPages.api.menuTree,
            success: function(rs){
                var data = rs.data;
                for(var region in data){
                    var tree_data = data[region],
                        li = $('<li>').attr('id', 'dynatree-' + region);
                    tree.append(li);
                    $('#dynatree-' + region).dynatree({
                        onActivate: function(node) {
                            if( node.data.href ){
                                StaticPages.router.navigate(node.data.href);
                            }
                        },
                        onCustomRender: function(node) {
                            var data = node.data.data,
                                $a = $('<a href="#" class="dynatree-title">').text(data.name);
                            if(!data.is_active) $a.addClass('inactive');
                            if(data.page) {
                                $a.addClass('has_page');
                                $a.append('&nbsp;<i class="glyphicon glyphicon-list-alt text-info"></i>');
                            }
                            return $a[0].outerHTML;
                        },
                        onCreate: function(node, nodeSpan) {},
                        onClick: function(node, event) {
                            var node_data = node.data.data, data, formView;
                            node_data['page_dict'] = null;
                            var page_content_id = 'id_content' + node_data.id;
                            if(node_data.t == 'item'){
                                if(node_data.page && node_data.page > 0){
                                    $.ajax({
                                        cache: false,
                                        url: URLS.staticPages.api.page + '/' + node_data.page,
                                        success: function(rs){
                                            node_data['page_dict'] = rs.data;
                                            data = new StaticPages.Data.MenuItemModel(node_data);
                                            formView = new StaticPages.Views.MenuItemForm({model: data});
                                            StaticPages.contents.show(formView);
                                            CKEDITOR.replace(page_content_id);
                                        }
                                    })
                                } else {
                                    data = new StaticPages.Data.MenuItemModel(node_data);
                                    formView = new StaticPages.Views.MenuItemForm({model: data});
                                    StaticPages.contents.show(formView);
                                }
                                $('#id_assign_page').unbind('change');
                                $('#id_assign_page').change(function(){
                                    if($(this).is(':checked')) {
                                        $('.new-page-form').show();
                                        CKEDITOR.replace(page_content_id);
                                    }
                                    else $('.new-page-form').hide();
                                });
                            }
                        },
                        dnd: {
                            preventVoidMoves: true, // Prevent dropping nodes 'before self', etc.
                            onDragStart: function(node) {
                                return true;
                            },
                            onDragEnter: function(node, sourceNode) {
        //                        if(node.parent !== sourceNode.parent)
        //                            return false;
                                console.log(node, sourceNode)
                                return ["before", "after"];
                            },
                            onDrop: function(node, sourceNode, hitMode, ui, draggable) {
                                sourceNode.move(node, hitMode);
                                console.log(node, sourceNode, hitMode)
                            }
                        },
                        persist: true,
                        children: [tree_data]
                    });
                }
                $('.add-menu-item').show();
            }
        });
    }

    /* TODO: make in with Marionette and Collections */
    $(document).ready(function(){
        $('.new-item-btn').on('click', function(){
            var region = $('#id_parent_item').find(':selected').data('region'),
                parent = $('#id_parent_item').val(),
                region_repr = $('#id_parent_item').find(':selected')
                    .closest('optgroup').attr('label');
            var data = new StaticPages.Data.MenuItemModel({
                id: 0,
                region: region,
                region_repr: region_repr,
                is_active: true,
                path: '',
                page_dict: {},
                parent: parent,
                absolute_url: ''
            });
            var formView = new StaticPages.Views.MenuItemForm({model: data});
            StaticPages.contents.show(formView);
            $('#id_assign_page').unbind('change');
            $('#id_assign_page').change(function(){
                if($(this).is(':checked')) {
                    $('.new-page-form').show();
                    CKEDITOR.replace('id_content0');
                }
                else $('.new-page-form').hide();
            });

        });

    });


    StaticPages.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: URLS.staticPages.index, pushState: true});
        }
    });
    return StaticPages;
});
