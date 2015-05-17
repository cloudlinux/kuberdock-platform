<div class="no-padding">
    <span class="status-line <%- status %>">Status: <%- status %></span>
    <% if ( status == "running" || status == "pending") { %>
        <span class="stop-btn">stop</span>
    <% } else { %>
        <span class="start-btn">start</span>
    <% } %>
    <span class="terminate-btn">delete</span>
    <% if (graphs) { %>
        <span class="list-btn">data</span>
    <% } else { %>
        <span class="stats-btn">stats</span>
    <% } %>
</div>
<div class="row placeholders">
    <div class="col-xs-10 col-xs-offset-2">
        <div class="col-xs-6 info">
            <div>Status: <%- status %></div>
            <div>Public IP: <%- podIP ? podIP : 'none' %></div>
            <div>Endpoint: <%- portalIP ? portalIP : 'none'%></div>
        </div>
        <div class="col-xs-6 servers">
            <div><b><%- name %></b></div>
            <div>Kube type: <%- kubeType %></div>
            <div>Restart policy: <%- restartPolicy %></div>
            <div>Kubes:  <%- kubes ? kubes : '0' %> <!-- ( <%- replicas ? replicas : '0' %> ) --></div>
            <div>Price: <%- price ? price : '0' %>$/hour</div>
            <!--
            <div class="edit">Edit pod</div>
            -->
        </div>
    </div>
</div>