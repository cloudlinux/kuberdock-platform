define(function () {

    // jQuery ajax setup
    var that = this;
    Backbone.ajax = function() {
        // Invoke $.ajaxSetup in the context of Backbone.$
        Backbone.$.ajaxSetup.call(Backbone.$, {
            statusCode: {
                400: function(xhr){
                    if(xhr.responseJSON.status) alert(xhr.responseJSON.status);
                },
                401: function (xhr) {
                    // Redirect to the login page.
//                    Backbone.history.navigate("login", true);
                },
                403: function (xhr) {
                    // 403 -- Access denied
//                    Backbone.history.navigate("login", true);
                },
                404: function(xhr){
                    $('body').html(
                        '404 Page not found'
                    );
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