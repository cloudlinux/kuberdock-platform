<div class="no-padding">
    <span class="status-line <%- status %>">Status: <%- status %></span>
    <% if ( status == "running" || status == "pending") { %>
        <span class="stop-btn">stop</span>
    <% } else { %>
        <span class="start-btn">start</span>
    <% } %>
    <span class="terminate-btn">delete</span>
    <% if (graphs) { %>
        <span class="list-btn pull-right">data</span>
    <% } else { %>
        <span class="stats-btn pull-right">stats</span>
    <% } %>
</div>
<div class="row placeholders">
    <div class="col-xs-10 col-xs-offset-2">
        <div class="col-xs-6 info">
            <% if (publicIP) { %>
                <div>Public IP: <%- publicIP %></div>
            <% } %>
            <% if (publicName) { %>
                <div>Public name: <%- publicName %></div>
            <% } %>
            <div>Pod IP: <%- (typeof(podIP) != 'undefined') ? podIP : 'Internal ip is not assigned yet'%></div>
            <div>Restart policy: <%- restartPolicy %></div>
            <div>Kube type: <%- kubeType.name %></div>
            <div>Kubes:  <%- kubes %> <!-- ( <%- replicas ? replicas : '0' %> ) --></div>
            <div>Price: <%- kubesPrice %> / <%- package.period %></div>
            <!--
            <div class="edit">Edit pod</div>
            -->
        </div>
        <div class="col-xs-6 servers">
            <div>CPU: <%- kubeType.cpu * kubes %> <%- kubeType.cpu_units %></div>
            <div>RAM: <%- kubeType.memory * kubes %> <%- kubeType.memory_units %></div>
            <div>HDD: <%- kubeType.disk_space * kubes %> <%- kubeType.disk_space_units %></div>
        </div>
    </div>
</div>