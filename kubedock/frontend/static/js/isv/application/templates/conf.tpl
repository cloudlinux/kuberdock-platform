<div class="row">
    <h2 class="col-sm-12">Configuration</h2>
    <div class="hidden-xs col-sm-2 isv-block text-center layers"></div>
    <div class="col-xs-12 col-sm-10 isv-block">
        <p>Service address: <a href="http://<%- domain %>"><%- domain %></a></p>
        <p>Domain name: <a href="http://<%- domain %>"><%- domain %></a></p>
    </div>
</div>

<div class="row">
    <ul class="nav nav-tabs col-sm-12">
        <% _.each(containers, function(container, i){ %>
            <li class="container-tab <%- current_tab_num == i ? 'active' : ''
             %>"
                data-name="<%- container.name%>"><%- container.image %></li>
        <% }) %>
    </ul>
</div>

<div class="row">
    <div class="container-info col-sm-12">
    </div>
</div>