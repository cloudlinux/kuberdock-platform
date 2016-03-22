<div id="logs-page">
    <div class="status-line"><span class="icon <%- status %>">Status: <%- status %></span></div>
    <!--
    <div class="page-top-menu">
        <span>Choose log:</span>
        <span class="active">Log 1</span>
        <span>Log 2</span>
        <span>Log 3</span>
        <span>Log 3</span>
    </div>
    -->
    <div class="node-logs">
        <% _.each(logs, function(line){ %>
            <p><%- line['@timestamp'] %> <%- line['ident'] %>: <%- line['message'] %></p>
        <% }) %>
        <% if (logsError) { %>
            <p><%- logsError %></p>
        <% } %>
    </div>
</div>