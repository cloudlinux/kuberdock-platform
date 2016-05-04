define([
    'app_data/app', 'app_data/utils',
    'app_data/breadcrumbs/views',
    'bootstrap-editable'
], function(App, utils, Breadcrumbs){

    var views = {};

    views.EditableName = Breadcrumbs.Text.extend({
        class: 'peditable',

        save: function(name){
            var successMsg = 'New pod name "' + name + '" is saved';
            this.model.set({name: name});
            if (this.model.isNew()){
                utils.notifyWindow(successMsg, 'success');
            } else {
                utils.preloader.show();
                this.model.command('set', {name: name})
                    .always(utils.preloader.hide).fail(utils.notifyWindow)
                    .done(function(){ utils.notifyWindow(successMsg, 'success'); });
            }
        },

        onRender: function(){
            var that = this;
            App.getPodCollection().done(function(podCollection){
                that.$el.editable({
                    type: 'text',
                    mode: 'inline',
                    value: that.model.get('name'),
                    success: function(response, newValue){ that.save(newValue); },
                    validate: function(newValue){
                        newValue = newValue.trim();

                        var msg;
                        if (!newValue)
                            msg = 'Please, enter pod name.';
                        else if (newValue.length > 63)
                            msg = 'The maximum length of the Pod name must be less than 63 characters.';
                        else if (_.without(podCollection.where({name: newValue}), that.model).length)
                            msg = 'Pod with name "' + newValue + '" already exists. Try another name.';

                        if (msg){
                            // TODO: style for ieditable error messages
                            // (use it instead of notifyWindow)
                            utils.notifyWindow(msg);
                            return ' ';
                        }
                    }
                });
            });
        },
    });

    return views;
});
