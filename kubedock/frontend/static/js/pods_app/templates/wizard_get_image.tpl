<div id="add-image" class="container">
    <div class="col-md-3 sidebar">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="active">Choose image</li>
            <li role="presentation">Set up image</li>
            <li role="presentation">Environment variables</li>
            <li role="presentation">Final setup</li>
        </ul>
    </div>
    <div id="details_content" class="col-sm-9 no-padding">
        <div id="tab-content">
            <label>Search from directories</label>
        <div>
    </div>
    <div class="clearfix">
        <!--
        <div class="col-md-3 no-padding">
            <select class="image-source">
                <option>Docker hub</option>
                <option>Private images</option>
                <option>Other registries</option>
            </select>
        </div>
        -->
        <div class="col-md-11 no-padding">
            <input type="text" id="search-image-field" class="form-control" placeholder="Enter image name or part of image name">
        </div>
        <div class="col-md-1 no-padding search-image-inner">
            <button class="search-image" type="button"></button>
        </div>
    </div>
    <div class="login-user row">
        <div class="col-md-6">
            <label>Enter username</label>
            <input type="text">
        </div>
        <div class="col-md-6">
            <label>Create password</label>
            <input type="text">
        </div>
    </div>
    <div id="search-results-scroll">
        <div id="data-collection"></div>
        <div class="search-control">
            <% if (showPaginator){ %>
            <div id="load-control" class="btn-more">Load more</div>
            <!--
            <div class="state no-more-state">There are no more items</div>
            <div class="state load-state"><span class="small-loader"></span> <span>Loading...</span></div>
            -->
            <% } %>
        </div>
    </div>
    <div class="buttons pull-right">
        <button class="gray podsList">Cancel</button>
    </div>
</div>