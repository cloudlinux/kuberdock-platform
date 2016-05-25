<div class="content-body clearfix" id="persistentVolumes-tab">
    <div class="col-xs-12 no-padding">
        <div class="row">
            <div class="col-xs-12">
                <table class="table" id="persistent-volumes-table">
                    <thead>
                        <tr>
                            <th class="name">Volume Name<b class="caret <%= sortingType.name == -1 ? 'rotate' : '' %>"></b></th>
                            <th class="size">Size<b class="caret <%= sortingType.size == -1 ? 'rotate' : '' %>"></b></th>
                            <th class="in_use">Status<b class="caret <%= sortingType.in_use == -1 ? 'rotate' : '' %>"></b></th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
                <div class="buttons clearfix">
                    <div class="description pull-left">* Each persistent volume billed as usual regardless of its status</div>
                </div>
            </div>
        </div>
    </div>
</div>
