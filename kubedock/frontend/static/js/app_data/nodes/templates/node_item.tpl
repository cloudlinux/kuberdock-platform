<td>
    <button class="detailedNode" title="<%- hostname %>">
        <%- hostname ? hostname : ip ? ip : 'Not specified' %>
    </button>
</td>
<td><%- ip %></td>
<td><%- kubeType %></td>
<td>
    <span class="<%- status %>"><%- status %></span>
</td>
<td>
    <span class="deleteNode" title="Remove <%- hostname %> node">&nbsp;</span>
</td>