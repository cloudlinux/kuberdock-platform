<div class="breadcrumbs-wrapper">
    <div class="container breadcrumbs" id="breadcrumbs">
        <ul class="breadcrumb">
            <li>
                <div id="users-page">Users</div>
            </li>
            <li class="active">Activity</li>
        </ul>
    </div>
</div>
<div class="container">
    <div class="row" id="all-user-activity-tab">
        <div class="col-md-2 col-sm-12 sidebar">
            <ul class="nav nav-sidebar list-unstyled" role="tablist">
                <li class="usersPage users"><span>Users</span></li>
                <li class="activityPage active"><span>Users activity</span></li>
            </ul>
        </div>
        <div class="tab-content col-md-10 col-sm-12">
            <div class="col-sm-12 serch-control">
                <div class="col-sm-5 no-padding form-group">
                    <div class="col-sm-6 no-padding input-wrap">
                        <input type="text" id="dateFrom" placeholder="From">
                        <i class="calendar"></i>
                    </div>
                    <div class="col-sm-6 no-padding input-wrap">
                        <input type="text" id="dateTo" placeholder="To">
                        <i class="calendar"></i>
                    </div>
                </div>
                <div class="col-sm-4 no-padding form-group input-wrap open">
                    <input type="text" name="username" placeholder="Search username" id="username" autocomplete="off">
                    <i class="search"></i>
                </div>
            </div>
            <table class="table" id="all-users-activities-table">
            <thead>
                <tr>
                    <th class="col-md-3">Last activity</th>
                    <th class="col-md-5">Date / time</th>
                    <th class="col-md-4">IP</th>
                </tr>
            </thead>
                <tbody id="users-activities-table"></tbody>
            </table>
        </div>
    </div>
</div>
