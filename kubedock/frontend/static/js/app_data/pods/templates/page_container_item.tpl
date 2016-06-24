<!-- <td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td> -->
<td>
    <a href="#pods/<%- podID %>/container/<%- name %>" class="container-page-btn">
        <%- imagename %>
    </a>
    <% if (imagetag) { %>
    <span title="image tag" class="image-tag"><%- imagetag %></span>
    <% } %>
</td>
<td><span class="<%- state %>"><%- state %></span></td>
<td>
    <% if (state == 'running' )  { %>
        <span class="copy-ssh-link" data-toggle="tooltip" data-placement="top" title="Copy SSH link to clipboard"></span>
        <span class="copy-ssh-password" data-toggle="tooltip" data-placement="top" title="Copy SSH password to clipboard"></span>
    <% } %>
</td>
<td><span><%- kubes ? kubes : 'unknown' %></span></td>
<td><span><%- startedAt ? startedAt : '' %></span></td>
<td class="actions">
    <% if (state == 'running' )  { %>
        <% if (!updateIsAvailable) { %>
            <span class="check-for-update" data-toggle="tooltip" data-placement="top" title="Check <%- image %> for updates">Check for updates</span>
        <% } else { %>
            <span class="container-update" data-toggle="tooltip" data-placement="top" title="Update <%- image %> container">Update</span>
        <% } %>
    <% }%>
</td>
