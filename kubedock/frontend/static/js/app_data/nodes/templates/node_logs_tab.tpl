<div id="logs-page">
    <div class="status-line"><span class="icon <%- status %>">Status: <%- status %></span></div>
    <div class="node-logs">
        <% _.each(logs, function(line){ %>
            <p><%- line['@timestamp'] %> <%- line['ident'] %>: <%- line['message'] %></p>
        <% }) %>
        <% if (logsError) { %>
            <p><%- logsError %></p>
        <% } %>
    </div>
</div>