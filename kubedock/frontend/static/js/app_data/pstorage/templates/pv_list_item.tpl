<td class="col-md-4"><%- name %></td>
<td class="col-md-3"><%- size %>&nbsp;GB</td>
<td class="col-md-3">



        <% if (in_use && available) { %>
            <span class="busy">Used by pod "<%= pod_name %>"</span>
        <% } else if (!available) { %>
            <span class="troubles" data-toggle="tooltip" data-placement="top"
            title="Contact your support">Troubles</span>

        <% } else { %>
            <span class="free">Free to use</span>
        <% } %>
</td>
<td class="col-md-2">
    <% if (forbidDeletionMsg){ %>
        <span class="terminate-btn disabled" data-toggle="tooltip" data-placement="top"
            title="<%- forbidDeletionMsg %>"></span>
    <% } else { %>
        <span class="terminate-btn" data-toggle="tooltip" data-placement="top" title='Delete "<%- name %>" volume'></span>
    <% } %>
    <!-- <span class="unmount"></span>
    <span class="onsearsh"></span> -->
</td>
