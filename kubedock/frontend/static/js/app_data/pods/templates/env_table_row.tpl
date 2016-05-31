<td><span class="name">
    <% if (before && !after){ %>
        (deleted)
    <% } else if (!before && after) { %>
        (added)
    <% } else if (before.value !== after.value) { %>
        (changed)
    <% } %>
    <%- id %>
</span></td>
<td><span class="value">
    <% if (before && !after){ %>
        <%- before.value %>
    <% } else if (!before && after) { %>
        <%- after.value %>
    <% } else if (before.value !== after.value) { %>
        <%- before.value %>
        (tooltip: <%- after.value %>)
    <% } else { %>
        <%- before.value %>
    <% } %>
</span></td>
