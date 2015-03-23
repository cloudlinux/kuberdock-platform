;

"use strict"; // jshint ;_;

var ScrollModel = Backbone.Model.extend({
    initialize: function(opts) {
        this.options = opts.options;
    },
    defaults: {
            },
    hasMore: function() {
        return this.get("noMoreItems") !== 1;
    },
    reset: function() {
        this.page = -1;
    },
    requestPending: false,
    page: -1,
    getMore: function(callback) {

        if (typeof this.options.data !== "undefined") { //local data
            var chunkSize = 10;
            
            var from = ++this.page * chunkSize;
            
            var chunk = []; //this.options.data
            
            for (var i = from; i < this.options.data.length; i++) {
            
                chunk.push(this.options.data[i]);
                
                if (i === this.options.data.length -1) {
                    this.set("noMoreItems", 1);
                    break;
                } else if (i === (from + chunkSize) - 1) {
                    break;
                }
            }
            
            this.dataReceived(chunk, callback);
            
        } else if (typeof this.options.dataUrl !== "undefined") { //remote data
            if (this.requestPending) {
                return;
            } else {
                this.requestPending = true;
            }

            var self = this;
            $.ajax({
                url: this.options.dataUrl + "?page=" + (++this.page) 
            }).done(function(data) {
                var d = data.data;
                if(parseInt(data.page) == parseInt(data.num_pages)){
                    self.set("noMoreItems", 1);
                }
                self.dataReceived(d, callback);
            }).fail(function(e) {
                $.error('ajax error', e);
            }).complete(function() {
                self.requestPending = false;
            });

        } else { //no tatasource - its an error
            $.error("No tadasource, please set 'data' or 'dataUrl'");
        }

//        if (typeof this.options.onRequestData !== 'undefined') {
//            var tempData = this.options.onRequestData(link);
//            if (typeof tempData === 'object') {
//                this.dataReceived(this.options.initialData, callback);
//                return;
//            }
//        }

    },
    dataReceived: function(data, callback) {
//        var self = this;

//        if (typeof self.options.onReceiveData !== 'undefined') {
//            var tempData = self.options.onReceiveData(data);
//            if (typeof tempData === 'object') {
//                data = tempData;
//            }
//        }

        callback(data);
    }
});
