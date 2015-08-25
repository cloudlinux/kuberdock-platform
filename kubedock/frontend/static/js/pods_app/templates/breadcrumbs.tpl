<div class="container breadcrumbs" id="breadcrumbs">
    <ul class="breadcrumb">
    <% _.each(breadcrumbs, function(b){  %>
        <% if (b.hasOwnProperty('href')){ %>
        <li>
            <a href="<%- b.href %>"><%- b.name %></a>
        </li>
        <% } else { %>
            <li class="active"><%- b.name %></li>
        <% } %>
    <% }) %>
    </ul>
    <div class="control-group">
        <a id="<%- buttonID %>" href="<%- buttonLink %>"><%- buttonTitle %></a>
        <div class="nav-search" id="nav-search"></div>
        <input type="text" placeholder="Search" class="nav-search-input" id="nav-search-input" autocomplete="off">
    </div>
</div>