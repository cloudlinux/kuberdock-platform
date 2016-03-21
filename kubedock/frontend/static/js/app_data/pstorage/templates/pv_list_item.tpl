<td><%- name %></td>
<td><%- size %>&nbsp;GB</td>
<td>
    <span class="<%- in_use ? 'busy' : 'free' %>"
    title="<%- in_use ? 'Used by pod "'+pod_name+'"' : 'Not used by any pod' %>">
        <%- in_use ? '"'+pod_name+'"' : 'free' %>
    </span>
</td>
<td>
    <% if (!forbidDeletion){ %>
        <span class="terminate-btn"></span>
    <% } %>
    <!-- <span class="unmount pull-right"></span>
    <span class="onsearsh pull-right"></span> -->
</td>
