<div class="container create-app">
    <div class="col-md-12 no-padding">
        <div>
            <label for="app-name">Enter App name</label>
            <input type="text" id="app-name" placeholder="Enter app name" value="<%= name %>">
            <input type="hidden" id="app-origin" value="<%= origin %>">
        </div>
        <label class="upload" for"app-upload">Upload yaml
            <input type="file" id="app-upload">
        </label>
        <textarea id="app-contents" placeholder="Upload and edit you pod yaml" cols="80" rows="8"><%= template %></textarea>
        <div class="more-info">
            <div>You can specify custom fields to let user fill it or to be generated automatically while starting an application if you need.<br>
                More information on <a href="http://docs.kuberdock.com/index.html?predefined_applications.htm" target="_blank">docs.kuberdock.com</a> section "<b>Administration</b>" -> "<b>Predefined application</b>"</div>
        </div>
        <div class="buttons clearfix">
            <button class="save-app blue">Save</button>
            <button class="cancel-app gray">Cancel</button>
        </div>
    </div>
</div>