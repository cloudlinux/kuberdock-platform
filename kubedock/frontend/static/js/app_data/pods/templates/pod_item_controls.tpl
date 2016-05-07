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
<div class="status-line">
    <span class="icon <%- status %>">Status: <%- status %></span>
    <% if (graphs) { %>
        <a class="list-btn" href="#pods/<%- id %>"><span>Data</span></a>
    <% } else { %>
        <a class="stats-btn" href="#pods/<%- id %>/stats"><span>Stats</span></a>
    <% } %>
    <% if (upgrade) { %>
        <a class="upgrade-btn back" href="#pods/<%- id %>"><span>Upgrade</span></a>
    <% } else { %>
        <a class="upgrade-btn" href="#pods/<%- id %>/upgrade"><span>Upgrade</span></a>
    <% } %>
    <div class="btn-group controls pull-right">
        <span type="button" class="dropdown-toggle" data-toggle="dropdown">
            <span class="ic_reorder">
                <span>Manage pod</span>
                <i class="caret"></i>
            </span>
        </span>
        <ul class="dropdown-menu" role="menu">
        <% if (ableTo('redeploy')) { %><li><span class="restart-btn"><span>Restart</span></span></li><% } %>
        <% if (ableTo('pay-and-start')) { %><li><span class="pay-and-start-btn"><span>Pay & start</span></span></li><% } %>
        <% if (ableTo('start')) { %><li><span class="start-btn"><span>Start</span></span></li><% } %>
        <% if (ableTo('stop')) { %><li><span class="stop-btn"><span>Stop</span></span></li><% } %>
        <% if (ableTo('delete')) { %><li><span class="terminate-btn"><span>Delete</span></span></li><% } %>
        </ul>
    </div>
</div>
<div class="control-icons col-md-10 col-md-offset-2 col-sm-12 clearfix">
    <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 info">
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
        <div>Kube Type: <%- kubeType.get('name') %></div>
        <div>Number of Kubes:  <%- kubes %> <!-- ( <%- replicas ? replicas : '0' %> ) --></div>
        <div>Price: <%- totalPrice %> / <%- period %></div>
        <!--
        <div class="edit">Edit pod</div>
        -->
    </div>
    <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 servers">
        <div>CPU: <%- limits.cpu %></div>
        <div>RAM: <%- limits.ram %></div>
        <div>HDD: <%- limits.hdd %></div>
    </div>
</div>
