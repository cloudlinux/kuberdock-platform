define(['settings_app/app'], function(data){

    describe("Settings TESTS", function(){
       var jasmine = true;

       it("jasmine is 'true'", function(){
           expect(jasmine).toBeTruthy();
       });

    });

    console.log('all tests loaded');
});
