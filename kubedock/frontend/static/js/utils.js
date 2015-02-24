define(function () {

    // jQuery ajax setup
    Backbone.ajax = function() {
        // Invoke $.ajaxSetup in the context of Backbone.$
        Backbone.$.ajaxSetup.call(Backbone.$, {
            statusCode: {
                400: function(xhr){
                    if(xhr.responseJSON.status) alert(xhr.responseJSON.status);
                },
                401: function () {
                    // Redirect to the login page.
//                    Backbone.history.navigate("login", true);
                },
                403: function () {
                    // 403 -- Access denied
//                    Backbone.history.navigate("login", true);
                }
            }
        });
        return Backbone.$.ajax.apply(Backbone.$, arguments);
    };


    // here you can define any useful functions or objects to use their in the project

    this.unwrapper = function (response) {
        if (response.hasOwnProperty('data'))
            return response['data'];
        else if(response.hasOwnProperty('status') && typeof response.status === 'string'){
            alert(response.status);
        }
        return response;
    };

    this.BaseModel = Backbone.Model.extend({
        parse: this.unwrapper
    });


    return this;
});