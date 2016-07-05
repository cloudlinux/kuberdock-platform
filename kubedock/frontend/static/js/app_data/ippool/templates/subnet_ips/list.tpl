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