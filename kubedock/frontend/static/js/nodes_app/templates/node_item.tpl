<td>
    <button id="detailedNode" title="<%- hostname %>">
        <%- hostname ? hostname : ip ? ip : 'Not specified' %>
    </button>
</td>
<td><%- ip %></td>
<td><%- kubeType %></td>
<td>
    <span class="<%- status %>"><%- status %></span>
    <span id="deleteNode" class="pull-right" title="Remove <%- hostname %> node">&nbsp;</span>
</td>
