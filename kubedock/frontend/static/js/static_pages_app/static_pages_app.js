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
            urlRoot: URLS.staticPages.api.menu + '/:id',
            parse: unwrapper
        });
        Data.MenuItemModel = Backbone.Model.extend({
            urlRoot: URLS.staticPages.api.menuItem + '/:id',
            parse: unwrapper
        });
        Data.PageModel = Backbone.Model.extend({
            urlRoot: URLS.staticPages.api.page + '/:id',
            parse: unwrapper
        });
    });

    StaticPages.module('Views', function(Views, App, Backbone, Marionette, $, _) {
        Views.MenuForm = Backbone.Marionette.ItemView.extend({
            template: '#menu-form-template',
            events: {
                'click button#save-btn': 'saveBtn',
                'click button#cancel-btn' : 'cancelBtn'
            },
            cancelBtn: function(){
//                App.router.navigate('/edit/' + this.model.id + '/', {trigger: true});
            },
            saveBtn: function(){
                alert('123');
                return false;
                var data = {
                    region: this.ui.id_region.val(),
                    name: this.ui.id_name.val(),
                    is_active: this.ui.id_is_active.val()
                };
                //TODO: validation
                this.model.set(data);
                this.model.save(undefined, {
                    wait: true,
                    success: function(rs){
                        alert(rs)
//                        App.router.navigate('/', {trigger: true})
                    },
                    error: function(){
                        alert('error while updating! Maybe some fields required.')
                    }
                });
            }
        });
        Views.MenuItemForm = Backbone.Marionette.ItemView.extend({
            template: '#menu-item-form-template',
            events: {
                'click button#save-btn': 'saveBtn',
                'click button#cancel-btn' : 'cancelBtn',
                'click button#delete-btn' : 'deleteBtn'
            },
            cancelBtn: function(){
//                App.router.navigate('/edit/' + this.model.id + '/', {trigger: true});
            },
            saveBtn: function(){
                try{
                    var data = {
                        path: $('#id_path').val(),
                        name: $('#id_name').val(),
                        is_active: $('#id_is_active').val(),
                        assign_page: $('#id_assign_page').val(),
                        page_slug: $('#id_slug').val(),
                        page_title: $('#id_title').val()
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
                        url: URLS.staticPages.api.menuItem + this.model.id,
                        type: 'POST',
                        data: data,
                        dataType: 'JSON',
                        success: function(rs){
                            if(rs.error) alert(rs.error);
                            else{
                                buildMenus();
                            }
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
                    url: URLS.staticPages.api.deleteMenuItem + this.model.id,
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
                        onCreate: function(node, nodeSpan) {},
                        onClick: function(node, event) {
                            var node_data = node.data.data, data, formView;
                            node_data['page_dict'] = null;
                            var page_content_id = 'id_content' + node_data.id;
                            if(node_data.t == 'item'){
                                if(node_data.page && node_data.page > 0){
                                    $.ajax({
                                        cache: false,
                                        url: URLS.staticPages.api.page + node_data.page,
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
                            } else {
                                data = new StaticPages.Data.MenuModel(node_data);
                                formView = new StaticPages.Views.MenuForm({model: data});
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
                parent = $('#id_parent_item').val();
            var data = new StaticPages.Data.MenuItemModel({
                id: 0,
                region: region,
                is_active: true,
                path: '',
                page_dict: {},
                parent: parent
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
