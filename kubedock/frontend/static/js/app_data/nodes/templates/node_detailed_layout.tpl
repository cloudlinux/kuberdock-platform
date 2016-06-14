<div id="nav"></div>
<div class="breadcrumbs-wrapper">
    <div class="container breadcrumbs" id="breadcrumbs">
        <ul class="breadcrumb">
            <li>
                <div id="nodes-page">Nodes</div>
            </li>
            <li class="active"><%= hostname %></li>
        </ul>
        <div class="control-group">
            <button id="delete_node">Delete</button>
        </div>
    </div>
</div>
<div class="container">
    <div class="row">
        <div class="col-sm-3 col-md-2 sidebar">
            <ul class="nav nav-sidebar">
            <% var s = {};
            switch (tab) {
                case 'general': s.general = 'active'; break;
                case 'stats': s.stats = 'active'; break;
                case 'logs': s.logs = 'active'; break;
                case 'monitoring': s.monitoring = 'active'; break;
                case 'timelines': s.timelines = 'active'; break;
                case 'configuration': s.configuration = 'active'; break;
            } %>
                <li role="presentation" class="general <%- s.general %> nodeGeneralTab"><span>General</span></li>
                <!-- <li role="presentation" class="stats <%- s.stats %> nodeStatsTab">Stats</li> -->
                <li role="presentation" class="stats <%- s.logs %> nodeLogsTab"><span>Logs</span></li>
                <li role="presentation" class="monitoring <%- s.monitoring %> nodeMonitoringTab"><span>Monitoring</span></li>
                <!-- <li role="presentation" class="<%- s.timelines %> nodeTimelinesTab">Timelines</li>
                <li role="presentation" class="configuration <%- s.configuration %> nodeConfigurationTab">Configuration</li> -->
            </ul>
        </div>
        <div id="details_content" class="col-sm-10">
            <div id="tab-content"></div>
        </div>
    </div>
</div>