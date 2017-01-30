<div>
    <div class="breadcrumbs-wrapper">
        <div class="container breadcrumbs" id="breadcrumbs">
            <ul class="breadcrumb">
                <li class="active">
                    <div>Settings</div>
                </li>
            </ul>
        </div>
    </div>
    <div class="container">
        <div class="row">
            <div class="col-sm-12 col-md-2 sidebar">
                <ul class="nav nav-sidebar list-unstyled" >
                    <% if(user.get('rolename')  === 'Admin') { %>
                        <li class="general">
                            <a href="/#settings/general">General</a>
                        </li>
                        <li class="license">
                            <a href="/#settings/usage">Usage info</a>
                        </li>
                        <li class="domain">
                            <a href="/#settings/domain">DNS provider</a>
                        </li>
                        <li class="billing">
                            <a href="/#settings/billing">Billing</a>
                        </li>
                    <% } %>
                    <li class="profile">
                        <a href="/#settings/profile">Profile</a>
                    </li>
                </ul>
            </div>
            <div id="details_content" class="col-sm-12 col-md-10">
                <div class="row placeholders">
                </div>
            </div>
        </div>
    </div>
</div>
