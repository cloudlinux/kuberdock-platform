<% if ( c.state.pageSize < c.state.totalRecords){ %>
    <ul class="pager" style="margin-top: <%= ((c.state.pageSize - c.length) * 50) + 10 %>px">
        <li class="paginatorPrev border pseudo-link <%- c.state.currentPage == 1 ? 'disabled' : ''%>">Prev</li>
        <li class="paginatorStat pseudo-link"><%- c.state.currentPage %> of <%- c.state.totalPages %></li>
        <li class="paginatorNext border pseudo-link <%- c.state.currentPage == c.state.totalPages ? 'disabled' : '' %>">Next</li>
    </ul>
<% } %>