<div class="row">
  <h2 class="col-sm-12">Configuration</h2>
  <div class="col-sm-12 col-md-6">
    <div>Service address: <a href="http://<%- domain %>"><%- domain %></a></div>
    <div>Domain name: <a href="http://<%- domain %>"><%- domain %></a></div>
  </div>
</div>

<div class="row">
  <div class="col-sm-12">
    <ul class="nav nav-tabs">
        <% _.each(containers, function(container, i){ %>
            <li class="container-tab <%- current_tab_num == i ? 'active' : ''
             %>"
                data-name="<%- container.name%>"><%- container.image %></li>
        <% }) %>
    </ul>
  </div>
</div>

<div class="row">
  <div class="container-info col-sm-12">
  </div>
</div>