<% if ( c.state.pageSize < c.state.totalRecords){ %>
<ul class="pager">
    <li class="paginatorFirst pseudo-link btn btn-default btn-sm btn-group">first</li>
    <li class="paginatorPrev pseudo-link btn btn-default btn-sm btn-group">prev</li>
    <li class="paginatorStat"><%- c.state.currentPage %> of <%- c.state.totalPages %></li>
    <li class="paginatorNext pseudo-link btn btn-default btn-sm btn-group">next</li>
    <li class="paginatorLast pseudo-link btn btn-default btn-sm btn-group">last</li>
</ul>
<% } %>