<div class="breadcrumbs-wrapper">
    <div class="container breadcrumbs" id="breadcrumbs">
        <ul class="breadcrumb">
            <li class="active">Users</li>
        </ul>
        <div class="control-group">
            <button id="create_user">Create user</button>
            <!--
            <div class="nav-search" id="nav-search"></div>
            <input type="text" placeholder="Search" class="nav-search-input" id="nav-search-input" autocomplete="off">
            -->
        </div>
    </div>
</div>
<div class="container">
    <div class="row">
        <div class="col-sm-3 col-md-2 sidebar">
            <ul class="nav nav-sidebar list-unstyled" role="tablist">
                <li class="general active">Users</li>
                <!-- <li class="onlinePage">Online users</li> -->
                <li class="activityPage">Users activity</li>
            </ul>
        </div>
        <div id="details_content" class="col-sm-10">
            <div class="row placeholders">
                <div class="tab-content col-xs-12">
                    <table id="userslist-table" class="table col-sm-12 no-padding">
                        <thead>
                            <tr>
                               <th class="username">Name<span class="caret <%= sortingType.username == -1 ? 'rotate' : '' %>"></span></th>
                               <th class="pods_count">Pods<span class="caret <%= sortingType.pods_count == -1 ? 'rotate' : '' %>"></span></th>
                               <th class="containers_count">Containers<span class="caret <%= sortingType.containers_count == -1 ? 'rotate' : '' %>"></span></th>
                               <th class="email">Email<span class="caret <%= sortingType.email == -1 ? 'rotate' : '' %>"></span></th>
                               <th class="package">Package<span class="caret <%= sortingType.package == -1 ? 'rotate' : '' %>"></span></th>
                               <th class="rolename">Role<span class="caret <%= sortingType.rolename == -1 ? 'rotate' : '' %>"></span></th>
                               <th class="active">Status<span class="caret <%= sortingType.active == -1 ? 'rotate' : '' %>"></span></th>
                               <th>Actions</span></th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>