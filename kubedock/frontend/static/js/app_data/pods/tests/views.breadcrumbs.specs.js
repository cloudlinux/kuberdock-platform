define(['pods_app/views/breadcrumbs', 'jasmine-jquery'], function(views){

    describe("When breadcrumbs", function(){

        it("have only one item one 'li' element is shown only", function(){
            var breadcrumbsData = {breadcrumbs: [{name: 'test-name'}],
                                  buttonID: 'test-id',
                                  buttonTitle: 'test-title',
                                  buttonLink: 'test-link'},
                breadcrumbsModel = new Backbone.Model(breadcrumbsData),
                breadcrumbs = new views.Breadcrumbs({model: breadcrumbsModel}),
                view = breadcrumbs.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures').toContainElement('div#breadcrumbs');
            expect('#jasmine-fixtures ul.breadcrumb > li').toHaveLength(1);
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(0)).toContainText('test-name');
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(0)).toHaveClass('active');
        });

        it("have more than one item some links are shown and 'li' element is shown last", function(){
            var breadcrumbsData = {breadcrumbs: [{name: 'test-first', href: 'test-first-link'},
                                                 {name: 'test-last'}],
                                  buttonID: 'test-id',
                                  buttonTitle: 'test-title',
                                  buttonLink: 'test-link'},
                breadcrumbsModel = new Backbone.Model(breadcrumbsData),
                breadcrumbs = new views.Breadcrumbs({model: breadcrumbsModel}),
                view = breadcrumbs.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures').toContainElement('div#breadcrumbs');
            expect('#jasmine-fixtures ul.breadcrumb > li').toHaveLength(2);
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(0)).toContainElement('a');
            expect('#jasmine-fixtures ul.breadcrumb > li:eq(0) > a').toHaveAttr('href', 'test-first-link');
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(1)).toHaveText('test-last');
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(1)).toHaveClass('active');
        });

        it("list table has 'add new container' button and search field", function(){
            var breadcrumbsData = {breadcrumbs: [{name: 'test-first', href: 'test-first-link'},
                                                 {name: 'test-last'}],
                                  buttonID: 'test-id',
                                  buttonTitle: 'test-title',
                                  buttonLink: 'test-link'},
                breadcrumbsModel = new Backbone.Model(breadcrumbsData),
                breadcrumbs = new views.Breadcrumbs({model: breadcrumbsModel}),
                view = breadcrumbs.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures').toContainElement('div.control-group');
            expect('#jasmine-fixtures div.control-group').toContainElement('a#test-id');
            expect('#jasmine-fixtures div.control-group a').toHaveAttr('href', 'test-link');
            expect('#jasmine-fixtures div.control-group a').toHaveText('test-title');
            expect('#jasmine-fixtures div.control-group').toContainElement('input[type="text"].nav-search-input');
            expect('#jasmine-fixtures div.control-group').toContainElement('i.nav-search-icon');
        });
    });

    describe("When 'search' field changed", function(){

        beforeEach(function(){
            var breadcrumbsData = {breadcrumbs: [{name: 'test-name'}],
                                  buttonID: 'test-id',
                                  buttonTitle: 'test-title',
                                  buttonLink: 'test-link'},
                breadcrumbsModel = new Backbone.Model(breadcrumbsData),
                keyup = $.Event('keyup', {keyCode: 75});
            this.view = new views.Breadcrumbs({model: breadcrumbsModel});
            this.view.render();
            spyOn(this.view, 'filterCollection');
            this.view.delegateEvents();
            this.view.$el.find('input[type=text]').trigger(keyup);
        });

        it("'keyup' event fires 'filterCollection' method", function(){
            expect(this.view.filterCollection).toHaveBeenCalled();
        });
    });
});