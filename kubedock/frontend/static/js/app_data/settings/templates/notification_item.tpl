<div class="col-xs-12 no-padding group">
    <span> <%- event.name %> </span>
    <label class="custom" for="itm<%- id %>">
        <input type="checkbox" class="sendAsHTML" id="itm<%- id %>" <% if(as_html) { %>checked<% } %> />
        send as html
    </label>
</div>
