<td>
    <a href="#ippool/<%- encodeURIComponent(id) %>"><%- network %></a>
</td>
<% if (!isFloating) { %>
    <td><%- node ? node : 'none'%></td>
<% } %>
<td><%- free_host_count || '0'%></td>
<td class="actions">
    <% if (forbidDeletionMsg){ %>
        <span id="deleteNetwork" class="disabled" data-toggle="tooltip" data-placement="top"
            title="<%- forbidDeletionMsg %>"></span>
    <% } else { %>
        <span id="deleteNetwork" data-toggle="tooltip" data-placement="top"
            title="Remove <%= network %> subnet"></span>
    <% } %>
</td>