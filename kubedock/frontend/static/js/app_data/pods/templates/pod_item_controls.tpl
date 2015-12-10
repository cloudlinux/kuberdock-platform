<div class="message-wrapper">
    <div class="message">
        <h3>Congratulations!</h3>
        <p>
            <% if (postDescription) { %>
                <%= postDescription %>
            <% } else {%>
                We just want to inform you that your application "<%- podName %>" now deploying and will be started in a few minutes. <br>
                The application will be available via
                that you have on top of the page. You can find app credential on application page in tab "General". You need to wait until application will obtain status "running" that will mean that you application is ready to use. You can find more information about how to use KuberDock in our documentation.
            <% } %>
        </p>
        <span class="close"></span>
    </div>
</div>
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
            <% if (hasPorts) { %>
                <div>Pod IP: <%- (typeof(podIP) !== 'undefined') ? podIP : 'Internal ip is not assigned yet'%></div>
            <% } %>
            <div>Restart policy: <%- restartPolicy %></div>
            <div>Kube type: <%- kubeType.name %></div>
            <div>Kubes:  <%- kubes %> <!-- ( <%- replicas ? replicas : '0' %> ) --></div>
            <div>Price: <%- totalPrice %> / <%- package.period %></div>
            <!--
            <div class="edit">Edit pod</div>
            -->
        </div>
        <div class="col-xs-6 servers">
            <div>CPU: <%- limits.cpu %></div>
            <div>RAM: <%- limits.ram %></div>
            <div>HDD: <%- limits.hdd %></div>
        </div>
    </div>
</div>
