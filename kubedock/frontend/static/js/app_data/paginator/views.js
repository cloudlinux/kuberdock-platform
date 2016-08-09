define(['app_data/app', 'tpl!app_data/paginator/paginator.tpl'], function(App, paginatorTpl){

    var paginator = {};

    paginator.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: paginatorTpl,

        initialize: function(options){
            this.model = new Backbone.Model({
                v: options.view,
                c: options.view.collection
            });
            this.listenTo(options.view.collection, 'update reset', this.render);
        },

        events: {
            'click li.pseudo-link' : 'paginateIt'
        },

        paginateIt: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target);
            if (tgt.hasClass('disabled')) return;
            if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
            else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
            this.model.get('v').render();
            this.render();
        },
    });

    return paginator;

});
