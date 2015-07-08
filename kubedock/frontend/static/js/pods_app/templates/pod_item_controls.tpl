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
            <div>Status: <%- status %></div>
            <% if (publicIP) { %>
                <div>Public IP: <%- publicIP %></div>
            <% } %>
            <% if (publicName) { %>
                <div>Public name: <%- publicName %></div>
            <% } %>
            <div>Pod IP: <%- (typeof(podIP) != 'undefined') ? podIP : 'Internal ip is not assigned yet'%></div>
        </div>
        <div class="col-xs-6 servers">
            <div><b><%- name %></b></div>
            <div>Kube type: <%- (typeof(kubeType) != 'undefined') ? kubeType : 'Standard' %></div>
            <div>Restart policy: <%- restartPolicy %></div>
            <div>Kubes:  <%- (typeof(kubes) != 'undefined') ? kubes : 0 %> <!-- ( <%- replicas ? replicas : '0' %> ) --></div>
            <div>Price: <%- (typeof(price) != 'undefined') ? price : 0 %>$/hour</div>
            <!--
            <div class="edit">Edit pod</div>
            -->
        </div>
    </div>
</div>