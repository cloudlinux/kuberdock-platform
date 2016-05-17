<td><a href="/#nodes/<%- id %>/general" title="Show <%- hostname %> page"><%- hostname ? hostname : ip ? ip : 'Not specified' %></a></td>
<td><%- ip %></td>
<td><%- kubeType %></td>
<td><span class="<%- status %>"><%- status %></span></td>
<td><span class="deleteNode" title="Remove <%- hostname %> node">&nbsp;</span></td>