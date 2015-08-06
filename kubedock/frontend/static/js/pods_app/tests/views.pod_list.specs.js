define(['pods_app/views/pods_list',
        'pods_app/models/pods',
        'jasmine-jquery'], function(views, data){

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

        it('list table displayed and header has six columns', function(){
            var collection = new data.PodCollection(),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            setFixtures(view.el.innerHTML);
            //expect(').toContain('table id="podlist-table"');
            expect('#jasmine-fixtures thead > tr > th').toHaveLength(6);
        });

        it('list table displayed and empty when no pods', function(){
            var collection = new data.PodCollection(),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures tbody > tr').toHaveLength(0);
        });

        it("'Delete' button is expected to be hidden if no pods entries selected", function(){
            var collection = new data.PodCollection(),
                listView = new views.PodCollection({collection: collection}),
                view = listView.render();
            setFixtures(view.el.innerHTML);
            expect('#jasmine-fixtures div.podsControl').toBeHidden();
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

        //it('if collection has 2 models list has 2 entries', function(){
        //    var model1 = new data.Pod({id: 1, name: 'first', kube_type: 0}),
        //        model2 = new data.Pod({id: 2, name: 'second', kube_type: 0}),
        //        collection = new data.PodCollection([model1, model2]),
        //        listView = new views.PodCollection({collection: collection});
        //    listView.ui.node_search[0].value = 'fir';
        //    listView.filterCollection();
        //    console.log(listView.collection.length);
        //    //var view = listView.render();
        //    //expect('#jasmine-fixtures tbody > tr').toHaveLength(2);
        //});

        listLayout.remove();

    });
});