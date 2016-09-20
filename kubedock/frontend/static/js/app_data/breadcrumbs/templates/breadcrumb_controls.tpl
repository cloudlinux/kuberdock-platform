<% if (button){ %>
    <% if (button.suspendedTitle) { %>
        <button id="<%- button.id %>" class="disabled" data-toggle="tooltip" data-placement="left" data-original-title="<%- button.suspendedTitle %>"> <%- button.title %></button>
    <% } else { %>
        <% if (button.href) { %>
            <a id="<%- button.id %>" href="<%- button.href %>"><%- button.title %></a>
        <% } else { %>
            <button id="<%- button.id %>"><%- button.title %></button>
        <% } %>
    <% }%>
<% } %>
<% if (search){ %>
    <div class="nav-search" id="nav-search"></div>
    <input type="text" placeholder="Search" class="nav-search-input" id="nav-search-input" autocomplete="off">
<% } %>
