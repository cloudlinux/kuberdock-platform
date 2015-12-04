<div class="col-xs-12 no-padding">
    <div class="col-xs-10 no-padding">
        <div class="item-header-title"><%= name || 'nameless' %></div>
        <div class="item-body-info">
            <%= description || 'No description' %>
        </div>
        <% if (description && name) { %>
            <div class="more">
            <% if (source_url !== undefined) { %>
                <a href="<%- /^https?:\/\//.test(source_url) ? source_url : 'http://' + source_url %>" target="blank">Learn more...</a>
            <% } %>
            </div>
        <% } %>
    </div>
    <div class="col-xs-2 no-padding">
        <button class="like"><%= star_count %></button>
        <button class="add-item">Select</button>
    </div>
</div>