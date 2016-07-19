<td id="<%- name %>"><b><%- image %></b></td>
<td class="inline-fix">
    <span class="kubes-less">-</span>
    <input class="kubes" type="number" min="1" max="<%- kubesLimit %>" value="<%- kubes %>"/>
    <span class="kubes-more">+</span>
</td>
<td><%- price %> / <%- period %></td>
<td class="actions text-right">
    <span class="edit-item" data-toggle="tooltip" data-placement="left" title="Edit <%- image %> container"></span>
    <% if (showDelete){ %>
        <span class="delete-item" data-toggle="tooltip" data-placement="left" title="Remove <%- image %> container"></span>
    <% } %>
</td>
