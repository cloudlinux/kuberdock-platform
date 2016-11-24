<button type="button" class="btn btn-primary go-to-app pull-right" <%= ready ? '' : 'disabled' %>>
    Go to application
</button>

<div class="btn-group controls pull-right">
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
