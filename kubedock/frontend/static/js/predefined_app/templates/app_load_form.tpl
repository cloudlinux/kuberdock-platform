<div>
    <input type="text" id="app-name" placeholder="Enter app name" value="<%= name %>">
</div>
<div>
    <input type="file" id="app-upload">
</div>
<div>
    <textarea id="app-contents" cols="80" rows="8"><%= template %></textarea>
</div>
<div class="buttons pull-right">
    <button class="cancel-app gray">Cancel</button>
    <button class="save-app blue">Save</button>
</div>