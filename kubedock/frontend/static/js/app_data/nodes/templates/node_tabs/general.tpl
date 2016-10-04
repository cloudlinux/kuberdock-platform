<% switch (status) { case 'running': %>
<% var ram = (resources.memory / (1024*1024*1024)).toFixed(2); %>
<div class="control-icons col-md-10 col-md-offset-1 clearfix">
    <div class="col-md-6 col-sm-12 info">
        <div>IP: <%- ip %></div>
    </div>
    <div class="col-md-6 col-sm-12 servers no-padding">
        <div>CPU: <%- resources.cpu %> cores</div>
        <div>RAM: <%- ram %> GB</div>
    </div>
</div>
<% break; case 'pending': %>
<div class="details">Node is in installation progress</div>
<div class="reason">
    <p>Node installation log</p>
    <% _.each(install_log.split('\n'), function(line){ %>
        <p><%- line %></p>
    <% }) %>
</div>
<% break; case 'troubles': %>
<div class="reason">
<% _.each(reason.split('\n'), function(line){ %>
    <p><%- line %></p>
<% }) %>
    <p>Node installation log</p>
    <% _.each(install_log.split('\n'), function(line){ %>
        <p><%- line %></p>
    <% }) %>
</div>
<% break; } %>