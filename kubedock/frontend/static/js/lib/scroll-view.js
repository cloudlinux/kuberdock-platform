;

"use strict"; // jshint ;_;

var ScrollView = Backbone.View.extend({
    columns: [],
    itemCount: -1,
    initialLoadingCallback: function (hasMore) { //initial data loading
        var self = this;

        //is the window fully loaded?
        if (hasMore && self.$el.outerHeight() < $(window).height()) {
            setTimeout(function () {
                self.addMoreItems(self.initialLoadingCallback);
            }, 100);
        } else {
        }
    },
    initialize: function (opts) {
        var self = this;
        this.options = opts.options;

        //initial column fetching
        this.fetchColumns();

        //on scroll page - load more data
        if (this.options.disableAutoscroll !== true) {

            var infinityScrollHandler = function (e) {
                //is position of scroll near by end?

                if (($(window).scrollTop() + $(window).height()) > ($(document).height() - $(window).height())) {
                    self.addMoreItems();
                }
            };

            //start of scroll event for touch devices
            if (document.addEventListener) {
                document.addEventListener("touchmove", infinityScrollHandler, false);
                document.addEventListener("scroll", infinityScrollHandler, false);
            }
        }

        //on resize the window - check the column count (responsive behavior)
        window.onresize = function (event) {
            self.fetchColumns();
        };

        self.lastWidth = $("body").innerWidth();

        $(window).resize(function () {

            if (self.lastWidth !== $("body").innerWidth()) {
                self.lastWidth = $("body").innerWidth();
                self.fetchColumns();
            }
        });

    },
    events: {
        "click .btn-more": function () {
            this.addMoreItems();  //it's a fallback, the link above the scroll area -  when auto-scroll detection is broken
        }
    },
    fetchColumns: function (onFetched) {
        var self = this;

        var $columns = $(this.options.columnsSelector + ":visible");

        if ($columns.length < 1) {
            jQuery.error("Columns are missing, please check the " + this.options.columnsSelector + ":visible selector");
        }

        if (self.columns.length !== $columns.length) { //there is a different column size suddenly (responsive design works)
            self.columns = [];

            $columns.each(function (i, column) {
                self.columns.push($(column));
            });

            self.resetItems();
        } else {
            if (onFetched) {
                onFetched();
            }
        }
    },
    resetItems: function () {
        this.thereAreNoMoreItems = false;
        this.itemCount = -1;
        this.model.reset();

        //clear columns
        _.each(this.columns, function ($item) {
            $item.html("");
        });

        this.addMoreItems(this.initialLoadingCallback);
    },
    getShortenColumn: function () { //determine the shorten column
        var self = this;

        var countHeight = function ($column) {
            var columnHeight;

            //call handler that allowes progammer to change the column height count (check the demos)
            if (typeof self.options.onCountColumnLenght !== 'undefined') {
                columnHeight = self.options.onCountColumnLenght($column);
            }

            if (typeof columnHeight === 'undefined') {
                columnHeight = $column.height();
            }

            return columnHeight;
        };

        var $shortenColumn = this.columns[0]; //get first column
        var shortenColumnHeight = countHeight($shortenColumn);

        for (var i = 1; i < this.columns.length; i++) { //compare with the rest of columns
            var $nextColumn = this.columns[i];
            var nextColumnHeight = countHeight($nextColumn);
            if (nextColumnHeight < shortenColumnHeight) { //new shorten column ?
                var $shortenColumn = $nextColumn;
                shortenColumnHeight = nextColumnHeight;
            }
        }

        return $shortenColumn;
    },
    gettingMore: false, //lock if it's rendering now 
    addMoreItems: function (onDone) {
        var self = this;

        if (this.gettingMore === true) {
            if (onDone) {
                onDone.call(self, true);
            }
            return;
        } else {
            this.gettingMore = true;
        }

        if (!this.model.hasMore()) {
            this.$el.find(".btn-more, .load-state").hide();
            this.$el.find(".no-more-state").show();
            this.gettingMore = false;
            if (onDone) {
                onDone.call(self, false);
            }
        } else {
            this.$el.find(".btn-more, .no-more-state").hide();
            this.$el.find(".load-state").show();

            this.model.getMore(function (items) {
                self.gettingMore = false;
                self.renderItems(items, onDone);
            });
        }
    },
    renderItems: function (itemsData, onDone) {
        var self = this;

        var templateSrc = $(document).find(this.options.itemTemplateSelector).html();

        if (typeof templateSrc === 'undefined') {
            jQuery.error("Missing pod prototype (check the itemTemplateSelector: " + this.options.itemTemplateSelector + ")");
        }

        var renderItem = function (i, itemsData) {

            self.itemCount = self.itemCount + 1;
            var itemData = itemsData[i];

            //evaluate additional CSS class names
            var classesStr = "";
            if (typeof self.options.itemClasses === 'string') { //if it's a string 
                classesStr = self.options.itemClasses;
            } else if (typeof self.options.itemClasses === 'function') { //a function
                classesStr = self.options.itemClasses(itemData);
            }

            itemData['url'] = 'http://' + self.options.requestData.url + '/' +
                (itemData.is_official?'_':'u') + '/' + itemData.name;
            var html = _.template(templateSrc)(itemData); //item html body

            //create an item DIV wrapper
            var $item = jQuery('<div/>', {
                "class": classesStr,
                "html": html
            });

            var shortenColumn = self.getShortenColumn();
            // try to call the onAddItem - return false means don't continue
            //
            // returns:
            // 
            // false = don't continue, skip this item node
            // object = here is a new item node, please use it but use also the origin one
            // -none- = continue and place the origin node as usual
            var callbackResult;
            if (typeof self.options.onAddItem !== 'undefined') {
                callbackResult = self.options.onAddItem(self.itemCount, shortenColumn, $item, itemData);
            }

            if (callbackResult === false) {
                //do nothing
            } else {
                if (typeof callbackResult === 'object') { //seems we have a new item to insert - an advertisement or something like that
                    callbackResult.appendTo(shortenColumn);
                    shortenColumn = self.getShortenColumn();
                }
                $item.appendTo(shortenColumn); //anyway the item shouldbe added
            }

            if (i < itemsData.length - 1) {
                setTimeout(function () { //it's necessary  
                    renderItem(i + 1, itemsData);
                }, 10);
            } else {
                self.gettingMore = false;

                if (self.model.hasMore()) {
                    self.$el.find(".btn-more").show();
                    self.$el.find(".load-state").hide();
                    if (onDone) {
                        onDone.call(self, true);
                    }
                } else {
                    self.$el.find(".load-state").hide();
                    self.$el.find(".no-more-state").show();
                    if (onDone) {
                        onDone.call(self, false);
                    }
                }
            }
        };

        renderItem(0, itemsData);
    }
});
