<td><span class="name">
    <% if (before && !after){ %>
        <span class="deleted" data-toggle="tooltip" data-placement="right" title="Deleted"></span>
    <% } else if (!before && after) { %>
        <span class="added" data-toggle="tooltip" data-placement="right" title="Added"></span>
    <% } else if (before.value !== after.value) { %>
        <span class="changed" data-toggle="tooltip" data-placement="right" title="Changed"></span>
    <% } %>
    <%- id %>
</span></td>
<td><span class="value">
    <% if (before && !after){ %>
        <%- before.value %>
    <% } else if (!before && after) { %>
        <%- after.value %>
    <% } else if (before.value !== after.value) { %>
        <span class="diff"><%- before.value %></span>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
         title="This variable will be modified after you apply changes."></span>
        <span><%- after.value %></span>
    <% } else { %>
        <%- before.value %>
    <% } %>
</span></td>
