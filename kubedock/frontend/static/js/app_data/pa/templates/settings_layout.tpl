<div class="container settings">
    <div id="masthead">
        <div id="app-header"><span><%= name %></span></div>
        <div id="pre-description"></div>
    </div>
    <% if (has_simple) { %>
    <div id="recource-fields"></div>
    <!-- resource fields -->
    <% } %>
    <div id="resource-list">
        <p>CPU: <span class='plan-cpu'>
                    <%= plan.get('info').cpu.toFixed(3) %> <%= plan.get('info').kubeType.cpu_units %>
                </span></p>
        <p>Мemory: <span class='plan-memory'>
                    <%= plan.get('info').memory %> <%= plan.get('info').kubeType.memory_units %>
                </span></p>
        <p>Storage: <span class='plan-disk'>
                    <%= plan.get('info').diskSpace %> <%= plan.get('info').kubeType.disk_space_units %>
                </span></p>
        <p <%= plan.get('info').totalPD ? '' : 'class="hidden"' %>>
        Persistent Storage: <span class='plan-pd'>
                    <%= plan.get('info').totalPD %> GB
                </span></p>
        <p <%= plan.get('info').publicIP ? '' : 'class="hidden"' %>>
        <span class='plan-public'>Public IP: yes</span></p>
    </div>
    <div id="select-controls"></div>
    <div class="clearfix">
        <div class="plan-period">/<%= plan.get('info').period %></div>
        <div class="plan-price"><%= plan.get('info').prefix %> <%=
            plan.get('info').price.toFixed(2) %>
        </div>
    </div>
    <div id="controls" class="buttons" class="clearfix">
        <button id="back-button" class="gray">Choose different package</button>
        <% if (billing_type.toLowerCase() != 'no billing') { %>
        <button id="submit-button" class="blue">Order now</button>
        <% } else { %>
        <button id="submit-button" class="blue">Start App</button>
        <% } %>
    </div>
</div>