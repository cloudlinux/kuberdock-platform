<% if ( c.state.pageSize < c.state.totalRecords){ %>
<ul class="pager">
<!--     <li class="paginatorFirst pseudo-link">First</li> -->
    <li class="paginatorPrev border pseudo-link">Prev</li>
    <li class="paginatorStat pseudo-link"><%- c.state.currentPage %> of <%- c.state.totalPages %></li>
    <li class="paginatorNext border pseudo-link">Next</li>
<!--     <li class="paginatorLast pseudo-link">Last</li> -->
</ul>
<% } %>