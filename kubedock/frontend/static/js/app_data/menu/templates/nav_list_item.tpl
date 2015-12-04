<% if (children.length){ %>
<a href="<%= path %>" class="dropdown-toggle" data-toggle="dropdown"><%= name %><b class="caret"></b></a>
<ul class="dropdown-menu">
<% _.each(children, function(i){ %>
<li><a href="<%= i.path %>"><%= i.name %></a></li>
<% }) %>
</ul>
<% } else { %>
<a href="<%= path %>"><%= name %></a>
<% } %>