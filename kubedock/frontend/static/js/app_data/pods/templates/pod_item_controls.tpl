<div class="status-line">
    <span class="icon <%- prettyStatus %>">
        Status: <span class="text-capitalize"><%- prettyStatus %></span>
    </span>
    <% if (graphs) { %>
        <a class="list-btn" href="#pods/<%- id %>"><span>Data</span></a>
    <% } else { %>
        <a class="stats-btn" href="#pods/<%- id %>/stats"><span>Stats</span></a>
    <% } %>
    <!-- <% if (upgrade) { %>
        <a class="upgrade-btn back" href="#pods/<%- id %>"><span>Upgrade</span></a>
    <% } else { %>
        <a class="upgrade-btn" href="#pods/<%- id %>/upgrade"><span>Upgrade</span></a>
    <% } %> -->
    <% if (prettyStatus === 'running') { %><span class="resetSsh"><span>Reset SSH access</span></span><% } %>
    <div class="btn-group controls pull-right">
        <span type="button" class="dropdown-toggle" data-toggle="dropdown">
            <span class="ic_reorder">
                <span>Manage pod</span>
                <i class="caret"></i>
            </span>
        </span>
        <ul class="dropdown-menu" role="menu">
        <% if ( !currentUser.roleIs('LimitedUser') && !currentUser.usernameIs('kuberdock-internal')) {%>
            <li><a class="edit-btn" href="#pods/<%- id %>/edit"><span>Edit</span></a></li>
        <% } %>
        <% if (ableTo('switch-package')) { %>
            <li><a class="switch-package-btn" href="#pods/<%- id %>/switch-package">
                <span>Switch package</span>
            </a></li>
        <% } %>
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
        <% if (publicIP && publicIP !== 'true' && isPublic) { %>
            <div>Public IP: <a href="http://<%- publicIP %>/" rel="noopener" target="_blank"><%- publicIP %></a></div>
        <% } else if (publicIP && publicIP === 'true') {%>
            <div>Public IP: Public IP is not assigned yet</div>
        <% } else if (typeof domain != 'undefined' && domain) {%>
            <div class="relative">
                <span class="ellipsis-text">
                    Service address: <a href="http://<%- domain %>/" rel="noopener" target="_blank"><%- domain %></a>
                </span>
                <i data-toggle="tooltip" data-placement="left" title="Copy link to clipboard" class="copy-link"></i>
            </div>
        <% } else if (publicName) { %>
            <div class="relative">
                <span class="ellipsis-text">
                    Service address: <a href="http://<%- publicName %>/" rel="noopener" target="_blank"><%- publicName %></a>
                </span>
                <i data-toggle="tooltip" data-placement="left" title="Copy link to clipboard" class="copy-link"></i>
            </div>
        <% } %>
        <% if (hasPorts) { %>
            <div>Pod IP: <%- (typeof(podIP) !== 'undefined') ? podIP : 'Internal IP is not assigned yet'%></div>
        <% } %>
        <div>Restart policy: <%- restartPolicy %></div>
        <div>Kube Type: <%- kubeType.get('name') %></div>
        <div>Number of Kubes:  <%- kubes %> <!-- ( <%- replicas ? replicas : '0' %> ) --></div>
        <div>Price: <%- totalPrice %> / <%- period %></div>
    </div>
    <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 servers">
        <div>CPU: <%- limits.cpu %></div>
        <div>RAM: <%- limits.ram %></div>
        <div>HDD: <%- limits.hdd %></div>
    </div>
</div>
