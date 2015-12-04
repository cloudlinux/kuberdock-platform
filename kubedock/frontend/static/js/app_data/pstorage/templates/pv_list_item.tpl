<td class="col-md-2"><%- name %></td>
<td class="col-md-2"><%- size %>&nbsp;GB</td>
<td>
    <span class="<%- in_use ? 'stopped' : 'running' %>"><%- pod %></span>
    <span class="terminate-btn pull-right"></span>
    <!-- <span class="unmount pull-right"></span>
    <span class="onsearsh pull-right"></span> -->
</td>
