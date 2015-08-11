<!-- table data row -->
<td>
    <label class="custom">
        <% if (checked){ %>
        <input type="checkbox" class="checkbox" checked>
        <% } else { %>
        <input type="checkbox" class="checkbox">
        <% } %>
        <span></span>
    </label>
</td>
<td class="index"><%- index %></td>
<td>
    <span class="poditem-page-btn" title="Edit <%- name %> pod" ><%- name %></span>
    <!--<a href="/#pods/<%- id %>" title="Edit <%- name %> pod" class="editPod" >&nbsp;</a>-->
</td>
<td>
    <% if (replicationController){ %>
        <span><%- replicas %></span>
    <% }  else { %>
        none
    <% } %>
</td>
<td>
    <% if (status) { %>
        <span class="<%- status %>"><%- status %></span>
        <% if ( status == 'running') { %>
            <span class="stop-btn" title="Stop <%- name %> pod">Stop</span>
        <% } else if ( status == 'stopped' ) { %>
            <span class="start-btn" title="Start <%- name %> pod">Start</span>
        <% } else if ( status == 'waiting' ) { %>
            <span class="stop-btn" title="Stop <%- name %> pod">Stop</span>
        <% } %>
    <% } else { %>
        <span class="stopped">stopped</span>
        <span class="start-btn" title="Start <%- name %> pod">Start</span>
    <% } %>
</td>
<td>
    <%- _.find(kubeTypes, function(e) { return e.id == kube_type; }).name %> (<%- kubes %>)
</td>