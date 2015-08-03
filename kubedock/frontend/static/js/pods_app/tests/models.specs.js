define(['pods_app/models/pods', 'sinon'], function(data, sinon){
    
    describe("empty Pod model", function(){
        
        var podModel = new data.Pod();
        
        it("has attribute 'name'", function(){
            expect(podModel.has('name')).toBeTruthy();
        });
        
        it("has attribute 'containers' of type array", function(){
            expect(podModel.has('containers')).toBeTruthy();
            expect(podModel.get('containers').constructor).toBe(Array);
        });
        
        it("has attribute 'volumes' of type array", function(){
            expect(podModel.has('volumes')).toBeTruthy();
            expect(podModel.get('volumes').constructor).toBe(Array);
        });
        
        it("has attribute 'replicationController' of type boolean", function(){
            expect(podModel.has('replicationController')).toBeTruthy();
            expect(typeof podModel.get('replicationController')).toBe("boolean");
        });
        
        it("has attribute 'replicas' of type integer number", function(){
            expect(podModel.has('replicas')).toBeTruthy();
            var value = podModel.get('replicas');
            expect(value === +value && value === (value|0)).toBeTruthy();
            
        });
        
        it("has attribute 'restartPolicy' of type string", function(){
            expect(podModel.has('replicationController')).toBeTruthy();
            var value = podModel.get('restartPolicy');
            expect(typeof value === 'string' || value instanceof String).toBeTruthy();
        });
        
        podModel.destroy();
    });
    
    describe("Pod collection", function(){
        
        var podCollection = new data.PodCollection();
        
        it("has 'Pod' model", function(){
            expect(podCollection.model).toBe(data.Pod);
        });
        
    });
    
    describe("When Pod collection successfully fetches with status 'OK'", function(){
        
        beforeEach(function(){
            this.fs = sinon.fakeServer.create();
            this.pc = new data.PodCollection();
            this.fs.respondWith(JSON.stringify({status: 'OK', data: [
                {name: 'test1'}, {name: 'test2'}
            ]}));
            this.pc.fetch();
            this.fs.respond();
        });
        
        it("has proper number of models", function(){
            expect(this.pc.length).toBe(2);
        });
        
        afterEach(function(){
            this.fs.restore();
        });
    });
    
    describe("When Pod collection successfully fetches with error status", function(){
        
        beforeEach(function(){
            spyOn($, 'notify');
            this.fs = sinon.fakeServer.create();
            this.pc = new data.PodCollection();
            this.fs.respondWith(JSON.stringify({
                status: 'error', data: 'this is error message'
            }));
            this.pc.fetch();
            this.fs.respond();
        });
        
        it("modal error has been called with received message", function(){
            expect($.notify).toHaveBeenCalledWith('this is error message',
            {autoHideDelay:5000,globalPosition:'top center',className:'danger'});
        });
        
        afterEach(function(){
            this.fs.restore();
        });
    });
    
});