<% if (!isAWS){ %>
    <div class="ips-list-control">
        <span class="button visibility <%- showExcludedIps ? '' : 'active' %>"><span><%- showExcludedIps ? 'Show' : 'Hide' %> excluded IP’s</span></span>
    </div>
<% } %>
<table class="table ip_table">
    <thead>
        <tr>
            <% if (isAWS){ %>
            <th>DNS names in use</th>
            <th>Username</th>
            <th>Pod</th>
            <% } else { %>
            <th>IP</th>
            <th>Status</th>
            <th>Actions</th>
            <% } %>
        </tr>
    </thead>
    <tbody></tbody>
</table>