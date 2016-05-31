<!-- <td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td> -->
<td>
    <a href="#pods/<%- pod.id %>/container/<%- id %><%- !before && after ? '/general' : '' %>"
        class="container-page-btn">
        <%- imagename %>
    </a>
    <% if (imagetag) { %>
    <span title="image tag" class="image-tag"><%- imagetag %></span>
    <% } %>
</td>
<td>
    <% if (before) { %>
        <span class="<%- before.state %>"><%- before.state %></span>
    <% } %>
    <% if (before && !after) { %>
        <span class="diff-deleted">
            <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
             title="This container will be deleted after you apply changes."></span>
            <span class="diff">deleted</span>
        </span>
    <% } else if (!before && after) { %>
        <span class="diff-added">
            <span class="diff-added-icon" data-toggle="tooltip" data-placement="top"
                title="This container will be added after you apply changes."></span>
            <span class="diff">new added</span>
        </span>
    <% } else if (changed) { %>
        <span class="diff-changed">
            <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
             title="This container will be modified after you apply changes."></span>
            <span class="diff">modified</span>
        </span>
        <% console.log(before, after); %>
    <% } %>
</td>
<td><span>
    <% if (before && after && before.kubes !== after.kubes) { %>
      <span class="diff-changed">
          <span><%- before.kubes %></span>
          <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
           title="The number of kubes will be changed after you apply changes.">
          </span>
          <span class="diff"><%- after.kubes %></span>
        </span>
    <% } else { %>
        <%- (before || after).kubes %>
    <% } %>
</span></td>
<td><span><%- startedAt %></span></td>
<td class="actions">
    <% if (before && before.state == 'running')  { %>
        <% if (!updateIsAvailable) { %>
            <span class="check-for-update" data-toggle="tooltip" data-placement="top" title="Check <%- before.image %> for updates">Check for updates</span>
        <% } else { %>
            <span class="container-update" data-toggle="tooltip" data-placement="top" title="Update <%- before.image %> container">Update</span>
        <% } %>
    <% }%>
</td>
