<table id="nodelist-table" class="table">
    <thead>
        <tr>
            <th class="hostname">Node<b class="caret <%= sortingType.hostname == -1 ? 'rotate' : '' %>"></b></th>
            <th class="ip">IP<b class="caret <%= sortingType.ip == -1 ? 'rotate' : '' %>"></b></th>
            <th class="kube_type">Kube Type<b class="caret <%= sortingType.kube_type == -1 ? 'rotate' : '' %>"></b></th>
            <th class="status">Status<b class="caret <%= sortingType.status == -1 ? 'rotate' : '' %>"></b></th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody></tbody>
</table>
