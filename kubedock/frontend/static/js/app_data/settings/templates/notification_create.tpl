<div id="settingsNotificationEditTab">
    <div id="user-contents" class="row">
        <div id="user-controls">
            <div class="status-line">
                <label>User Created Notification template</label>
            </div>
            <div class="col-xs-8 col-xs-offset-1">
                <div class="form-group">
                    <label for="id_text_html">HTML</label>
                    <textarea id="id_text_html" rows="10"></textarea>
                </div>
                <div class="form-group">
                    <label for="id_text_plain">Plain Text</label>
                    <textarea id="id_text_plain" rows="10"></textarea>
                </div>
                <div class="form-group">
                    <label for="id_event">Event</label>
                    <select name="event" id="id_event">
                        <option value="eid">event</option>
                    </select>
                </div>
                <div class="help_text">
                    <strong>Template keys</strong>:<br/>
                    <i id="event_keys"></i>
                </div>
                <div class="checkbox">
                    <label class="">
                        <input type="checkbox" name="as_html" id="id_as_html">
                        <span></span>
                        Send as HTML
                    </label>
                </div>
            </div>
        </div>
        <div class="buttons pull-right">
            <button id="template-back-btn">Cancel</button>
            <button id="template-add-btn" class="" type="submit">Submit</button>
        </div>
    </div>
</div>