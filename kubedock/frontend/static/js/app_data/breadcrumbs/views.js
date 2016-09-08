define([
    'app_data/model',
    'app_data/breadcrumbs/templates/breadcrumb_layout.tpl',
    'app_data/breadcrumbs/templates/breadcrumb_controls.tpl',
    'tooltip'
], function(Model, breadcrumbLayoutTpl, breadcrumbControlsTpl){

    var views = {};

    /**
     * Common breadcrumbs layout.
     *
     * It contains default region called "controls", for controls on the right
     * side of breadcrumbs, and list of regions for provided points.
     *
     * @param {string[]} options.points - list of strings. Each point will make
     *  a region to attach link, plain text or enything else.
     */
    views.Layout = Backbone.Marionette.LayoutView.extend({
        template: breadcrumbLayoutTpl,
        className: 'breadcrumbs-wrapper',
        tagName: 'div',
        regions: function(options){
            var regions = {controls: '.control-group'};
            _.each(options.points, function(point, i){
                regions[point] = '.breadcrumb li:eq(' + i + ')';
            });
            return regions;
        },

        initialize: function(options){ this.points = options.points; },
        templateHelpers: function(){ return {points: this.points}; },
    });

    /**
     * Use this to add plain text beadcrumb-point
     *
     * @param options.text
     */
    views.Text = Backbone.Marionette.ItemView.extend({
        tagName: 'span',
        initialize: function() {
            this.template = _.wrap(this.getOption('text'), _.escape);
        },
    });

    /**
     * Use this to add link beadcrumb-point
     *
     * @param options.text
     * @param options.href
     */
    views.Link = views.Text.extend({
        tagName: 'a',
        attributes: function(){ return {href: this.getOption('href')}; },
    });


    /**
     * Base view for controls in the breadcrumbs.
     *
     * @param {Model.BreadcrumbsControls} options.model
     * or plain attributes of model:
     * @param {boolean} options.search - to show search or not
     * @param {boolean|Object} options.button -
     *      false - to hide button, or
     *      {id, title, href} - button spec
     */
    views.Controls = Backbone.Marionette.ItemView.extend({
        template: breadcrumbControlsTpl,
        tagName: 'div',

        ui: {
            'searchButton' : '.nav-search',
            'search'       : 'input#nav-search-input',
            'tooltip'      : '[data-toggle="tooltip"]'
        },

        events: {
            'keyup @ui.search'      : 'search',
            'click @ui.searchButton': 'showSearch',
            'blur @ui.search'       : 'closeSearch',
        },

        initialize: function(options){
            this.model = options.model || new Model.BreadcrumbsControls(options);
        },

        onRender: function() {
            this.ui.tooltip.tooltip();
        },

        search: function(evt){
            this.trigger('search', evt.target.value.trim());
        },

        showSearch: function(){
            this.ui.searchButton.addClass('active');
            this.ui.search.focus();
        },

        closeSearch: function(){
            if (this.ui.search.val().trim() === '')
                this.ui.searchButton.removeClass('active');
        }
    });

    return views;
});
