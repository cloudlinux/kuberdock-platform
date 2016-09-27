define([
    'app_data/app', 'app_data/model', 'app_data/utils',
    'app_data/pods/templates/messages/layout.tpl',
    'app_data/pods/templates/messages/pod_has_changes.tpl',
    'app_data/pods/templates/messages/post_description.tpl',
    'bbcode-parser', 'tooltip'
], function(
    App, Model, utils,
    layoutTpl,
    podHasChangesTpl,
    postDescriptionTpl,
    BBCodeParser
){

    var views = {};

    views.Layout = Backbone.Marionette.LayoutView.extend({
        template: layoutTpl,
        regions: {
            postDescription: '.post-description-message',
            podHasChanges: '.pod-has-changes-message',
        },
    });

    views.PodHasChanges = Backbone.Marionette.ItemView.extend({
        template: podHasChangesTpl,
        className: 'message-wrapper edit-pod',

        events: {
            'click .pay-and-apply'    : 'applyChanges',
            'click .apply'            : 'applyChanges',
            'click .reset-changes'    : 'resetChanges',
        },

        modelEvents: {
            'change': 'render',
            'apply-changes-start': 'render',
        },

        initialize: function(options){ this.fixedPrice = !!options.fixedPrice; },

        templateHelpers: function(){
            var pkg = App.userPackage,
                changesRequirePayment;

            this.model.recalcInfo(pkg);

            if (this.model.get('edited_config')){
                this.model.get('edited_config').recalcInfo(pkg);
                var diff = this.model.get('edited_config').rawTotalPrice - this.model.rawTotalPrice;
                if (diff > 0)
                    changesRequirePayment = pkg.getFormattedPrice(diff);
            }

            return {
                changesRequirePayment: changesRequirePayment,
                fixedPrice: this.fixedPrice,
                period: pkg.get('period'),
                ableTo: _.bind(this.model.ableTo, this.model),
            };
        },

        onRender: function(){
            this.$el.toggleClass('show', this.model.isChanged());
        },

        applyChanges: function(){
            var model = this.model;
            utils.preloader.show();
            model.cmdApplyChanges()
                .always(utils.preloader.hide)
                .done(function(){
                    utils.notifyWindow('Pod will be restarted with the new '
                                       + 'configuration soon', 'success');
                });
        },
        resetChanges: function(){
            var that = this,
                oldEdited = this.model.get('edited_config');
            utils.modalDialog({
                title: 'Are you sure?',
                body: 'Reset all unapplied changes?',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.$el.slideUp({
                            complete: function(){
                                utils.preloader.show();
                                that.model.set('edited_config', null).command('edit')
                                    .always(utils.preloader.hide)
                                    .fail(utils.notifyWindow, function(){
                                        that.model.set('edited_config', oldEdited);
                                    });
                            },
                        });
                    },
                    buttonCancel: true,
                    buttonOkText: 'Reset',
                }
            });
        },
    });

    views.PostDescription = Backbone.Marionette.ItemView.extend({
        template: postDescriptionTpl,
        className: 'message-wrapper post-description',

        ui: {
            close : 'span.close',
        },
        events: {
            'click @ui.close': 'closeMessage'
        },
        modelEvents: {
            'change': 'render',
        },

        templateHelpers: function(){
            var rawPostDescription = this.model.get('postDescription');
            return {
                postDescription: this.preparePostDescription(rawPostDescription),
            };
        },

        onRender: function(){
            this.$el.toggleClass('show', !!this.model.get('postDescription'));
        },
        closeMessage: function(){
            var model = this.model;
            this.$el.slideUp({
                complete: function(){
                    model.unset('postDescription');
                    model.command('set', {postDescription: null});
                }
            });
        },

        preparePostDescription: function(val){
            if (val == null)
                return;
            var publicIP = this.model.get('public_ip');
            val = val.replace(/(%PUBLIC_ADDRESS%)/gi, (
                (publicIP !== 'true' && publicIP) ||
                this.model.get('public_aws') ||
                this.model.get('domain') || '...'));
            var parser = new BBCodeParser(BBCodeParser.defaultTags());
            return parser.parseString(val);
        },
    });

    return views;
});
