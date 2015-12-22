<div id="nav"></div>
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
            <div class="col-sm-3 col-md-2 sidebar">
                <ul class="nav nav-sidebar list-unstyled" >
                    <% if(backendData.administrator) { %>
                    <li class="general">
                        General
                    </li>
                    <li class="license">
                        License
                    </li>
                    <% } %>
                    <li class="profile">
                        Profile
                    </li>
                    <!-- <li class="notifications">
                        Notification
                    </li>
                    <li class="permissions">
                        Permision
                    </li> -->
                </ul>
            </div>
            <div id="details_content" class="col-sm-10">
                <div class="row placeholders">
                </div>
            </div>
        </div>
    </div>
</div>