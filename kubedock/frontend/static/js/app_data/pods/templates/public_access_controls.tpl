<% if (!isAWS){ %>
<div class="col-xs-12">
    <label class="normal margin-bottom-2">Public access type ***:</label>
    <label class="custom margin-bottom-3 radio-inline">
        <input id="public-access-type-ip" class="public-access-type"
                value="ip" type="radio" name="public-access-type"
                <%= typeof domain == 'undefined' || domain == null ? 'checked' : '' %>>
        <span></span><i>Public IP</i>
    </label>
    <label class="custom margin-bottom-3 radio-inline">
        <input id="public-access-type-domain" class="public-access-type"
                value="domainName" type="radio" name="public-access-type"
                <%= typeof domain == 'undefined' || domain == null ? '' : 'checked' %>>
        <span></span><i>Domain</i>
        <span class="help" data-toggle="tooltip" data-placement="right" title="Support only ports 80 and 443 at pod port"></span>
    </label>
</div>
<% } %>
<div class="col-xs-12">
    <div class="col-md-5 col-xs-12 select-domain-wrapper no-padding">
        <label class="normal margin-bottom-2">
            Select domain:
            <% if (isAWS){ %>
            <span class="help inline" data-toggle="tooltip" data-placement="right" title="Support only ports 80 and 443 at pod port"></span>
            <% } %>
        </label>
        <select class="choose-domain-select">
            <%  domains.each(function(domain){ %>
                <option value="<%= domain.get('name') %>"><%= domain.get('name') %></option>
            <% }) %>
        </select>
    </div>
</div>
