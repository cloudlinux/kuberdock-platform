define(['pods_app/views/pods_list', 'pods_app/models/pods', 'jasmine-jquery'], function(views, data){
    
    describe("When Pod list is shown", function(){
        
        var listLayout = new views.PodListLayout();
        kubeTypes = [{id: 0, name: 'Test kube'}];
        listLayout.render();
        
        it('list layout created', function(){
            expect(listLayout.el.innerHTML)
                .toContain('<div id="layout-list"></div>');
            expect(listLayout.el.innerHTML)
                .toContain('<div id="layout-footer"></div>');
        });
        
        it('list table displayed and empty when no pods', function(){
            var collection = new data.PodCollection(),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            expect(view.el.innerHTML).toContain('table id="podlist-table"');
            expect(view.el.innerHTML).toContain('<tbody></tbody>');
        });
        
        it("list table has breadcrumbs and only word 'Pods' inside", function(){
            var collection = new data.PodCollection(),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures').toContainElement('div#breadcrumbs');
            expect('#jasmine-fixtures ul.breadcrumb > li').toHaveLength(1);
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(0)).toContainText('Pods');
            expect($('#jasmine-fixtures ul.breadcrumb > li').get(0)).toHaveClass('active');
        });
        
        it("list table has 'add new container' button and search field", function(){
            var collection = new data.PodCollection(),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures').toContainElement('div.control-group');
            expect('#jasmine-fixtures div.control-group').toContainElement('a#add_pod');
            expect('#jasmine-fixtures div.control-group a#add_pod').toHaveAttr('href', '/#newpod');
            expect('#jasmine-fixtures div.control-group').toContainElement('input[type="text"].nav-search-input');
            expect('#jasmine-fixtures div.control-group').toContainElement('i.nav-search-icon');
        });
        
        it('if collection has 2 models list has 2 entries', function(){
            var model1 = new data.Pod({id: 1, name: 'test1', kube_type: 0}),
                model2 = new data.Pod({id: 2, name: 'test2', kube_type: 0}),
                collection = new data.PodCollection([model1, model2]),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures tbody > tr').toHaveLength(2);
        });
        
        listLayout.remove();
        
    });
});