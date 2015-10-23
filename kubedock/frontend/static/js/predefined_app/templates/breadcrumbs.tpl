<div class="container breadcrumbs" id="breadcrumbs">
    <ul class="breadcrumb">
        <% if (showControls){ %>
            <li class="active"><%- breadcrumbs[0].name %></li>
        <% } else { %>
            <li class="cancel-app"><%- breadcrumbs[0].name %></li>
            <li class="active"><%- breadcrumbs[1].name %></li>
        <% } %>
    </ul>
    <% if (showControls){ %>
    <div class="control-group">
        <a id="<%- buttonID %>" href="<%- buttonLink %>"><%- buttonTitle %></a>
        <div class="nav-search" id="nav-search"></div>
        <input type="text" placeholder="Search" class="nav-search-input" id="nav-search-input" autocomplete="off">
    </div>
    <% } %>
</div>