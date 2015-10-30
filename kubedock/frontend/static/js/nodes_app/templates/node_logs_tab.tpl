<div id="logs-page" class="col-sm-12 no-padding">
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
    </div>
</div>