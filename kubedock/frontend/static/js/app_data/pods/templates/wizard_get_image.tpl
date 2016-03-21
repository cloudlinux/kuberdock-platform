<div id="add-image" class="container">
    <div class="col-md-3 sidebar">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="active">Choose image</li>
            <li role="presentation">Set up image</li>
            <li role="presentation">Environment variables</li>
            <li role="presentation">Final setup</li>
        </ul>
    </div>
    <div id="details_content" class="col-md-9 col-sm-12 no-padding">
    <div id="tab-content">
        <label class="placeholder">Search images in DockerHub</label>
        <div class="clearfix">
            <div class="col-md-4 no-padding">
                <select class="selectpicker image-source">
                    <option>Docker Hub</option>
                    <option>Docker Hub/private repo</option>
                    <option>Other registries</option>
                </select>
            </div>
            <div class="col-md-7 no-padding">
                <input type="text" id="search-image-field" class="form-control" placeholder="Enter image name or part of image name">
            </div>
            <div class="col-md-1 no-padding search-image-inner">
                <button class="search-image" type="button"></button>
            </div>
            <div class="col-md-6 no-padding private">
                <input type="text" id="private-image-field" class="form-control" placeholder="/namespace/image">
            </div>
            <div class="col-md-2 no-padding private search-image-inner">
                <button class="select-image" type="button">SELECT</button>
            </div>
        </div>
        <div class="login-user row">
            <div class="col-md-6">
                <label>Username</label>
                <input type="text" id="username" placeholder="Enter registry name">
            </div>
            <div class="col-md-6">
                <label>Password</label>
                <input type="password" id="password" placeholder="Enter password">
            </div>
        </div>
        <div id="search-results-scroll">
            <div id="data-collection"></div>
            <div class="search-control">
                <% if (showPaginator){ %>
                    <div id="load-control" class="btn-more">Load more</div>
                <% } %>
            </div>
        </div>
        <div class="buttons pull-right">
            <button class="gray podsList">Cancel</button>
        </div>
    </div>
</div>