<div class="row">
    <h2 class="col-sm-12">Configuration</h2>
    <div class="hidden-xs col-sm-2 isv-block text-center layers"></div>
    <div class="col-xs-12 col-sm-10 isv-block">
        <p>Service address: <a href="http://<%- domain %>"><%- domain %></a></p>
        <p>Domain name:
            <% if(custom_domain) { %>
                <a href="http://<%- custom_domain %>"><%- custom_domain %></a>
            <% } else { %>
                not set
            <% } %>
            <a href="#app/conf/domain"
               class="edit-domain"
               data-toggle="tooltip"
               data-placement="top"
               data-original-title="Edit domain name"></a>
        </p>
    </div>
</div>

<div class="row">
    <ul class="nav nav-tabs col-sm-12">
        <% _.each(containers, function(container){ %>
            <li class="container-tab <%- activeSshTab === container.name ? 'active' : ''
             %>"
                data-name="<%- container.name%>"><%- container.image %></li>
        <% }) %>
    </ul>
</div>

<div class="row">
    <div class="container-info col-sm-12">
    </div>
</div>
