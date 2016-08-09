<% if (!isAWS){ %>
    <div class="ips-list-control">
        <span class="button visibility <%- showExcluded ? 'active' : '' %>">
            <span><%- showExcluded ? 'Hide' : 'Show' %> excluded IPs</span>
        </span>
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
