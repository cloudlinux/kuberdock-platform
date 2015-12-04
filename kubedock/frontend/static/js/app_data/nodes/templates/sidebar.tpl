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
    <li role="presentation" class="general <%- s.general %> nodeGeneralTab">General</li>
    <!-- <li role="presentation" class="stats <%- s.stats %> nodeStatsTab">Stats</li> -->
    <li role="presentation" class="<%- s.logs %> nodeLogsTab">Logs</li>
    <li role="presentation" class="<%- s.monitoring %> nodeMonitoringTab">Monitoring</li>
    <!-- <li role="presentation" class="<%- s.timelines %> nodeTimelinesTab">Timelines</li>
    <li role="presentation" class="configuration <%- s.configuration %> nodeConfigurationTab">Configuration</li> -->
</ul>
