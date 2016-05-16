<div class="container breadcrumbs" id="breadcrumbs">
    <ul class="breadcrumb">
        <% _.each(points, function(point, i){ %>
            <li class="bpoint-<%- point %> <%= i + 1 === points.length ? 'active' : '' %>"></li>
        <% }) %>
    </ul>
    <div class="control-group"></div>
</div>
