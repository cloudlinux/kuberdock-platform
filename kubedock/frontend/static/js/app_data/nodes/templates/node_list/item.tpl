<td><a href="/#nodes/<%- id %>/general"><%- hostname ? hostname : ip ? ip : 'Not specified' %></a></td>
<td><%- ip %></td>
<td><%- kubeType %></td>
<td><span class="<%- status %>"><%- status %></span></td>
<td><span class="deleteNode" data-toggle="tooltip" data-placement="top" title="Delete <%- hostname %> node">&nbsp;</span></td>