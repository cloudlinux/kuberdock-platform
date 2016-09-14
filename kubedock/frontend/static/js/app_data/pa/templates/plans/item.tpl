<% if (recommended){ %>
    <span class="title">recommended</span>
<% } %>
<div class="plan-img-wrapper">
    <div class="plan-name"><%- name %></div>
    <div class="price-wrapper">
        <div class="plan-price"><%- info.prefix %><%- (info.price).toFixed(2) %></div>
        <div class="text-right">
            <span class="plan-price-suffix"><%- info.suffix %></span>
            <span class="plan-period">/<%- info.period %></span>
        </div>
    </div>
</div>
<% if (goodFor){ %>
    <div class="plan-goodfor">Good for<br/><span><%- goodFor %></span></div>
<% } %>
<div class="show-more">Show details</div>
<div class="plan-details">
    <% if (info.cpu){ %><p><b>CPU:</b> <span><%- (info.cpu).toFixed(2) %> Cores</span></p><% } %>
    <% if (info.memory){ %><p><b>Мemory:</b> <span><%- info.memory %> MB</span></p><% } %>
    <% if (info.diskSpace){ %><p><b>Storage:</b> <span><%- info.diskSpace %> GB</span></p><% } %>
    <% if (info.totalPD){ %><p><b>Persistent Storage:</b> <span><%- info.totalPD %> GB</span></p><% } %>
    <% if (info.publicIP){ %><p><b>Public IP:</b><span> yes</span></p><% } %>
</div>
<div class="buttons">
    <% if (!current){ %>
        <button class="choose-button">Choose package</button>
    <% } else { %>
        <button class="current-button">current package</button>
    <% } %>
</div>
