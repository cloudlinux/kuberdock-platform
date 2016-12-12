<div class="btn-group controls">
    <span type="button" class="dropdown-toggle" data-toggle="dropdown">
        <span class="ic_reorder">
            <span>Actions</span>
            <i class="caret"></i>
        </span>
    </span>
    <ul class="dropdown-menu" role="menu">
        <% if (ableTo('redeploy')) { %><li><span class="restart-btn"><span>Restart</span></span></li><% } %>
        <% if (ableTo('start')) { %><li><span class="start-btn"><span>Start</span></span></li><% } %>
        <% if (ableTo('stop')) { %><li><span class="stop-btn"><span>Stop</span></span></li><% } %>
    </ul>
</div>
<button type="button" class="active-button go-to-app" <%= ready ? '' : 'disabled' %>>
    <span>Go to application</span>
</button>
