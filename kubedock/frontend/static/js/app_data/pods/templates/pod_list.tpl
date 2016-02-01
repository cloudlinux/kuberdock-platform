<div class="col-md-12 no-padding">
    <div class="podsControl" style="display:<%- checked ? 'block' : 'none' %>">
        <span class="count"><%- checked %><%- (checked > 1) ? ' Items' : ' Item' %></span>
        <span class="runPods" title="Run">Run</span>
        <span class="stopPods" title="Stop">Stop</span>
        <span class="removePods" title="Delete">Delete</span>
    </div>
    <table id="podlist-table" class="table">
        <thead class="<%- checked ? 'pods-checked' : '' %>">
            <tr>
                <th class="checkboxes">
                    <label class="custom">
                        <input type="checkbox" <%- allChecked? 'checked' : '' %> <%- isCollection %> >
                        <span></span>
                    </label>
                </th>
                <th class="name">Pod name<b class="caret <%= sortingType.name == -1 ? 'rotate' : '' %>"></th>
                <th class="replicas">Replicated<b class="caret <%= sortingType.replicas == -1 ? 'rotate' : '' %>"></b></th>
                <th class="status">Status<b class="caret <%= sortingType.status == -1 ? 'rotate' : '' %>"></b></th>
                <th class="kube_type">Kube Type<b class="caret <%= sortingType.kube_type == -1 ? 'rotate' : '' %>"></th>
                <th>Number of Kubes</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>
