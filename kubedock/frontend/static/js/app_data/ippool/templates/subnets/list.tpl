 <% if (totalFreeIps) {%>
    <div id="aboveTableSection">
        <span>Total of available IP’s: <%- totalFreeIps %></span>
    </div>
<% } %>
<table class="table ip_pool_table">
    <thead>
        <tr>
            <th>Subnet</th>
            <% if (!isFloating) { %>
                <th>Node hostname</th>
            <% } %>
            <th>Available IP’s</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody></tbody>
</table>
