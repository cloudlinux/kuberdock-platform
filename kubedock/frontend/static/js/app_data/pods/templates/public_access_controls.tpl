<div class="col-xs-12">
    <label class="normal margin-bottom-2">Public access type ***:</label>
    <label class="custom margin-bottom-3 radio-inline">
        <input id="public-access-type-ip" class="public-access-type"
                value="ip" type="radio" name="public-access-type"
                <%= typeof domain == 'undefined' || domain == null ? 'checked' : '' %>>
        <span></span><i><%= isAWS ? 'Standard domain' : 'Public IP' %></i>
    </label>
    <label class="custom margin-bottom-3 radio-inline">
        <input id="public-access-type-domain" class="public-access-type"
                value="domainName" type="radio" name="public-access-type"
                <%= typeof domain == 'undefined' || domain == null ? '' : 'checked' %>>
        <span></span><i><%= isAWS ? 'Specific domain' : 'Domain' %></i>
    </label>
</div>
<div class="col-xs-12">
    <div class="col-md-5 col-xs-12 select-domain-wrapper no-padding">
        <label class="normal margin-bottom-2">Select domain:</label>
        <div class="select-wrapper">
            <span class="info-icon" data-toggle="tooltip" data-placement="right" title="Support only ports 80 and 443 at pod port"></span>
            <select class="choose-domain-select">
                <%  domains.each(function(domain){ %>
                    <option value="<%= domain.get('name') %>"><%= domain.get('name') %></option>
                <% }) %>
            </select>
        </div>
    </div>
</div>