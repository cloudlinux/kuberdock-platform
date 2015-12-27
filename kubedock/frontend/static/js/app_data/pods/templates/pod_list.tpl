<div class="col-md-12 no-padding">
    <div class="podsControl" style="display:<%- checked ? 'block' : 'none' %>">
        <span class="count"><%- checked %><%- (checked > 1) ? ' Items' : ' Item' %></span>
        <span class="runPods">Run</span>
        <span class="stopPods">Stop</span>
        <span class="removePods">Delete</span>
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
                <th class="name">Pod name<b class="caret"></th>
                <th class="replicas">Replicated<b class="caret"></b></th>
                <th class="status">Status<b class="caret"></b></th>
                <th class="kube_type">Kube type<b class="caret"></th>
                <th>Kubes quantity</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>
