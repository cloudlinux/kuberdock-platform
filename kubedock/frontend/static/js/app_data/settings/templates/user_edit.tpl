<% if (edit) { %>
    <div id="user-contents" class="clearfix settings-user">
        <div id="user-controls" class="col-md-12 no-padding">
            <div class="form-group col-md-offset-3">
                <label for="firstname">First name</label>
                <input type="text" name="firstname" class="form-control" id="firstname">
            </div>
            <div class="form-group col-md-offset-3">
                <label for="lastname">Last name</label>
                <input type="text" name="lastname" class="form-control" id="lastname">
            </div>
            <div class="form-group col-md-offset-3">
                <label for="middle_initials">Middle initials</label>
                <input type="text" name="middle_initials" class="form-control" id="middle_initials">
            </div>
            <div class="form-group col-md-offset-3">
                <label for="email">E-mail</label>
                <input type="email" name="email" class="form-control" id="email">
            </div>
            <div class="form-group col-md-offset-3">
                <label for="password">Password</label>
                <input type="password" class="form-control" id="password" name="password">
                <input type="password" class="form-control" id="password-again" name="password-again">
            </div>
            <div class="form-group col-md-offset-3">
                <label for="timezone">Timezone</label>
                <input type="text" name="timezone" class="form-control" id="timezone">
            </div>
        </div>
        <div class="buttons pull-right">
            <button id="template-back-btn">Cancel</button>
            <button id="template-save-btn" class="hideButton" type="submit">Save changes</button>
        </div>
    </div>
<% } else { %>
    <div id="user-contents" class="clearfix settings-user">
        <div id="user-controls" class="col-md-12 no-padding">
            <div class="form-group col-md-offset-3 show">
                <label for="firstname">First name</label>
                <div><%- first_name ? first_name : 'No first name'%></div>
                <label for="lastname">Last name</label>
                <div><%- last_name ? last_name : 'No last name'%></div>
                <label for="middle_initials">Middle initials</label>
                <div><%- middle_initials ? middle_initials : 'No middle initials'%></div>
                <label for="email">E-mail</label>
                <div><%- email ? email : 'No email'%></div>
                <label for="timezone">Timezone</label>
                <div><%- timezone ? timezone : ''%></div>
            </div>
        </div>
        <div class="buttons pull-right">
            <button id="template-edit-btn" type="submit">Edit</button>
            <!-- <button id="template-remove-btn" class="pull-right" type="submit">Terminate account</button> -->
        </div>
    </div>
<% } %>