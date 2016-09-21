<% if (!hidden) { %>
    <div class="custom-field-item">
        <label class="custom-field-title"><%= label %></label>
        <div class="custom-field-body">
            <input id="field-<%= name %>" class="custom-field"
                   type="text" value="<%= default_value %>">
        </div>
    </div>
<% } %>