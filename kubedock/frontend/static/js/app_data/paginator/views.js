define(['app_data/app', 'tpl!app_data/paginator/paginator.tpl'], function(App, paginatorTpl){

    var paginator = {};

    paginator.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: paginatorTpl,

        initialize: function(options) {
            this.model = new Backbone.Model({
                v: options.view,
                c: options.view.collection
            });
            this.listenTo(options.view.collection, 'remove', this.render);
            this.listenTo(options.view.collection, 'reset', this.render);
        },

        events: {
            'click li.pseudo-link' : 'paginateIt'
        },

        paginateIt: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target);
            if (tgt.hasClass('paginatorFirst')) this.model.get('c').getFirstPage();
            else if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
            else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
            else if (tgt.hasClass('paginatorLast')) this.model.get('c').getLastPage();
            this.model.get('v').render();
            this.render();
        }
    });

    return paginator;

});