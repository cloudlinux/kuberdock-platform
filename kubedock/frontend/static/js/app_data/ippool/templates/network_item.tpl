<td class="network"><%- network %></td>
<td class="actions">
    <% if (forbidDeletionMsg){ %>
        <span id="deleteNetwork" class="disabled" data-toggle="tooltip" data-placement="right"
            title="<%- forbidDeletionMsg %>"></span>
    <% } else { %>
        <span id="deleteNetwork"  title="Remove <%= network %> subnet"></span>
    <% } %>
</td>
