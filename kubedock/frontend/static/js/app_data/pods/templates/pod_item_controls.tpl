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
    <% if ( status == "running" || status == "pending") { %>
        <span class="icon hover stop-btn">Stop</span>
        <span class="icon hover restart-btn">Restart</span>
    <% } else { %>
        <% if ( status === "unpaid") { %>
            <span class="icon hover pay-and-start-btn">Pay & start</span>
        <% } else { %>
            <span class="icon hover start-btn">Start</span>
        <% } %>
    <% } %>
    <span class="icon hover terminate-btn">Delete</span>
    <% if (graphs) { %>
        <a class="icon hover list-btn" href="#pods/<%- id %>">Data</a>
    <% } else { %>
        <a class="icon hover stats-btn" href="#pods/<%- id %>/stats">Stats</a>
    <% } %>
    <% if (upgrade) { %>
        <a class="icon hover upgrade-btn back" href="#pods/<%- id %>">Upgrade</a>
    <% } else { %>
        <a class="icon hover upgrade-btn" href="#pods/<%- id %>/upgrade">Upgrade</a>
    <% } %>
</div>
<div class="row placeholders">
    <div class="control-icons col-md-10 col-md-offset-2 col-sm-12">
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
</div>
