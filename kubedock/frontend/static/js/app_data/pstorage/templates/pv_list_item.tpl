<td class="col-md-4"><%- name %></td>
<td class="col-md-3"><%- size %>&nbsp;GB</td>
<td class="col-md-3">
    <span class="<%- in_use ? 'busy' : 'free' %>" data-toggle="tooltip" data-placement="top"
    title="<%- in_use ? 'Used by pod "'+pod_name+'"' : 'Not used by any pod' %>">
        <%- in_use ? '"'+pod_name+'"' : 'free' %>
    </span>
</td>
<td class="col-md-2">
    <% if (forbidDeletionMsg){ %>
        <span class="terminate-btn disabled" data-toggle="tooltip" data-placement="top"
            title="<%- forbidDeletionMsg %>"></span>
    <% } else { %>
        <span class="terminate-btn"></span>
    <% } %>
    <!-- <span class="unmount pull-right"></span>
    <span class="onsearsh pull-right"></span> -->
</td>
