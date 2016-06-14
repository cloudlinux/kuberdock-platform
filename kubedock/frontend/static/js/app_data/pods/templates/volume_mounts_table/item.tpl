<td>
    <% if (before && !after){ %>
        <span class="deleted" data-toggle="tooltip" data-placement="right" title="Deleted"></span>
    <% } else if (!before && after) { %>
        <span class="added" data-toggle="tooltip" data-placement="right" title="Added"></span>
    <% } else if (!_.isEqual(before, after) || !_.isEqual(pdBefore, pdAfter)) { %>
        <span class="changed" data-toggle="tooltip" data-placement="right" title="Changed"></span>
    <% } %>
    <%- (before || after).mountPath %>
</td>
<td>
    <% if (before && after && !pdBefore !== !pdAfter){ %>
        <%- pdBefore ? 'yes' : 'no' %>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
        title="This volume will be modified after you apply changes."></span>
        <%- pdAfter ? 'yes' : 'no' %>
    <% } else { %>
        <%- (pdBefore || pdAfter) ? 'yes' : 'no' %>
    <% } %>
</td>
<td>
    <% if (pdBefore && pdAfter && pdBefore.pdName !== pdAfter.pdName){ %>
        <%- pdBefore.pdName %>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
        title="This volume will be modified after you apply changes."></span>
        <%- pdAfter.pdName %>
    <% } else { %>
        <%- (pdBefore || pdAfter) ? (pdBefore || pdAfter).pdName : '' %>
    <% } %>
</td>
<td>
    <% if (pdBefore && pdAfter && pdBefore.pdSize !== pdAfter.pdSize){ %>
        <%- pdBefore.pdSize %>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
        title="This volume will be modified after you apply changes."></span>
        <%- pdAfter.pdSize %>
    <% } else { %>
        <%- (pdBefore || pdAfter) ? (pdBefore || pdAfter).pdSize : '' %>
    <% } %>
</td>
