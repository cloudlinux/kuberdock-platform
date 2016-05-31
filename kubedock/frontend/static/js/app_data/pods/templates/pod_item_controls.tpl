<div class="message-wrapper <%- changed ? 'editPod' : ''%>">
    <% if (postDescription) { %>
        <div class="message">
            <h3>Congratulations!</h3>
            <p><%= postDescription %></p>
            <span class="close"></span>
        </div>
    <% } %>
    <% if (changed) { %>
        <div class="message">
            <h3>
              <span class="message-pod-canged-info-title-ico"></span>
              <span>You have some changes that haven't been applied yet!</span>
            </h3>
            <p>
                <% if (changesRequirePayment && fixedPrice){ %>
                You need to pay <%- changesRequirePayment %> to re-deploy
                pod with new containers and configuration.
                <div class="buttons text-center">
                    <button class="blue pay-and-apply" title="Pod will be restarted">Pay & apply changes</button>
                <% } else { %>
                You need to re-deploy pod with new containers and configuration.
                <div class="buttons text-center">
                    <button class="blue apply">Restart & apply changes</button>
                <% } %>
                    <button class="gray reset-changes">Reset changes</button>
                </div>
            </p>
        </div>
    <% } %>
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
        <li><a class="edit-btn" href="#pods/<%- id %>/edit"><span>Edit</span></a></li>
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
            <div>Pod IP: <%- (typeof(podIP) !== 'undefined') ? podIP : 'Internal IP is not assigned yet'%></div>
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
