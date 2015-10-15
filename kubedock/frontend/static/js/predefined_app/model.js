define(['predefined_app/app', 'backbone', 'backbone-paginator'], function(Apps, Backbone){
    
    var unwrapper,
        data = {};
    
    unwrapper = function(data){
        if (data.hasOwnProperty('data')) {
            return data['data'];
        }
        else {
            return data;
        }
    };
    
    data.AppModel = Backbone.Model.extend({
        defaults: {
            name: '',
            template: '',
            qualifier: ''
        },
        urlRoot: '/api/predefined-apps',
        parse: unwrapper
    });
    
    data.AppCollection = Backbone.PageableCollection.extend({
        url: '/api/predefined-apps',
        model: data.AppModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        },
    });
    return data;
});