<% if ( c.state.pageSize < c.state.totalRecords){ %>
<ul class="pager">
    <li class="paginatorFirst pseudo-link custom-link btn btn-small">first</li>
    <li class="paginatorPrev pseudo-link custom-link btn btn-small">prev</li>
    <li class="paginatorStat btn btn-small green"><%- c.state.currentPage %> of <%- c.state.totalPages %></li>
    <li class="paginatorNext pseudo-link custom-link  btn btn-small">next</li>
    <li class="paginatorLast pseudo-link custom-link btn btn-small">last</li>
</ul>
<% } %>