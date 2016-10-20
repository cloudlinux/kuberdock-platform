<td><b><%- name %></b></td>
<td class="inline-fix">
    <% if(persistentDisk) { %>
        <span class="pd-less">-</span>
        <input class="pd" type="number" min="1" max=""
               value="<%- persistentDisk.pdSize %>"/>
        <span class="pd-more">+</span>
    <% } %>
</td>
<td>
    <% if(persistentDisk) { %>
        <span class="pstorage_price"><%= formatPrice( pkg.get('price_pstorage') * persistentDisk.pdSize) %></span>
    <% } %>
</td>
<td class="actions text-right">
    <% if (persistentDisk && persistentDisk.pdSize !== 1) { %>
            <span class="help" data-toggle="tooltip" data-placement="left"
                  title="<%= formatPrice( pkg.get('price_pstorage') ) %> per 1 GB"></span>
    <% } %>
</td>