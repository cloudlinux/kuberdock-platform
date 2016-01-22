<td class="col-md-2"><%- name %></td>
<td class="col-md-2"><%- size %>&nbsp;GB</td>
<td>
    <span class="<%- in_use ? 'busy' : 'free' %>"
    title="<%- in_use ? 'Used by pod "'+pod_name+'"' : 'Not used by any pod' %>">
        <%- in_use ? '"'+pod_name+'"' : 'free' %>
    </span>
    <span class="terminate-btn pull-right"></span>
    <!-- <span class="unmount pull-right"></span>
    <span class="onsearsh pull-right"></span> -->
</td>
