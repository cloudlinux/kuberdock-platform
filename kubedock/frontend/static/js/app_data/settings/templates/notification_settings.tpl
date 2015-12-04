<div class="tab-pane fade in" id="settingsNotificationTab">
    <div class="content-body">
        <div class="row">
             <div class="col-xs-6 col-xs-offset-1">
                <label for="notifyEmail">Where should we notify you?</label>
                <input type="email" placeholder="Email" name="" id="notifyEmail">
            </div>
            <div class="col-xs-5 bell"></div>
          </div>
        <div class="row">
            <div class="col-xs-6 col-xs-offset-1">
                <label for="smtp">SMTP</label>
                <input type="text"  name="" id="smtp">
            </div>
            <div class="col-xs-5 inline">
                <label for="autorization" class="custom">
                    <input type="checkbox" id="autorization"/>
                    <span></span>
                Authorization needed</label>
            </div>
        </div>
        <div class="row">
            <div class="col-xs-6 col-xs-offset-1">
                <label>Connection type</label>
                <select class="selectpicker" id="conectionType">
                    <option>Select 1</option>
                    <option>Select 2</option>
                    <option>Select 3</option>
                </select>
            </div>
        <div class="col-xs-5 inline">
            <label for="certificates" class="custom">
                <input type="checkbox" id="certificates"/>
                <span></span>
                Recieve certificates
            </label>
            </div>
        </div>
        <div class="row notifications">
            <div class="col-xs-11 col-xs-offset-1"
                 id="notification-templates">
                <label>Notification templates</label>
            </div>
        </div>
    </div>
    <div class="buttons pull-right">
        <button id="user-cancel-btn" class="">Cancel</button>
        <button id="user-add-btn" class="" type="submit">Submit</button>
    </div>
</div>