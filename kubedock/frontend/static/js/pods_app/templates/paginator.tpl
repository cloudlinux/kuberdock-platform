<% if ( c.state.pageSize < c.state.totalRecords){ %>
<ul class="pager">
    <li class="paginatorFirst pseudo-link">First</li>
    <li class="paginatorPrev pseudo-link">Prev</li>
    <li class="paginatorStat pseudo-link"><%- c.state.currentPage %> of <%- c.state.totalPages %></li>
    <li class="paginatorNext pseudo-link">Next</li>
    <li class="paginatorLast pseudo-link">Last</li>
</ul>
<% } %>