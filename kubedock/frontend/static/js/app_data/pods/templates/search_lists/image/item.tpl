<div class="col-xs-12 no-padding clearfix">
    <div class="col-md-2 col-sm-2 hidden-xs container-image empty"></div>
    <div class="col-md-8 col-sm-8 col-xs-8">
        <div class="item-header-title"><%= name || 'nameless' %></div>
        <div class="item-body-info">
            <%= description || 'No description' %>
        </div>
        <% if (description && name) { %>
            <div class="more">
            <% if (source_url !== undefined) { %>
                <a href="<%- /^https?:\/\//.test(source_url) ? source_url : 'http://' + source_url %>" target="blank"><span>Learn more...</span></a>
            <% } %>
            </div>
        <% } %>
    </div>
    <div class="col-md-2 col-sm-2 col-xs-4">
        <button class="like"><span><%= star_count %></span></button>
        <button class="add-item">Select</button>
    </div>
</div>