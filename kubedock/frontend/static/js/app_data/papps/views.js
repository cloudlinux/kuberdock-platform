import App from 'app_data/app';
import * as utils from 'app_data/utils';

import mainTpl from 'app_data/papps/templates/main.tpl';
import listEmptyTpl from 'app_data/papps/templates/app_list/empty.tpl';
import listItemTpl from 'app_data/papps/templates/app_list/item.tpl';
import listTpl from 'app_data/papps/templates/app_list/list.tpl';
import appLoadFormTpl from 'app_data/papps/templates/load_form.tpl';
import YAMLTextareaTpl from 'app_data/papps/templates/yaml_textarea.tpl';

import jsyaml from 'js-yaml';
import 'tooltip';

export const MainLayout = Marionette.LayoutView.extend({
    template: mainTpl,

    regions: {
        nav: '#nav',
        breadcrumbs: '#breadcrumbs',
        main: '#main',
        pager: '#footer',
    },

    initialize(){
        let that = this;
        this.listenTo(this.main, 'show', function(view){
            that.listenTo(view, 'app:save', that.saveApp);
            that.listenTo(view, 'app:saveAnyway', that.saveAppAnyway);
        });
    },

    saveApp(data){ this.trigger('app:save', data); },
    saveAppAnyway(data){ this.trigger('app:saveAnyway', data); },
});

export const YAMLTextarea = Marionette.ItemView.extend({
    template: YAMLTextareaTpl,
    ui: {
        textarea : 'textarea',
        numbers : '.yaml-textarea-line-numbers',
    },
    events: {
        'input @ui.textarea' : 'renderNumbers',
        'keyup @ui.textarea' : 'renderNumbers',
    },
    onDomRefresh(){
        this.oldNumberOfLines = 0;
        this.renderNumbers();
        this.ui.textarea.on('scroll', () => {
            this.ui.numbers.scrollTop(this.ui.textarea.scrollTop());
        });
    },
    renderNumbers(){
        let numberOfLines = this.ui.textarea.val().split('\n').length,
            oldNumberOfLines = this.oldNumberOfLines || 0,
            change = numberOfLines - oldNumberOfLines;
        if (!change) return;
        if (change < 0){
            this.ui.numbers.find(`div:nth-last-child(${1 - change}) ~ div`).remove();
        } else {
            this.ui.numbers.append(
                _.map(_.range(oldNumberOfLines, numberOfLines), function(i){
                    return `<div class="yaml-textarea-number-${i + 1} yaml-textarea-number">
                            ${i + 1}</div>`;
                }).join('')
            );
        }
        this.oldNumberOfLines = numberOfLines;
    },
});

export const AppLoader = Marionette.LayoutView.extend({
    template: appLoadFormTpl,
    tagName: 'div',
    regions: {
        textarea: '.yaml-textarea-wrapper'
    },

    ui: {
        uploader : 'input#app-upload',
        display  : 'textarea#app-contents',
        appname  : 'input#app-name',
        save     : 'button.save-app',
        cancel   : '.cancel-app',
        origin   : 'input#app-origin'
    },

    events: {
        'click @ui.save'      : 'saveApp',
        'change @ui.uploader' : 'handleUpload',
        'focus @ui.appname'   : 'removeError',
        'focus @ui.display'   : 'removeError'
    },

    onDomRefresh(){
        this.textarea.show(new YAMLTextarea({model: this.model}));
        this.bindUIElements();
        if (this.logScroll === null)  // stick to bottom
            this.ui.display.scrollTop(this.ui.display[0].scrollHeight);
        else  // stay at the same position
            this.ui.display.scrollTop(this.logScroll);
    },

    templateHelpers(){
        return {
            isNew: this.model.isNew(),
            jsyaml: jsyaml,
            errorData: this.errorData
        };
    },

    handleUpload(evt){
        let file = evt.target.files[0],
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

    removeError(evt){
        let target = $(evt.target);

        if (target.hasClass('error')) target.removeClass('error');
        if (this.ui.save.hasClass('anyway')){
            this.ui.save.removeClass('anyway');
            this.ui.save.text(this.model.isNew() ? 'Add' : 'Save');
        }
    },

    saveApp(env){
        env.stopPropagation();
        env.preventDefault();
        let target = $(env.target),
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

export const AppListEmpty = Marionette.ItemView.extend({
    template : listEmptyTpl,
    tagName : 'tr',
});

export const AppListItem = Marionette.ItemView.extend({
    template : listItemTpl,
    tagName : 'tr',

    initialize(){
        this.urlPath = `${window.location.protocol}//${window.location.host}/apps/`;
    },

    templateHelpers(){
        let modified = this.model.get('modified');

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

    onShow(){ this.ui.tooltip.tooltip(); },

    deleteItem(){
        let that = this,
            name = this.model.get('name');

        utils.modalDialogDelete({
            title: `Delete "${name}"`,
            body: `Are you sure you want to delete "${name}" predefined application?`,
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
                            utils.notifyWindow(`Predefined application "${name}" is removed`,
                                               'success');
                        });
                    that.render();
                },
                buttonCancel: true
           }
       });
    },

    copyLink(){
        let link = this.urlPath + this.model.get('qualifier');
        utils.copyLink(link, 'Link copied to buffer');
    }
});

export const AppList = Marionette.CompositeView.extend({
    template : listTpl,
    childView : AppListItem,
    tagName : 'div',
    className : 'container',
    emptyView : AppListEmpty,
    childViewContainer : 'tbody',
    ui: { th : 'thead th' },
    events: { 'click @ui.th' : 'toggleSort' },

    initialize(){
        this.counter = 1;
        this.collection.order = [{key: 'name', order: 1},
                                 {key: 'modified', order: -1}];
        this.collection.fullCollection.sort();
        this.collection.on('change', function(){ this.fullCollection.sort(); });
    },

    templateHelpers(){
        return {
            sortingType : this.collection.orderAsDict(),
        };
    },

    search(data){
        this.collection.searchString = data;
        this.collection.refilter();
    },

    toggleSort(e) {
        let targetClass = e.target.className;
        if (!targetClass) return;
        this.collection.toggleSort(targetClass);
        this.render();
    },
});
