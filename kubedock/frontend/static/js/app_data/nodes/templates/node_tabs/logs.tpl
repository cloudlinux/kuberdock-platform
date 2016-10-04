<div id="logs-page">
    <div class="node-logs">
        <% _.each(logs, function(line){ %>
            <p><time><%- line['@timestamp'] %></time> <span class="ident"><%- line['ident'] %></span>: <%- line['message'] %></p>
        <% }) %>
        <% if (logsError) { %>
            <p><%- logsError %></p>
        <% } %>
    </div>
</div>